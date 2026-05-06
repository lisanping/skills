"""Quantity takeoff — aggregate Qto values across an IFC model.

Usage:
    python quantity_takeoff.py <model.ifc> [--by storey|type|both]
                                            [--types IfcWall IfcSlab ...]

By default reports volume/area/length per IFC type and per storey.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import ifcopenshell.util.element as util

from _common import open_ifc

QUANTITY_KEYS = ("NetVolume", "GrossVolume", "NetArea", "GrossArea",
                 "NetSideArea", "GrossSideArea", "NetFloorArea", "GrossFloorArea",
                 "Length", "Width", "Height")

DEFAULT_TYPES = ["IfcWall", "IfcSlab", "IfcColumn", "IfcBeam",
                 "IfcDoor", "IfcWindow", "IfcSpace"]


def collect_qto(ent) -> dict[str, float]:
    out: dict[str, float] = {}
    psets = util.get_psets(ent, qtos_only=True)
    for _, props in psets.items():
        for k, v in props.items():
            if k in QUANTITY_KEYS and isinstance(v, (int, float)):
                out[k] = out.get(k, 0.0) + float(v)
    return out


def takeoff(path: str, types: list[str], group_by: str) -> dict:
    f = open_ifc(path)
    by_type: dict[str, dict] = defaultdict(lambda: {"count": 0, "qto": defaultdict(float)})
    by_storey: dict[str, dict] = defaultdict(
        lambda: defaultdict(lambda: {"count": 0, "qto": defaultdict(float)})
    )

    for t in types:
        for ent in f.by_type(t):
            qto = collect_qto(ent)
            by_type[t]["count"] += 1
            for k, v in qto.items():
                by_type[t]["qto"][k] += v

            container = util.get_container(ent)
            sname = container.Name if container is not None else "<unassigned>"
            by_storey[sname][t]["count"] += 1
            for k, v in qto.items():
                by_storey[sname][t]["qto"][k] += v

    def _round(d: dict) -> dict:
        return {k: round(v, 3) for k, v in d.items()}

    by_type_out = {
        t: {"count": data["count"], "totals": _round(data["qto"])}
        for t, data in by_type.items()
    }
    by_storey_out = {
        s: {
            t: {"count": d["count"], "totals": _round(d["qto"])}
            for t, d in storey_data.items()
        }
        for s, storey_data in by_storey.items()
    }

    payload: dict = {"source": str(path)}
    if group_by in ("type", "both"):
        payload["by_type"] = by_type_out
    if group_by in ("storey", "both"):
        payload["by_storey"] = by_storey_out
    return payload


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("ifc_path")
    ap.add_argument("--by", choices=["type", "storey", "both"], default="both")
    ap.add_argument("--types", nargs="+", default=DEFAULT_TYPES)
    ap.add_argument("--output")
    args = ap.parse_args()

    payload = takeoff(args.ifc_path, args.types, args.by)
    out = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(out, encoding="utf-8")
        print(f"Wrote takeoff → {args.output}")
    else:
        print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
