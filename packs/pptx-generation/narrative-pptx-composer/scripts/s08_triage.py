#!/usr/bin/env python3
"""Step 8 — Triage (deterministic, no LLM).

Reads dimension grades + anomalies, assigns priorities, filters
low-confidence noise, marks conflicts.

Input:
  - s08-perslide-grades.json  (mode=perslide)
  - s08-cohort-grades.json    (mode=cohort)

Output:
  - s08-perslide-triaged.json  or  s08-cohort-triaged.json

Usage:
  python s08_triage.py <session_dir> --mode perslide
  python s08_triage.py <session_dir> --mode cohort
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

MIN_EVIDENCE_CHARS = 30

VAGUE_TOKENS = ("maybe", "possibly", "feels", "could be", "perhaps", "looks like it might")


def is_vague(evidence: str) -> bool:
    if not evidence or len(evidence) < MIN_EVIDENCE_CHARS:
        return True
    low = evidence.lower()
    return sum(1 for t in VAGUE_TOKENS if t in low) >= 2 and len(evidence) < 80


def anomaly_priority(severity: str, confidence: str) -> str:
    """Shared priority logic for anomalies (same for perslide and cohort)."""
    if severity == "critical" and confidence != "low":
        return "P1"
    if severity == "critical" and confidence == "low":
        return "P2"
    if severity == "minor" and confidence == "high":
        return "P2"
    return "P3"


def triage_perslide(data: dict) -> dict:
    """Process per-slide grades into triaged output."""
    slides = data.get("slides", [])
    items: list[dict] = []
    dropped: list[dict] = []

    for slide in slides:
        sid = slide["slideId"]
        dims = slide.get("dimensions", {})
        anomalies = slide.get("anomalies", [])

        # Grade dimensions → priority
        for dim_name, dim_val in dims.items():
            grade = dim_val.get("grade", "pass")
            if grade in ("fail", "marginal"):
                priority = "P0" if grade == "fail" else "P2"
                items.append({
                    "slideId": sid,
                    "type": "dimension",
                    "trigger": dim_name,
                    "grade": grade,
                    "evidence": dim_val.get("evidence", ""),
                    "priority": priority,
                })

        # Anomalies → filter + priority
        for i, anom in enumerate(anomalies):
            conf = anom.get("confidence", "low")
            ev = anom.get("evidence", "")
            if conf == "low" and is_vague(ev):
                dropped.append({
                    "slideId": sid,
                    "index": i,
                    "what": anom.get("what", ""),
                    "reason": "confidence=low + vague evidence",
                })
                continue
            pri = anomaly_priority(anom.get("severity", "minor"), conf)
            item = {
                "slideId": sid,
                "type": "anomaly",
                "trigger": anom.get("what", ""),
                "severity": anom.get("severity"),
                "confidence": conf,
                "evidence": ev,
                "fixDirection": anom.get("fixDirection", ""),
                "suggestedDimension": anom.get("suggestedDimension"),
                "priority": pri,
            }
            # Conflict detection: same slide + contradictory directions
            items.append(item)

    # Conflict marking
    by_slide: dict[str, list[dict]] = defaultdict(list)
    for item in items:
        if item["type"] == "anomaly":
            by_slide[item["slideId"]].append(item)
    for sid, group in by_slide.items():
        if len(group) < 2:
            continue
        dirs = [(it.get("fixDirection") or "").lower() for it in group]
        has_shrink = any("shrink" in d or "smaller" in d or "缩" in d for d in dirs)
        has_grow = any("enlarge" in d or "bigger" in d or "expand" in d or "增" in d for d in dirs)
        if has_shrink and has_grow:
            for it in group:
                it["conflict"] = True

    return _build_output(items, dropped, "perslide")


def triage_cohort(data: list[dict]) -> dict:
    """Process per-cohort grades into triaged output."""
    items: list[dict] = []
    dropped: list[dict] = []

    for cohort in data:
        cid = cohort.get("cohortId", "")
        dims = cohort.get("dimensions", {})
        anomalies = cohort.get("anomalies", [])

        for dim_name, dim_val in dims.items():
            grade = dim_val.get("grade", "pass")
            if grade in ("fail", "marginal"):
                priority = "P0" if grade == "fail" else "P2"
                items.append({
                    "cohortId": cid,
                    "type": "dimension",
                    "trigger": dim_name,
                    "grade": grade,
                    "evidence": dim_val.get("evidence", ""),
                    "priority": priority,
                })

        for i, anom in enumerate(anomalies):
            conf = anom.get("confidence", "low")
            ev = anom.get("evidence", "")
            if conf == "low" and is_vague(ev):
                dropped.append({
                    "cohortId": cid,
                    "index": i,
                    "what": anom.get("what", ""),
                    "reason": "confidence=low + vague evidence",
                })
                continue
            pri = anomaly_priority(anom.get("severity", "minor"), conf)
            items.append({
                "cohortId": cid,
                "type": "anomaly",
                "trigger": anom.get("what", ""),
                "severity": anom.get("severity"),
                "confidence": conf,
                "evidence": ev,
                "fixDirection": anom.get("fixDirection", ""),
                "affectedMembers": anom.get("affectedMembers", []),
                "suggestedDimension": anom.get("suggestedDimension"),
                "priority": pri,
            })

    return _build_output(items, dropped, "cohort")


def _build_output(items: list[dict], dropped: list[dict], mode: str) -> dict:
    by_pri: dict[str, int] = defaultdict(int)
    for it in items:
        by_pri[it.get("priority", "?")] += 1

    return {
        "generatedAt": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "mode": mode,
        "items": items,
        "dropped": dropped,
        "summary": {
            "total": len(items),
            "byPriority": dict(by_pri),
            "droppedCount": len(dropped),
            "conflicts": sum(1 for it in items if it.get("conflict")),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("session", help="Session directory")
    parser.add_argument("--mode", choices=["cohort", "perslide"], required=True)
    args = parser.parse_args()

    session = Path(args.session).resolve()
    if not session.is_dir():
        print(f"❌ session dir not found: {session}", file=sys.stderr)
        return 2

    if args.mode == "perslide":
        in_path = session / "s08-perslide-grades.json"
        out_path = session / "s08-perslide-triaged.json"
        if not in_path.is_file():
            print(f"❌ input not found: {in_path}", file=sys.stderr)
            return 2
        with open(in_path, encoding="utf-8") as f:
            data = json.load(f)
        result = triage_perslide(data)
    else:
        in_path = session / "s08-cohort-grades.json"
        out_path = session / "s08-cohort-triaged.json"
        if not in_path.is_file():
            print(f"❌ input not found: {in_path}", file=sys.stderr)
            return 2
        with open(in_path, encoding="utf-8") as f:
            data = json.load(f)
        # cohort grades file is an array of cohort objects
        if isinstance(data, dict):
            data = data.get("cohorts", [data])
        result = triage_cohort(data)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    s = result["summary"]
    print(f"✅ wrote {out_path.name}")
    print(f"   total={s['total']}  dropped={s['droppedCount']}  conflicts={s['conflicts']}")
    print(f"   byPriority={s['byPriority']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
