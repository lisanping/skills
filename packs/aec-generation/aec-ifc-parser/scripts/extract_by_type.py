"""Extract all entities of a given IFC type with basic identifying info.

Usage:
    python extract_by_type.py <model.ifc> <IfcType> [--storey NAME]
                              [--include-subtypes/--no-include-subtypes]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import ifcopenshell.util.element as util

from _common import open_ifc


def extract(path: str, ifc_type: str, storey: str | None,
            include_subtypes: bool) -> list[dict]:
    f = open_ifc(path)
    rows: list[dict] = []
    for ent in f.by_type(ifc_type, include_subtypes=include_subtypes):
        container = util.get_container(ent)
        if storey and (container is None or container.Name != storey):
            continue
        rows.append({
            "global_id": ent.GlobalId,
            "name": getattr(ent, "Name", None),
            "type": ent.is_a(),
            "tag": getattr(ent, "Tag", None),
            "storey": container.Name if container is not None else None,
        })
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("ifc_path")
    ap.add_argument("ifc_type")
    ap.add_argument("--storey")
    sub = ap.add_mutually_exclusive_group()
    sub.add_argument("--include-subtypes", dest="subtypes", action="store_true", default=True)
    sub.add_argument("--no-include-subtypes", dest="subtypes", action="store_false")
    ap.add_argument("--output")
    args = ap.parse_args()

    rows = extract(args.ifc_path, args.ifc_type, args.storey, args.subtypes)
    payload = json.dumps(rows, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(payload, encoding="utf-8")
        print(f"Wrote {len(rows)} {args.ifc_type} → {args.output}")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
