"""High-level summary of an IFC file.

Usage:
    python summarize.py <model.ifc> [--output summary.json]
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from _common import open_ifc


def summarize(path: str) -> dict:
    f = open_ifc(path)
    by_type: Counter[str] = Counter(e.is_a() for e in f)

    project = f.by_type("IfcProject")
    sites = f.by_type("IfcSite")
    buildings = f.by_type("IfcBuilding")
    storeys = f.by_type("IfcBuildingStorey")
    spaces = f.by_type("IfcSpace")

    return {
        "source": str(path),
        "schema": f.schema,
        "total_entities": sum(by_type.values()),
        "project": project[0].Name if project else None,
        "site_count": len(sites),
        "building_count": len(buildings),
        "storey_count": len(storeys),
        "space_count": len(spaces),
        "storey_names": [s.Name for s in storeys],
        "top_entity_types": by_type.most_common(20),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("ifc_path")
    ap.add_argument("--output")
    args = ap.parse_args()

    payload = json.dumps(summarize(args.ifc_path), ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(payload, encoding="utf-8")
        print(f"Wrote summary → {args.output}")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
