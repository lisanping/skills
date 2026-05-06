"""Diff two IFC models at the entity level (added / removed / changed-name).

Usage:
    python model_diff.py <baseline.ifc> <revised.ifc> [--output diff.json]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from _common import open_ifc

TRACKED_TYPES = ["IfcWall", "IfcSlab", "IfcColumn", "IfcBeam",
                 "IfcDoor", "IfcWindow", "IfcSpace", "IfcBuildingStorey"]


def index(path: str) -> dict[str, dict]:
    f = open_ifc(path)
    out: dict[str, dict] = {}
    for t in TRACKED_TYPES:
        for e in f.by_type(t):
            out[e.GlobalId] = {
                "type": e.is_a(),
                "name": getattr(e, "Name", None),
            }
    return out


def diff(a: dict, b: dict) -> dict:
    a_keys, b_keys = set(a), set(b)
    added = sorted(b_keys - a_keys)
    removed = sorted(a_keys - b_keys)
    changed = []
    for k in a_keys & b_keys:
        if a[k] != b[k]:
            changed.append({"global_id": k, "before": a[k], "after": b[k]})
    return {
        "added": [{"global_id": k, **b[k]} for k in added],
        "removed": [{"global_id": k, **a[k]} for k in removed],
        "changed": changed,
        "summary": {
            "added": len(added),
            "removed": len(removed),
            "changed": len(changed),
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("baseline")
    ap.add_argument("revised")
    ap.add_argument("--output")
    args = ap.parse_args()

    a = index(args.baseline)
    b = index(args.revised)
    result = {"baseline": args.baseline, "revised": args.revised, **diff(a, b)}

    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(payload, encoding="utf-8")
        print(f"Wrote diff → {args.output} ({result['summary']})")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
