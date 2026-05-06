"""Generate a downstream-facing composer digest from a completed template-profile.json.

The digest is a simplified, decision-focused view of the profile, intended
for consumption by branded-pptx-generator and other downstream tools.
It extracts layout selection hints, style reference recommendations,
and generation strategy guidance into a compact JSON file.

Usage:
    python generate_composer_digest.py profile.json -o composer-digest.json
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

VERSION = "1.0.0"

# Strategy selection thresholds.
_STRATEGY_THRESHOLDS = {
    "clone_ratio": 0.6,     # clone candidates / classified >= this -> clone
    "min_classified": 3,    # need at least this many for a confident recommendation
}

# Use-case inference rules: each group is checked independently (additive tags).
# Format: (keywords_to_match, tags_to_emit)
_USE_CASE_RULES = [
    (["agenda", "numbered list", "outline"],       ["agenda", "outline"]),
    (["kpi", "stat", "metric", "indicator"],       ["kpi", "metrics"]),
    (["timeline", "milestone", "roadmap"],         ["timeline", "roadmap"]),
    (["table", "grid", "matrix"],                  ["table", "comparison"]),
    (["quote", "testimonial", "callout"],          ["quote", "callout"]),
    (["image", "photo", "visual", "picture"],      ["image-layout", "photo-stories"]),
    (["chart", "graph", "data viz", "diagram"],    ["data-viz", "charts"]),
]


def generate_digest(profile: dict[str, Any]) -> dict[str, Any]:
    """Generate a downstream-facing digest from a profile."""

    # Extract basic stats
    layouts = profile.get("layouts", [])
    samples = profile.get("sample_slide_catalog", []) or []
    # Exclude guide-only slides from sample analysis
    non_guide_samples = [
        s for s in samples if s.get("role") not in ("guide",)
    ]
    samples_with_content = [s for s in non_guide_samples if s.get("has_content")]
    classified = [s for s in samples_with_content if s.get("layoutRelationship")]

    # Count relationships
    rel_counts = {}
    for s in classified:
        rel = s.get("layoutRelationship")
        if rel:
            rel_counts[rel] = rel_counts.get(rel, 0) + 1

    style_counts = {}
    for s in classified:
        style = s.get("styleSourceType")
        if style:
            style_counts[style] = style_counts.get(style, 0) + 1

    suit_counts = {}
    for s in classified:
        suit = s.get("styleRefSuitability")
        if suit:
            suit_counts[suit] = suit_counts.get(suit, 0) + 1

    clone_count = sum(1 for s in classified if s.get("cloneCandidate") is True)

    # Layout usage analysis
    layout_usage = {}
    for s in classified:
        k = s.get("layout_index") or s.get("layout_file")
        if k is None:
            continue
        k_str = str(k)
        if k_str not in layout_usage:
            layout_usage[k_str] = {
                "mappedLayout": k,
                "usageCount": 0,
                "faithful": 0,
                "variant": 0,
                "detached": 0,
            }
        bucket = layout_usage[k_str]
        bucket["usageCount"] += 1
        rel = s.get("layoutRelationship")
        if rel in ("faithful", "variant", "detached"):
            bucket[rel] += 1

    # Sort by usage
    top_layouts = sorted(
        [
            {
                "mappedLayout": v["mappedLayout"],
                "usageCount": v["usageCount"],
                "distributionByRelationship": {
                    "faithful": v["faithful"],
                    "variant": v["variant"],
                    "detached": v["detached"],
                },
                "behavior": "detached-dominant"
                if v["detached"] > 0
                and v["detached"] >= v["variant"] + v["faithful"]
                else "mixed",
                "recommendation": (
                    "Canvas-based layout; prioritize styleRef-driven generation"
                    if v["detached"] >= v["variant"] + v["faithful"]
                    else "Mixed behavior; assess per use case"
                ),
            }
            for v in layout_usage.values()
        ],
        key=lambda x: x["usageCount"],
        reverse=True,
    )

    # High suitability style references
    high_suit = [
        {
            "slideFile": s.get("slide_file"),
            "title": s.get("title", "(untitled)"),
            "contentPattern": s.get("contentPattern", ""),
            "patternDescription": s.get("patternDescription"),
            "layoutIndex": s.get("layout_index"),
            "complexity": "simple"
            if len(s.get("complexElements", [])) == 0
            else "moderate"
            if len(s.get("complexElements", [])) <= 2
            else "complex",
            "cloneCandidate": s.get("cloneCandidate", False),
            "recommendedFor": _infer_use_cases(s),
        }
        for s in classified
        if s.get("styleRefSuitability") == "high"
    ]

    # Low suitability (avoid as default)
    low_suit = [
        {
            "slideFile": s.get("slide_file"),
            "title": s.get("title", "(untitled)"),
            "reason": _summarize_low_suitability(s),
        }
        for s in classified
        if s.get("styleRefSuitability") == "low"
    ]

    # Design language summary
    dl = profile.get("design_language") or {}
    motifs = dl.get("visual_motifs", [])

    # --- Guide slide rules integration ---
    template_guide = profile.get("template_guide") or {}
    guide_slides = template_guide.get("slides", [])
    guide_rules_by_type = template_guide.get("byType", {})

    # Merge guide-explicit typography/color directives into designDirectives
    guide_design_directives: dict[str, Any] = {}
    guide_typography_rules = guide_rules_by_type.get("typography") or []
    guide_color_rules = guide_rules_by_type.get("colorUsage") or []

    if guide_typography_rules:
        guide_design_directives["typographyRules"] = [
            {
                "applies_to": r.get("applies_to"),
                "constraint": r.get("constraint"),
                "rawQuote": r.get("rawQuote"),
                "provenance": "guide_slide_explicit",
            }
            for r in guide_typography_rules
        ]

    if guide_color_rules:
        guide_design_directives["colorRules"] = [
            {
                "applies_to": r.get("applies_to"),
                "constraint": r.get("constraint"),
                "rawQuote": r.get("rawQuote"),
                "provenance": "guide_slide_explicit",
            }
            for r in guide_color_rules
        ]

    # Build guardrails from guide rules (donts, spacing, layout usage, etc.)
    guide_guardrails = []
    for rule_kind in ("donts", "spacing", "layoutUsage", "logoUsage", "imagery", "iconography", "elementUsage", "general"):
        rules = guide_rules_by_type.get(rule_kind) or []
        for r in rules:
            severity = "hard" if rule_kind == "donts" else "soft"
            guide_guardrails.append({
                "rule": r.get("rawQuote", ""),
                "applies_to": r.get("applies_to", ""),
                "ruleKind": rule_kind,
                "severity": severity,
                "source": "guide_slide",
                "sourceSlide": r.get("sourceSlide"),
                "confidence": r.get("confidence", 0),
            })

    # Build layout usage constraints from guide rules
    layout_usage_constraints: dict[str, list[str]] = {}
    for r in guide_rules_by_type.get("layoutUsage") or []:
        applies_to = r.get("applies_to", "")
        raw = r.get("rawQuote", "")
        if applies_to:
            layout_usage_constraints.setdefault(applies_to, []).append(raw)

    # Strategy policy
    t = _STRATEGY_THRESHOLDS
    clone_ratio = clone_count / len(classified) if classified else 0
    confident = len(classified) >= t["min_classified"]
    default_strategy = (
        "clone" if clone_ratio >= t["clone_ratio"]
        else "spec-composed"
    )

    digest = {
        "meta": {
            "profileVersion": profile.get("meta", {}).get("extractor_version", "unknown"),
            "digestVersion": VERSION,
            "generatedAt": _get_iso_timestamp(),
        },
        "template": {
            "name": _extract_template_name(profile),
            "layoutsTotal": len(layouts),
            "sampleSlidesTotal": len(samples),
            "sampleSlidesWithContent": len(samples_with_content),
            "guideSlidesIdentified": len(guide_slides),
        },
        "profileHealth": {
            "classificationCoverage": "{}/{}".format(
                len(classified), len(samples_with_content)
            ),
            "gapsCount": len(profile.get("gaps", {}).get("missing_from_potx", [])),
        },
        "designDirectives": {
            "whitespaceRhythm": dl.get("whitespace_rhythm") or "unspecified",
            "colorUsage": dl.get("style_tone") or "unspecified",
            "visualHierarchyMethod": dl.get("visual_hierarchy_method") or "unspecified",
            "componentStylePattern": dl.get("component_style_pattern") or "unspecified",
            "coverVsContentContrast": dl.get("cover_vs_content_contrast") or "unspecified",
            "motifsPriority": motifs,
            "provenance": "vlm_inferred",
            # Guide-explicit rules override/supplement VLM-inferred directives
            **({
                "guideExplicitOverrides": guide_design_directives,
                "guideOverrideProvenance": "guide_slide_explicit",
            } if guide_design_directives else {}),
        },
        "layoutBehaviorSummary": {
            "relationshipDistribution": rel_counts,
            "styleSourceTypeDistribution": style_counts,
            "implicationForComposer": _interpret_distribution(rel_counts),
        },
        "preferredLayoutHints": top_layouts[:5],
        "styleRefCandidates": {
            "highSuitability": high_suit,
            "lowSuitabilityAvoidAsDefault": low_suit,
        },
        "strategyPolicy": {
            "defaultStrategy": default_strategy,
            "cloneCandidateRatio": "{}/{}".format(clone_count, len(classified)),
            "confidence": "high" if confident else "low",
            "whenToCloneAndEdit": [
                "Target slide closely matches a high-suitability styleRef pattern",
                "Content structure aligns with sample element slots (title + fixed blocks)",
            ],
            "whenToUseGenerate": [
                "Target slide requires detached canvas treatment with custom rearrangement",
                "Target slide needs to fuse styles from multiple samples",
            ],
        },
        "guardrails": [
            {"rule": r["rule"], "severity": r["severity"], "source": "vlm_inferred"}
            for r in (dl.get("vlm_guardrails") or [])
        ] + guide_guardrails,
        **({
            "guideSlidesSummary": {
                "slidesIdentified": len(guide_slides),
                "rulesExtracted": template_guide.get("rulesExtracted", 0),
                "ruleKindsCovered": [
                    k for k, v in guide_rules_by_type.items() if v
                ],
            },
            "layoutUsageConstraints": layout_usage_constraints,
        } if guide_slides else {}),
    }

    # --- Aesthetic principles projection ---
    ap = profile.get("aesthetic_principles")
    if ap and isinstance(ap, dict):
        cs = ap.get("compositionSystem") or {}
        col = ap.get("colorSemantics") or {}
        typo = ap.get("typographicSystem") or {}
        sg = ap.get("shapeGrammar") or {}
        pb = col.get("paletteBalance") or {}

        digest["aestheticPrinciples"] = {
            "patternRecipes": ap.get("patternRecipes", []),
            "compositionSummary": {
                "alignmentAnchors": cs.get("alignmentAnchors"),
                "marginStrategy": cs.get("marginStrategy"),
                "symmetryPreference": cs.get("symmetryPreference"),
            },
            "colorSummary": {
                "roleAssignment": col.get("roleAssignment", []),
                "colorEmphasisProgression": col.get("colorEmphasisProgression"),
                "paletteBalanceGuideline": pb.get("balanceGuideline"),
            },
            "typographySummary": {
                "scaleStops": typo.get("scaleStops", []),
                "emphasisMechanism": typo.get("emphasisMechanism"),
                "textDensityGuideline": typo.get("textDensityGuideline"),
            },
            "shapeSummary": {
                "primitiveVocabulary": sg.get("primitiveVocabulary", []),
                "compositionRules": sg.get("compositionRules"),
                "scalingBehavior": sg.get("scalingBehavior"),
            },
        }

    return digest


def _extract_template_name(profile: dict[str, Any]) -> str:
    """Extract template name from profile metadata."""
    meta = profile.get("meta", {})
    source = meta.get("source_file", "unknown")
    # Extract basename without extension
    import os

    return os.path.splitext(os.path.basename(source))[0]


def _infer_use_cases(slide: dict[str, Any]) -> list[str]:
    """Infer recommended use cases from slide contentPattern. Tags are additive."""
    pattern = slide.get("contentPattern", "").lower()
    tags = []
    for keywords, labels in _USE_CASE_RULES:
        if any(kw in pattern for kw in keywords):
            tags.extend(labels)
    # Deduplicate while preserving order
    seen: set[str] = set()
    tags = [t for t in tags if not (t in seen or seen.add(t))]
    return tags if tags else ["general-content"]


def _summarize_low_suitability(slide: dict[str, Any]) -> str:
    """Summarize why a slide has low suitability."""
    complex_elems = slide.get("complexElements", [])
    rel = slide.get("layoutRelationship")

    if len(complex_elems) >= 2:
        return "Complex multi-element composition ({}); difficult to abstract as reusable".format(
            ", ".join(complex_elems[:2])
        )
    elif rel == "detached" and len(complex_elems) >= 1:
        return "Specialized custom diagram ({}) with high semantic coupling".format(
            complex_elems[0]
        )
    else:
        return "Highly specific design; limited generalization potential"


def _interpret_distribution(rel_counts: dict[str, int]) -> str:
    """Interpret the relationship distribution for composer implications."""
    total = sum(rel_counts.values())
    if total == 0:
        return "No samples classified; use default strategy"

    detached_pct = rel_counts.get("detached", 0) / total * 100

    if detached_pct >= 0.7:
        return "Template uses primarily detached/canvas-based samples; prioritize spec-composed strategy with styleRef constraints, avoid assuming layout defaults"
    elif detached_pct >= 0.4:
        return "Mixed sample behavior; assess each slide target; consider adaptive strategy selection"
    else:
        return "Template uses primarily faithful/variant layouts; layout defaults can be leveraged; clone strategy may be effective"


def _get_iso_timestamp() -> str:
    """Get current ISO timestamp."""
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def main():
    parser = argparse.ArgumentParser(
        description="Generate a downstream-facing composer digest from a template profile."
    )
    parser.add_argument("profile", help="Path to template-profile.json")
    parser.add_argument(
        "-o", "--output", help="Output file path (default: composer-digest.json)"
    )

    args = parser.parse_args()

    # Load profile
    try:
        with open(args.profile, "r", encoding="utf-8") as f:
            profile = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error loading profile: {e}", file=sys.stderr)
        sys.exit(1)

    # Generate digest
    digest = generate_digest(profile)

    # Determine output path
    if args.output:
        output_path = Path(args.output)
    else:
        # Default: same directory as profile, with .digest.json suffix
        profile_path = Path(args.profile)
        output_path = profile_path.parent / (profile_path.stem + ".composer-digest.json")

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(digest, f, indent=2, ensure_ascii=False)

    print(f"✓ Composer digest generated: {output_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
