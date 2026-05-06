"""Print the spatial structure tree of an IFC file.

Usage:
    python spatial_tree.py <model.ifc> [--max-depth 6] [--output tree.json]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from _common import open_ifc


def build_node(ent, depth: int, max_depth: int) -> dict:
    node = {
        "type": ent.is_a(),
        "name": getattr(ent, "Name", None) or "(unnamed)",
        "global_id": ent.GlobalId,
        "children": [],
    }
    if depth >= max_depth:
        return node
    for rel in getattr(ent, "IsDecomposedBy", []) or []:
        for child in rel.RelatedObjects:
            node["children"].append(build_node(child, depth + 1, max_depth))
    for rel in getattr(ent, "ContainsElements", []) or []:
        for child in rel.RelatedElements:
            node["children"].append(build_node(child, depth + 1, max_depth))
    return node


def render(node: dict, depth: int = 0, lines: list[str] | None = None) -> list[str]:
    lines = lines if lines is not None else []
    lines.append("  " * depth + f"{node['type']}: {node['name']} [{node['global_id']}]")
    for c in node["children"]:
        render(c, depth + 1, lines)
    return lines


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("ifc_path")
    ap.add_argument("--max-depth", type=int, default=6)
    ap.add_argument("--output", help="Write JSON tree (default: pretty text to stdout)")
    args = ap.parse_args()

    f = open_ifc(args.ifc_path)
    projects = f.by_type("IfcProject")
    if not projects:
        print("No IfcProject found", file=sys.stderr)
        return 1

    trees = [build_node(p, 0, args.max_depth) for p in projects]
    if args.output:
        Path(args.output).write_text(
            json.dumps(trees, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"Wrote tree → {args.output}")
    else:
        for t in trees:
            print("\n".join(render(t)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
