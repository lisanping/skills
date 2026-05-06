#!/usr/bin/env python3
"""Step 8 v2 — Cohort definitions.

Derives slide cohorts (structurally-similar groups) for the per-cohort
VLM detection pass.

Discovery rules (deterministic):

1. **bookends** (semantic-pair): one slide with ``narrativeRole=opening``
   (or ``slideType=cover``) + one with ``narrativeRole=resolution``
   (or ``slideType=closing``). If both exist → cohort.
2. **act-dividers** (role-series): all slides with ``slideType=divider``;
   if ≥ 2 → cohort.
3. **layout:<pattern>** (layout-repetition): group by ``layoutPattern``;
   emit cohort for each group with size ≥ 2.

For each cohort we build a ``comparisonTable`` indexed by ``roleHint``
(only roles present in ≥ 2 members) → slideId → metric snapshot. The
per-cohort VLM prompt consumes this as structured cross-member anchor.

Q3-B layoutPattern normalization is left as an opt-in pluggable hook
(``--normalize`` flag) — for the test sessions inspected so far the
upstream visual-design LLM produces stable names; an LLM call adds
unnecessary cost. When the flag is set, future implementations may
inject a normalization step here.

Usage:
  python s08_cohort_definitions.py <session_dir>
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


# ── Discovery ────────────────────────────────────────────────────────


def discover_bookends(slides: list[dict]) -> list[str] | None:
    """Return [openerId, closerId] when both endpoints exist."""
    opener = None
    closer = None
    for sl in slides:
        if opener is None and (
            sl.get("narrativeRole") == "opening"
            or sl.get("slideType") == "cover"
        ):
            opener = sl.get("taskId")
        if sl.get("narrativeRole") == "resolution" or sl.get("slideType") == "closing":
            # Take the LAST closing slide to handle decks with intermediate
            # "resolution-style" slides (e.g. Q&A before the real close).
            closer = sl.get("taskId")
    if opener and closer and opener != closer:
        return [opener, closer]
    return None


def discover_act_dividers(slides: list[dict]) -> list[str] | None:
    """Return ordered list of divider slide ids when ≥ 2 exist."""
    members = [
        sl["taskId"] for sl in slides if sl.get("slideType") == "divider" and sl.get("taskId")
    ]
    return members if len(members) >= 2 else None


def discover_layout_repetitions(slides: list[dict]) -> dict[str, list[str]]:
    """Return {layoutPattern: [slideIds]} for patterns appearing ≥ 2 times."""
    by_pattern: dict[str, list[str]] = defaultdict(list)
    for sl in slides:
        pat = sl.get("layoutPattern")
        sid = sl.get("taskId")
        if pat and sid:
            by_pattern[pat].append(sid)
    return {p: ids for p, ids in by_pattern.items() if len(ids) >= 2}


# ── Comparison table aggregation ─────────────────────────────────────


_TEXT_SAMPLE_LIMIT = 80


def _zone_to_snapshot(zone: dict) -> dict[str, Any]:
    """Pluck the comparison-relevant fields from a zone metric entry."""
    runs = zone.get("textRuns") or []
    dominant = next((r for r in runs if (r.get("text") or "").strip()), None)
    image = zone.get("image") or {}
    fill = zone.get("fill") or {}
    snapshot: dict[str, Any] = {
        "zoneId": zone.get("zoneId"),
        "shapeType": zone.get("shapeType"),
        "bboxIn": zone.get("bboxIn"),
        "fillColor": fill.get("fillColor"),
        "dominantText": (dominant.get("text") or "")[:_TEXT_SAMPLE_LIMIT] if dominant else None,
        "fontPt": dominant.get("fontPt") if dominant else None,
        "fontFamily": dominant.get("fontFamily") if dominant else None,
        "bold": dominant.get("bold") if dominant else None,
        "color": dominant.get("color") if dominant else None,
        "estimatedRenderedLines": dominant.get("estimatedRenderedLines") if dominant else None,
        "imageAspectDelta": image.get("aspectDelta") if image else None,
    }
    return snapshot


def build_comparison_table(
    member_ids: list[str], metrics: dict
) -> dict[str, dict[str, dict]]:
    """Build {roleHint: {slideId: snapshot}} for roles present in ≥ 2 members.

    A role is included when at least 2 distinct member slides have a zone
    whose roleHint == that role. Roles unique to one member are dropped
    (they cannot be compared).
    """
    # Index zones per slide by roleHint (first occurrence wins; duplicates
    # within a slide are rare and indicate naming ambiguity in s05).
    per_slide: dict[str, dict[str, dict]] = {}
    for sl_metric in metrics.get("slides", []):
        sid = sl_metric.get("slideId")
        if sid not in member_ids:
            continue
        bag: dict[str, dict] = {}
        for z in sl_metric.get("zones", []):
            role = z.get("roleHint")
            if not role:
                continue
            if role not in bag:
                bag[role] = z
        per_slide[sid] = bag

    # Count roles across members.
    role_counts: dict[str, int] = defaultdict(int)
    for sid, bag in per_slide.items():
        for role in bag:
            role_counts[role] += 1

    table: dict[str, dict[str, dict]] = {}
    for role, count in role_counts.items():
        if count < 2:
            continue
        table[role] = {}
        for sid in member_ids:
            zone = per_slide.get(sid, {}).get(role)
            if zone is None:
                continue
            table[role][sid] = _zone_to_snapshot(zone)
    return table


# ── Main ─────────────────────────────────────────────────────────────


def normalize_layout_patterns(slides: list[dict], enable_llm: bool) -> dict[str, str]:
    """Q3-B hook. Returns original → canonical map. Currently identity stub.

    When enable_llm=True a future implementation may invoke an LLM here
    to merge near-duplicate names (e.g. 'image-left-text-right' and
    'image-text-split'). For now: no-op identity, returning {} signals
    "no normalization applied" so downstream can elide the field.
    """
    if not enable_llm:
        return {}
    # TODO Phase 2.1+ : LLM-based normalization. Skipped — see docstring.
    return {}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("session", help="Session directory")
    parser.add_argument(
        "--design",
        default="s05-slide-visual-design.json",
        help="Visual-design JSON filename (default: s05-slide-visual-design.json)",
    )
    parser.add_argument(
        "--metrics",
        default="s08-zone-metrics.json",
        help="Zone-metrics JSON filename (default: s08-zone-metrics.json)",
    )
    parser.add_argument(
        "--out",
        default="s08-cohort-definitions.json",
        help="Output filename (default: s08-cohort-definitions.json)",
    )
    parser.add_argument(
        "--normalize",
        action="store_true",
        help="Enable Q3-B layoutPattern normalization (no-op stub today).",
    )
    args = parser.parse_args()

    session = Path(args.session).resolve()
    if not session.is_dir():
        print(f"❌ session dir not found: {session}", file=sys.stderr)
        return 2

    design_path = session / args.design
    metrics_path = session / args.metrics
    if not design_path.is_file():
        print(f"❌ design JSON not found: {design_path}", file=sys.stderr)
        return 2
    if not metrics_path.is_file():
        print(f"❌ metrics JSON not found: {metrics_path}", file=sys.stderr)
        return 2

    with open(design_path, encoding="utf-8") as f:
        design = json.load(f)
    with open(metrics_path, encoding="utf-8") as f:
        metrics = json.load(f)

    slides = design.get("slides", [])
    if not slides:
        print(f"❌ no slides in {design_path}", file=sys.stderr)
        return 2

    # Apply layoutPattern normalization (currently identity).
    norm_map = normalize_layout_patterns(slides, args.normalize)
    if norm_map:
        for sl in slides:
            pat = sl.get("layoutPattern")
            if pat and pat in norm_map:
                sl["layoutPattern"] = norm_map[pat]

    cohorts: list[dict] = []

    # 1. bookends (semantic-pair).
    be = discover_bookends(slides)
    if be:
        opener_id, closer_id = be
        opener = next((s for s in slides if s.get("taskId") == opener_id), {})
        closer = next((s for s in slides if s.get("taskId") == closer_id), {})
        cohorts.append(
            {
                "cohortId": "bookends",
                "cohortType": "semantic-pair",
                "members": be,
                "rationale": "Opening and closing slides should visually rhyme (titlescale, decoration symmetry, palette).",
                "sharedSpec": None,
                "sourceFields": {
                    "narrativeRole": [opener.get("narrativeRole"), closer.get("narrativeRole")],
                    "slideType": [opener.get("slideType"), closer.get("slideType")],
                },
                "comparisonTable": build_comparison_table(be, metrics),
            }
        )

    # 2. act-dividers (role-series).
    div_members = discover_act_dividers(slides)
    if div_members:
        # Use first divider's layoutPattern as shared anchor.
        first = next(s for s in slides if s.get("taskId") == div_members[0])
        cohorts.append(
            {
                "cohortId": "act-dividers",
                "cohortType": "role-series",
                "members": div_members,
                "rationale": (
                    f"All {len(div_members)} section-break slides share slideType=divider — "
                    "must keep visual consistency across the act numbers and titles."
                ),
                "sharedSpec": {
                    "slideType": "divider",
                    "layoutPattern": first.get("layoutPattern"),
                },
                "sourceFields": {"slideType": "divider"},
                "comparisonTable": build_comparison_table(div_members, metrics),
            }
        )

    # 3. layout-repetition.
    layout_groups = discover_layout_repetitions(slides)
    for pattern, members in sorted(layout_groups.items()):
        # Skip the act-divider pattern if it duplicates the role-series cohort.
        if div_members and set(members) == set(div_members):
            continue
        cohorts.append(
            {
                "cohortId": f"layout:{pattern}",
                "cohortType": "layout-repetition",
                "members": members,
                "rationale": (
                    f"Same layoutPattern '{pattern}' appears on {len(members)} slides — "
                    "members should keep proportional and typographic consistency."
                ),
                "sharedSpec": {"layoutPattern": pattern},
                "sourceFields": {"layoutPattern": pattern},
                "comparisonTable": build_comparison_table(members, metrics),
            }
        )

    payload: dict[str, Any] = {
        "generatedAt": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sourceDesignFile": args.design,
        "sourceMetricsFile": args.metrics,
        "cohorts": cohorts,
    }
    if norm_map:
        payload["layoutPatternNormalization"] = norm_map

    out_path = session / args.out
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"✅ wrote {out_path.relative_to(session)}")
    print(f"   cohorts={len(cohorts)}")
    for c in cohorts:
        n_roles = len(c.get("comparisonTable", {}))
        print(
            f"   - {c['cohortId']:42s} type={c['cohortType']:18s} members={len(c['members'])} comparedRoles={n_roles}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
