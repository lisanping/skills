#!/usr/bin/env python3
"""Step 8 v2 — Anchor pack.

Deterministic aggregation of per-slide and per-cohort anchors that the
detection prompts (per-slide and per-cohort) consume verbatim. Generated
once at the start of Step 8 (before any VLM call) so re-running detection
during a fix cycle is reproducible.

Sources:
  - s05-slide-visual-design.json   — narrativeIntent, layoutPattern, etc.
  - s06-slide-content.json         — title + body text per slide
  - s08-zone-metrics.json          — per-slide metrics subset
  - s08-cohort-definitions.json    — cohort comparisonTables

Usage:
  python s08_anchor_pack.py <session_dir>
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
from pathlib import Path
from typing import Any

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

CONTENT_TEXT_LIMIT = 600


def _read_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def _slide_content_text(slide_content: dict) -> str:
    """Concatenate title + slot texts up to CONTENT_TEXT_LIMIT chars."""
    parts: list[str] = []
    title = slide_content.get("title")
    if title:
        parts.append(str(title).strip())
    for slot in slide_content.get("slots", []) or []:
        txt = slot.get("text")
        if txt:
            parts.append(str(txt).strip())
    joined = " · ".join(p for p in parts if p)
    if len(joined) > CONTENT_TEXT_LIMIT:
        joined = joined[: CONTENT_TEXT_LIMIT - 1] + "…"
    return joined


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("session", help="Session directory")
    parser.add_argument("--design", default="s05-slide-visual-design.json")
    parser.add_argument("--content", default="s06-slide-content.json")
    parser.add_argument("--metrics", default="s08-zone-metrics.json")
    parser.add_argument("--cohorts", default="s08-cohort-definitions.json")
    parser.add_argument("--out", default="s08-anchor-pack.json")
    args = parser.parse_args()

    session = Path(args.session).resolve()
    if not session.is_dir():
        print(f"❌ session dir not found: {session}", file=sys.stderr)
        return 2

    design = _read_json(session / args.design)
    content = _read_json(session / args.content)
    metrics = _read_json(session / args.metrics)
    cohorts = _read_json(session / args.cohorts)

    if metrics is None:
        print(f"❌ metrics missing: {session / args.metrics}", file=sys.stderr)
        return 2
    if design is None:
        print(f"❌ design missing: {session / args.design}", file=sys.stderr)
        return 2

    # Index sources by slideId for O(1) lookup.
    design_by_id = {sl.get("taskId"): sl for sl in design.get("slides", [])}
    metrics_by_id = {sl.get("slideId"): sl for sl in metrics.get("slides", [])}
    content_by_id: dict[str, dict] = {}
    if content:
        content_by_id = {sl.get("taskId"): sl for sl in content.get("slides", [])}

    per_slide: dict[str, Any] = {}
    for sid, design_entry in design_by_id.items():
        if not sid:
            continue
        metric_entry = metrics_by_id.get(sid, {})
        content_entry = content_by_id.get(sid, {})
        per_slide[sid] = {
            "slideId": sid,
            "title": design_entry.get("title") or content_entry.get("title"),
            "slideType": design_entry.get("slideType"),
            "narrativeRole": design_entry.get("narrativeRole"),
            "narrativeIntent": design_entry.get("narrativeIntent"),
            "layoutPattern": design_entry.get("layoutPattern"),
            "contentText": _slide_content_text(content_entry) if content_entry else None,
            "metricsSubset": {
                "background": metric_entry.get("background"),
                "zones": metric_entry.get("zones", []),
                "outOfCanvas": metric_entry.get("outOfCanvas", []),
                "placeholderHits": metric_entry.get("placeholderHits", []),
            },
        }

    per_cohort: dict[str, Any] = {}
    if cohorts:
        for c in cohorts.get("cohorts", []):
            cid = c.get("cohortId")
            if not cid:
                continue
            per_cohort[cid] = {
                "cohortId": cid,
                "cohortType": c.get("cohortType"),
                "members": c.get("members", []),
                "rationale": c.get("rationale", ""),
                "sharedSpec": c.get("sharedSpec"),
                "comparisonTable": c.get("comparisonTable", {}),
            }

    payload = {
        "generatedAt": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sourceDesignFile": args.design,
        "sourceMetricsFile": args.metrics,
        "sourceCohortDefinitionsFile": args.cohorts,
        "slideDimensions": metrics.get("slideDimensions"),
        "perSlide": per_slide,
        "perCohort": per_cohort,
    }

    out_path = session / args.out
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"✅ wrote {out_path.relative_to(session)}")
    print(f"   perSlide={len(per_slide)} perCohort={len(per_cohort)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
