"""Query property sets (Pset_*) and quantity sets (Qto_*) of IFC entities.

Usage:
    python query_pset.py <model.ifc> <IfcType> [--pset PSET_NAME] [--prop PROP_NAME]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import ifcopenshell.util.element as util

from _common import open_ifc


def query(path: str, ifc_type: str,
          pset_name: str | None, prop_name: str | None) -> list[dict]:
    f = open_ifc(path)
    rows: list[dict] = []
    for ent in f.by_type(ifc_type):
        psets = util.get_psets(ent)
        if pset_name:
            psets = {k: v for k, v in psets.items() if k == pset_name}
        if prop_name:
            psets = {
                k: {p: v for p, v in props.items() if p == prop_name}
                for k, props in psets.items()
            }
            psets = {k: v for k, v in psets.items() if v}
        rows.append({
            "global_id": ent.GlobalId,
            "name": getattr(ent, "Name", None),
            "type": ent.is_a(),
            "psets": psets,
        })
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("ifc_path")
    ap.add_argument("ifc_type")
    ap.add_argument("--pset", help="Limit to one Pset / Qto name")
    ap.add_argument("--prop", help="Limit to one property name")
    ap.add_argument("--output")
    args = ap.parse_args()

    rows = query(args.ifc_path, args.ifc_type, args.pset, args.prop)
    payload = json.dumps(rows, ensure_ascii=False, indent=2, default=str)
    if args.output:
        Path(args.output).write_text(payload, encoding="utf-8")
        print(f"Wrote {len(rows)} record(s) → {args.output}")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
