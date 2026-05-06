"""Geometric summary of a DXF file: entity counts, bbox, layer distribution.

Usage:
    python geom_summary.py <file_or_dir> [--output summary.json]
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from ezdxf import bbox

from _common import iter_dxf_files, open_dxf


def summarize_one(path: Path) -> dict:
    doc = open_dxf(path)
    msp = doc.modelspace()
    types: Counter[str] = Counter()
    by_layer: Counter[str] = Counter()
    for ent in msp:
        types[ent.dxftype()] += 1
        by_layer[ent.dxf.layer] += 1

    try:
        ext = bbox.extents(msp)
        bbox_payload: dict | None = {
            "min": [round(ext.extmin.x, 3), round(ext.extmin.y, 3), round(ext.extmin.z, 3)],
            "max": [round(ext.extmax.x, 3), round(ext.extmax.y, 3), round(ext.extmax.z, 3)],
            "size": [
                round(ext.extmax.x - ext.extmin.x, 3),
                round(ext.extmax.y - ext.extmin.y, 3),
                round(ext.extmax.z - ext.extmin.z, 3),
            ],
        }
    except Exception:  # noqa: BLE001 - bbox can fail on weird entities
        bbox_payload = None

    return {
        "source": str(path),
        "dxf_version": doc.dxfversion,
        "units_code": doc.header.get("$INSUNITS", 0),
        "layer_count": len(doc.layers),
        "entity_count": sum(types.values()),
        "by_type": dict(types.most_common()),
        "by_layer": dict(by_layer.most_common()),
        "bbox": bbox_payload,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("target")
    ap.add_argument("--output")
    args = ap.parse_args()

    reports = [summarize_one(p) for p in iter_dxf_files(args.target)]
    payload = json.dumps(reports, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(payload, encoding="utf-8")
        print(f"Summarized {len(reports)} file(s) → {args.output}")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
