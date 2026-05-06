"""Check DXF layer compliance against a YAML standard.

Usage:
    python check_layers.py <file_or_dir> [--standard layer-standards.yaml]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import yaml  # type: ignore

from _common import iter_dxf_files, open_dxf

DEFAULT_STANDARD = Path(__file__).parent.parent / "references" / "layer-standards.yaml"


def load_standard(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def check_one(dxf_path: Path, std: dict) -> dict:
    doc = open_dxf(dxf_path)
    actual = {layer.dxf.name: layer for layer in doc.layers}

    required = {item["name"]: item for item in std.get("required_layers", [])}
    forbidden = set(std.get("forbidden_layers", []))
    naming_patterns = [re.compile(p) for p in std.get("naming_patterns", [])]
    color_strict = std.get("color_strict", False)

    issues: list[dict] = []

    for name, spec in required.items():
        if name not in actual:
            issues.append({
                "severity": "error",
                "kind": "missing_required_layer",
                "layer": name,
                "expected": spec,
            })
            continue
        layer = actual[name]
        exp_color = spec.get("color")
        exp_lt = spec.get("linetype")
        if exp_color is not None and layer.dxf.color != exp_color:
            issues.append({
                "severity": "error" if color_strict else "warning",
                "kind": "color_mismatch",
                "layer": name,
                "expected_color": exp_color,
                "actual_color": layer.dxf.color,
            })
        if exp_lt and layer.dxf.linetype.upper() != exp_lt.upper():
            issues.append({
                "severity": "warning",
                "kind": "linetype_mismatch",
                "layer": name,
                "expected_linetype": exp_lt,
                "actual_linetype": layer.dxf.linetype,
            })

    for name in actual:
        if name in forbidden:
            issues.append({
                "severity": "error",
                "kind": "forbidden_layer",
                "layer": name,
            })
        if naming_patterns and name not in required and name != "0":
            if not any(p.match(name) for p in naming_patterns):
                issues.append({
                    "severity": "warning",
                    "kind": "naming_violation",
                    "layer": name,
                })

    return {
        "source": str(dxf_path),
        "layer_count": len(actual),
        "issue_count": len(issues),
        "errors": sum(1 for i in issues if i["severity"] == "error"),
        "warnings": sum(1 for i in issues if i["severity"] == "warning"),
        "issues": issues,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("target", help="DXF file or directory")
    ap.add_argument("--standard", default=str(DEFAULT_STANDARD))
    ap.add_argument("--output", help="Write JSON to this file (default: stdout)")
    args = ap.parse_args()

    std = load_standard(Path(args.standard))
    reports = [check_one(p, std) for p in iter_dxf_files(args.target)]

    payload = json.dumps(reports, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(payload, encoding="utf-8")
        print(f"Checked {len(reports)} file(s) → {args.output}")
    else:
        print(payload)
    total_err = sum(r["errors"] for r in reports)
    return 1 if total_err else 0


if __name__ == "__main__":
    sys.exit(main())
