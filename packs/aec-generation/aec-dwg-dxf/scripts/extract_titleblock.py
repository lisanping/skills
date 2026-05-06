"""Extract titleblock metadata from a DXF file.

Usage:
    python extract_titleblock.py <file.dxf> [--config titleblock-config.yaml]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover
    yaml = None

from _common import iter_dxf_files, matches_any, normalize_tag, open_dxf

DEFAULT_BLOCK_NAME_PATTERNS = [
    r"^TITLEBLOCK.*",
    r"^TITLE.*",
    r"^A[0-4]_?(标题栏|TITLE).*",
    r"^图签.*",
    r"^标题栏.*",
    r"^BORDER.*",
    r"^SHEET_BORDER.*",
    r"^M_TitleBlock.*",
]

DEFAULT_ATTRIB_FIELD_MAP = {
    "DWG_NO": "drawing_number",
    "SHEET_NO": "drawing_number",
    "图号": "drawing_number",
    "DWG_NAME": "drawing_title",
    "SHEET_NAME": "drawing_title",
    "图名": "drawing_title",
    "REV": "revision",
    "REVISION": "revision",
    "版次": "revision",
    "SCALE": "scale",
    "比例": "scale",
    "DATE": "date",
    "ISSUE_DATE": "date",
    "日期": "date",
    "出图日期": "date",
    "PROJECT": "project_name",
    "PROJECT_NAME": "project_name",
    "项目": "project_name",
    "PROJ_NO": "project_number",
    "项目编号": "project_number",
    "DESIGNER": "designer",
    "设计": "designer",
    "CHECKER": "checker",
    "校对": "checker",
    "APPROVER": "approver",
    "审核": "approver",
    "审定": "approver",
    "PHASE": "phase",
    "设计阶段": "phase",
}


def load_config(path: str | None) -> tuple[list[re.Pattern[str]], dict[str, str]]:
    patterns = list(DEFAULT_BLOCK_NAME_PATTERNS)
    field_map = dict(DEFAULT_ATTRIB_FIELD_MAP)
    if path and yaml is not None:
        cfg_path = Path(path)
        if cfg_path.exists():
            cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
            patterns = list(cfg.get("block_name_patterns", patterns))
            extra = cfg.get("attrib_field_map", {}) or {}
            for k, v in extra.items():
                field_map[normalize_tag(k)] = v
    compiled = [re.compile(p, re.IGNORECASE) for p in patterns]
    return compiled, field_map


def extract_one(dxf_path: Path, patterns, field_map) -> list[dict]:
    """Return all titleblocks found in a DXF file."""
    doc = open_dxf(dxf_path)
    msp = doc.modelspace()
    results: list[dict] = []
    for insert in msp.query("INSERT"):
        if not matches_any(insert.dxf.name, patterns):
            continue
        record: dict = {
            "source": str(dxf_path),
            "block_name": insert.dxf.name,
            "insert_handle": insert.dxf.handle,
        }
        for attrib in insert.attribs:
            tag = normalize_tag(attrib.dxf.tag)
            field = field_map.get(tag)
            if field:
                record.setdefault(field, attrib.dxf.text or "")
            else:
                record.setdefault(f"_raw_{tag}", attrib.dxf.text or "")
        results.append(record)
    if not results:
        results.append({"source": str(dxf_path), "error": "no titleblock found"})
    return results


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("target", help="DXF file or directory")
    ap.add_argument("--config", help="Optional titleblock-config.yaml")
    ap.add_argument("--output", help="Write JSON to this file (default: stdout)")
    args = ap.parse_args()

    patterns, field_map = load_config(args.config)
    all_records: list[dict] = []
    for p in iter_dxf_files(args.target):
        all_records.extend(extract_one(p, patterns, field_map))

    payload = json.dumps(all_records, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(payload, encoding="utf-8")
        print(f"Wrote {len(all_records)} record(s) → {args.output}")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
