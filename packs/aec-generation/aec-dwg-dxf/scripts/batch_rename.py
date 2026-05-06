"""Batch rename DXF files based on titleblock content.

Default pattern: {drawing_number}_{drawing_title}_R{revision}.dxf

Usage:
    python batch_rename.py <dir> [--pattern "{drawing_number}_{drawing_title}.dxf"]
                                  [--apply]            # without --apply = dry-run
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from _common import iter_dxf_files
from extract_titleblock import extract_one, load_config

DEFAULT_PATTERN = "{drawing_number}_{drawing_title}_R{revision}.dxf"
SAFE_RE = re.compile(r'[\\/:*?"<>|]+')


def safe_name(s: str) -> str:
    return SAFE_RE.sub("_", s).strip().strip(".")


def plan_renames(target: str, pattern: str, config: str | None) -> list[dict]:
    patterns, field_map = load_config(config)
    plan: list[dict] = []
    for p in iter_dxf_files(target):
        recs = extract_one(p, patterns, field_map)
        rec = next((r for r in recs if "error" not in r), None)
        if rec is None:
            plan.append({"source": str(p), "skipped": "no titleblock"})
            continue
        try:
            new_stem = pattern.format(**{k: safe_name(str(v)) for k, v in rec.items()})
        except KeyError as e:
            plan.append({"source": str(p), "skipped": f"missing field {e}"})
            continue
        new_name = new_stem if new_stem.lower().endswith(".dxf") else f"{new_stem}.dxf"
        new_path = p.with_name(new_name)
        plan.append({
            "source": str(p),
            "target": str(new_path),
            "would_rename": p.name != new_path.name,
        })
    return plan


def apply_plan(plan: list[dict], log_path: Path) -> int:
    log: list[dict] = []
    renamed = 0
    for item in plan:
        if not item.get("would_rename"):
            continue
        src = Path(item["source"])
        dst = Path(item["target"])
        if dst.exists():
            item["error"] = "target exists"
            log.append(item)
            continue
        src.rename(dst)
        log.append({"from": str(src), "to": str(dst)})
        renamed += 1
    log_path.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")
    return renamed


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("target")
    ap.add_argument("--pattern", default=DEFAULT_PATTERN)
    ap.add_argument("--config")
    ap.add_argument("--apply", action="store_true",
                    help="Actually perform renames (default is dry-run)")
    ap.add_argument("--log", default="rename-log.json")
    args = ap.parse_args()

    plan = plan_renames(args.target, args.pattern, args.config)
    print(json.dumps(plan, ensure_ascii=False, indent=2))

    if args.apply:
        n = apply_plan(plan, Path(args.log))
        print(f"\nRenamed {n} file(s). Log → {args.log}")
    else:
        n = sum(1 for i in plan if i.get("would_rename"))
        print(f"\n[dry-run] {n} file(s) would be renamed. Pass --apply to execute.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
