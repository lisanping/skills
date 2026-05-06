"""Generate a sheet index (drawing list) by extracting titleblocks from a folder.

Usage:
    python generate_index.py <dir> [--format md|csv|json] [--output index.md]
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from pathlib import Path

from _common import iter_dxf_files
from extract_titleblock import extract_one, load_config

COLUMNS = [
    ("drawing_number", "图号"),
    ("drawing_title", "图名"),
    ("revision", "版次"),
    ("scale", "比例"),
    ("date", "日期"),
    ("source", "文件"),
]


def collect(target: str, config: str | None) -> list[dict]:
    patterns, field_map = load_config(config)
    rows: list[dict] = []
    for p in iter_dxf_files(target):
        for rec in extract_one(p, patterns, field_map):
            if "error" in rec:
                continue
            rec["source"] = Path(rec["source"]).name
            rows.append(rec)
    rows.sort(key=lambda r: (r.get("drawing_number") or "", r.get("source") or ""))
    return rows


def to_markdown(rows: list[dict]) -> str:
    head = "| " + " | ".join(label for _, label in COLUMNS) + " |"
    sep = "| " + " | ".join("---" for _ in COLUMNS) + " |"
    body = []
    for r in rows:
        body.append("| " + " | ".join(str(r.get(k) or "") for k, _ in COLUMNS) + " |")
    return "\n".join(["# 图纸目录", "", head, sep, *body, ""])


def to_csv(rows: list[dict]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([label for _, label in COLUMNS])
    for r in rows:
        w.writerow([r.get(k) or "" for k, _ in COLUMNS])
    return buf.getvalue()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("target")
    ap.add_argument("--format", choices=["md", "csv", "json"], default="md")
    ap.add_argument("--config")
    ap.add_argument("--output")
    args = ap.parse_args()

    rows = collect(args.target, args.config)

    if args.format == "md":
        out = to_markdown(rows)
    elif args.format == "csv":
        out = to_csv(rows)
    else:
        out = json.dumps(rows, ensure_ascii=False, indent=2)

    if args.output:
        Path(args.output).write_text(out, encoding="utf-8")
        print(f"Wrote index for {len(rows)} sheet(s) → {args.output}")
    else:
        print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
