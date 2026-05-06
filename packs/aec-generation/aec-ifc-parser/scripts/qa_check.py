"""Run quality checks on an IFC model based on references/qa-checklist.yaml.

Usage:
    python qa_check.py <model.ifc> [--rules qa-checklist.yaml] [--output report.json]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import ifcopenshell.util.element as util
import yaml  # type: ignore

from _common import open_ifc

DEFAULT_RULES = Path(__file__).parent.parent / "references" / "qa-checklist.yaml"


def check(path: str, rules: dict) -> dict:
    f = open_ifc(path)
    issues: list[dict] = []

    schema_cfg = rules.get("schema", {})
    if f.schema not in schema_cfg.get("allowed", []):
        sev = "warning" if f.schema in schema_cfg.get("warn_on", []) else "error"
        issues.append({
            "severity": sev,
            "kind": "schema_unsupported",
            "actual": f.schema,
            "allowed": schema_cfg.get("allowed", []),
        })

    naming = rules.get("naming", {})
    for ifc_type, spec in naming.items():
        pattern = re.compile(spec.get("pattern", ".*"))
        for ent in f.by_type(ifc_type):
            name = getattr(ent, "Name", None) or ""
            if not pattern.match(name):
                issues.append({
                    "severity": rules["severity"].get("naming_violation", "warning"),
                    "kind": "naming_violation",
                    "type": ifc_type,
                    "global_id": ent.GlobalId,
                    "name": name,
                    "expected_pattern": spec.get("pattern"),
                })

    required = rules.get("required_properties", {})
    for ifc_type, pset_map in required.items():
        for ent in f.by_type(ifc_type):
            psets = util.get_psets(ent)
            for pset_name, props in pset_map.items():
                actual_props = psets.get(pset_name, {})
                for p in props:
                    if actual_props.get(p) in (None, ""):
                        issues.append({
                            "severity": rules["severity"].get(
                                "missing_required_property", "error"),
                            "kind": "missing_required_property",
                            "type": ifc_type,
                            "global_id": ent.GlobalId,
                            "pset": pset_name,
                            "property": p,
                        })

    spatial = rules.get("spatial_structure", {})
    if spatial.get("no_orphan_elements"):
        for ent in f.by_type("IfcElement"):
            if util.get_container(ent) is None:
                issues.append({
                    "severity": rules["severity"].get("orphan_element", "error"),
                    "kind": "orphan_element",
                    "type": ent.is_a(),
                    "global_id": ent.GlobalId,
                })

    summary = {
        "source": str(path),
        "schema": f.schema,
        "issue_count": len(issues),
        "errors": sum(1 for i in issues if i["severity"] == "error"),
        "warnings": sum(1 for i in issues if i["severity"] == "warning"),
        "issues": issues,
    }
    return summary


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("ifc_path")
    ap.add_argument("--rules", default=str(DEFAULT_RULES))
    ap.add_argument("--output")
    args = ap.parse_args()

    rules = yaml.safe_load(Path(args.rules).read_text(encoding="utf-8")) or {}
    report = check(args.ifc_path, rules)
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(payload, encoding="utf-8")
        print(f"Wrote QA report → {args.output} (errors={report['errors']}, "
              f"warnings={report['warnings']})")
    else:
        print(payload)
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
