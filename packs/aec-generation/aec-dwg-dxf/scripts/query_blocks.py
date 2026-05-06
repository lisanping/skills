"""Query block instances and their attributes from one or more DXF files.

Usage:
    python query_blocks.py <file_or_dir> [--block PATTERN] [--attr TAG=VALUE]
                                          [--format json|csv]
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
from pathlib import Path

from _common import iter_dxf_files, normalize_tag, open_dxf


def parse_attr_filter(s: str) -> tuple[str, re.Pattern[str]]:
    if "=" not in s:
        raise argparse.ArgumentTypeError("expected TAG=VALUE_REGEX")
    tag, val = s.split("=", 1)
    return normalize_tag(tag), re.compile(val, re.IGNORECASE)


def query(target: str, block_pattern: str | None,
          attr_filters: list[tuple[str, re.Pattern[str]]]) -> list[dict]:
    bp = re.compile(block_pattern, re.IGNORECASE) if block_pattern else None
    rows: list[dict] = []
    for p in iter_dxf_files(target):
        doc = open_dxf(p)
        for insert in doc.modelspace().query("INSERT"):
            if bp and not bp.match(insert.dxf.name):
                continue
            attribs = {normalize_tag(a.dxf.tag): (a.dxf.text or "") for a in insert.attribs}
            if attr_filters and not all(
                tag in attribs and pat.search(attribs[tag])
                for tag, pat in attr_filters
            ):
                continue
            rows.append({
                "source": p.name,
                "block": insert.dxf.name,
                "handle": insert.dxf.handle,
                "layer": insert.dxf.layer,
                "x": round(insert.dxf.insert.x, 3),
                "y": round(insert.dxf.insert.y, 3),
                "z": round(insert.dxf.insert.z, 3),
                **attribs,
            })
    return rows


def to_csv(rows: list[dict]) -> str:
    if not rows:
        return ""
    cols: list[str] = []
    seen = set()
    for r in rows:
        for k in r.keys():
            if k not in seen:
                seen.add(k)
                cols.append(k)
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=cols)
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("target")
    ap.add_argument("--block", help="Block name regex (case-insensitive)")
    ap.add_argument("--attr", action="append", default=[],
                    type=parse_attr_filter,
                    help="ATTRIB filter, e.g. FIRE_RATING=2\\.0h (repeatable)")
    ap.add_argument("--format", choices=["json", "csv"], default="json")
    ap.add_argument("--output")
    args = ap.parse_args()

    rows = query(args.target, args.block, args.attr)
    out = to_csv(rows) if args.format == "csv" else json.dumps(rows, ensure_ascii=False, indent=2)

    if args.output:
        Path(args.output).write_text(out, encoding="utf-8")
        print(f"Wrote {len(rows)} row(s) → {args.output}")
    else:
        print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
