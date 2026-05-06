#!/usr/bin/env python3
"""Step 4 checkpoint validator — s04-content-draft.json + s04a-terminology-registry.json.

Catches Step-4 structural / grounding errors at the Step 4 boundary
instead of letting them surface in Step 6 (after Step 5's design pass
has already consumed the bad input).

Verifies:
  1. Slide coverage — every blueprint slide has a matching s04 entry
     (and vice-versa); taskIds align 1:1.
  2. Headline verbatim — every body slide's `headlineMessage` is
     copied verbatim from the blueprint (no Step-4 rewriting).
  3. contentForm shape — `contentForm.type` is in the canonical enum;
     type-specific count fields are present and positive.
  4. Structural slides — cover / divider / closing / agenda may have
     `contentForm = null` or omit body text.
  5. Speaker notes — present on every slide (no divider exemption).
  6. Source traceability — `contentSource: "document"` slides carry
     `sourceRef` (or every supportingPoint is a SourcedPoint).
  7. Terminology registry shape — `namedEntities` is a dict keyed by
     entity id, each value `{canonical, rejected}`. Same load-bearing
     check as `s06_validate_content.py`.
  8. Data-point grounding — every `dataPoints` entry has
     `verificationTier` + `confidence`; low-confidence precise numbers
     carry a `qualitativeForm`.
  9. Illustration spec — when present, `source` ∈ {to-generate,
     user-media, null} and refined `subject` is non-empty.

Usage:
  python s04_validate_content.py <session_dir>
  python s04_validate_content.py . --strict
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

try:
    import jsonschema  # type: ignore
except ImportError:  # pragma: no cover
    jsonschema = None

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass


def check_schema(content: dict, schema_path: Path) -> list[str]:
    """Validate content draft against s04-content-draft.schema.json.

    Skipped (with a notice) when jsonschema is not installed or the
    schema file is missing.
    """
    if jsonschema is None:
        return []
    if not schema_path.exists():
        return []
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"schema {schema_path.name} is not valid JSON: {exc}"]
    validator = jsonschema.Draft7Validator(schema)
    errors: list[str] = []
    for err in sorted(validator.iter_errors(content), key=lambda e: list(e.absolute_path)):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        errors.append(f"{loc}: {err.message}")
    return errors


# ── Catalog mirrors workflow-step4.md § Form Type Catalog ──────────────
CONTENT_FORM_TYPES = {
    # Structural slides (no required count fields)
    "cover":               set(),
    "divider":             set(),
    "closing":             set(),
    "agenda":              set(),
    # Content slides
    "text-narrative":      {"paragraphs"},
    "bullet-list":         {"items"},
    "stat-callout":        {"stats"},
    "comparison-matrix":   {"rows", "columns"},
    "timeline":            {"milestones"},
    "step-flow":           {"steps"},
    "architecture-layers": {"layers"},
    "code-walkthrough":    {"codeBlocks", "explanationPoints"},
    "diagram-callouts":    {"calloutCount"},
    "before-after":        set(),
    "card-grid":           {"cards"},
    "quote":               set(),
    "data-visualization":  {"chartType", "dataPoints"},
    "icon-list":           {"items"},
    "full-bleed-image":    set(),
}

STRUCTURAL_SLIDE_TYPES = {"cover", "divider", "closing", "agenda"}

ILLUSTRATION_SOURCES = {"to-generate", "user-media", None}

# Bullet-detection patterns: lines starting with -, *, •, or numbered list.
_BULLET_LINE = re.compile(r"^\s*(?:[-*•◦—]|\d+[.)])\s+", re.MULTILINE)


def _word_count(text: str) -> int:
    if not text:
        return 0
    return len(re.findall(r"\b\w+\b", text))


def _has_image(slide: dict) -> bool:
    """hasImage = mediaAttachments non-empty
              OR illustrationSpec.source == 'to-generate'
              OR contentForm.type == 'full-bleed-image'."""
    media = slide.get("mediaAttachments") or []
    if media:
        return True
    spec = slide.get("illustrationSpec") or {}
    if spec.get("source") == "to-generate":
        return True
    cf = slide.get("contentForm") or {}
    if isinstance(cf, dict) and cf.get("type") == "full-bleed-image":
        return True
    return False


def derive_content_metrics(slide: dict) -> dict:
    """Compute the deterministic content metrics for one slide.

    `wordCount` and `bulletCount` come from `contentBody` + supportingPoints.
    `dataPointCount` counts numeric tokens in body text using the same
    pattern as `s06_validate_content.py`. `hasImage` follows the
    three-source rule (see `_has_image`).
    """
    body = slide.get("contentBody") or ""
    sps = slide.get("supportingPoints") or []
    sp_text_parts: list[str] = []
    for sp in sps:
        if isinstance(sp, str):
            sp_text_parts.append(sp)
        elif isinstance(sp, dict):
            txt = sp.get("text")
            if isinstance(txt, str):
                sp_text_parts.append(txt)
    sp_text = "\n".join(sp_text_parts)
    full_text = (body + "\n" + sp_text).strip()

    word_count = _word_count(full_text)

    bullets_in_body = len(_BULLET_LINE.findall(body))
    bullet_count = bullets_in_body + len(sps)

    # Same numeric-token pattern as s06 validator (currency / decimals /
    # percent / basis points / 4+ digit ints, excluding plausible years).
    num_pattern = re.compile(
        r"\$\d[\d,]*(?:\.\d+)?[BMK]?"
        r"|\b\d+\.\d+%?"
        r"|\b\d{1,3}%"
        r"|\b\d+bps?\b"
        r"|\b\d{4,}\b"
    )
    year_pattern = re.compile(r"^(19|20)\d{2}$")
    data_point_count = sum(
        1
        for tok in num_pattern.findall(full_text)
        if not year_pattern.match(tok)
    )

    return {
        "wordCount": word_count,
        "dataPointCount": data_point_count,
        "bulletCount": bullet_count,
        "hasImage": _has_image(slide),
    }


def sync_content_metrics(content: dict) -> tuple[bool, list[str]]:
    """Recompute every slide's contentMetrics from its body/media.

    Returns (changed, notes). When a slide's existing metrics differ
    from the derived values, the derived values overwrite them and the
    delta is recorded in `notes`.
    """
    changed = False
    notes: list[str] = []
    for slide in content.get("slides", []):
        derived = derive_content_metrics(slide)
        existing = slide.get("contentMetrics") or {}
        if existing != derived:
            diffs = []
            for key in ("wordCount", "dataPointCount", "bulletCount", "hasImage"):
                old = existing.get(key)
                new = derived[key]
                if old != new:
                    diffs.append(f"{key}: {old!r}→{new!r}")
            notes.append(f"{slide.get('taskId', '?')}: {', '.join(diffs)}")
            slide["contentMetrics"] = derived
            changed = True
    return changed, notes


DEFAULT_CONFIDENCE_THRESHOLD = 0.7
_APPROX_MARKERS = re.compile(
    r"^[~≈≲≳<>]|about|approx|roughly|nearly|around|估计|约",
    re.IGNORECASE,
)


def load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        text = f.read()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        obj, _ = decoder.raw_decode(text)
        return obj


# ── Checks ──────────────────────────────────────────────────────────────


def check_slide_coverage(blueprint: dict, content: dict) -> list[str]:
    bp_ids = {s["slideId"] for s in blueprint.get("slides", [])}
    cd_ids = {s.get("taskId") for s in content.get("slides", [])}
    errors: list[str] = []
    missing = bp_ids - cd_ids
    extra = cd_ids - bp_ids
    if missing:
        errors.append(f"Missing from s04 content draft: {sorted(missing)}")
    if extra:
        errors.append(f"Extra in s04 (not in blueprint): {sorted(extra)}")
    return errors


def check_headline_verbatim(blueprint: dict, content: dict) -> list[str]:
    """Body slides must carry blueprint.headlineMessage verbatim.

    Step 4 explicitly forbids shortening / splitting headlines —
    that is Step 6a's job.
    """
    bp_map = {s["slideId"]: s for s in blueprint.get("slides", [])}
    errors: list[str] = []
    for slide in content.get("slides", []):
        tid = slide.get("taskId")
        bp = bp_map.get(tid)
        if not bp:
            continue
        bp_head = bp.get("headlineMessage")
        if not bp_head:
            continue  # structural slide
        cd_head = slide.get("headlineMessage")
        if cd_head != bp_head:
            errors.append(
                f"{tid}: headlineMessage differs from blueprint. "
                f"Blueprint: {bp_head!r}; s04: {cd_head!r}. "
                f"Step 4 must keep the blueprint headline verbatim."
            )
    return errors


def check_content_form(content: dict) -> list[str]:
    errors: list[str] = []
    for slide in content.get("slides", []):
        tid = slide.get("taskId", "?")
        slide_type = slide.get("slideType", "")
        cf = slide.get("contentForm")

        # contentForm may still be null/omitted for structural slides as a
        # legacy shorthand; both null and the explicit structural form id
        # (cover/divider/closing/agenda) are accepted.
        if cf in (None, {}):
            if slide_type in STRUCTURAL_SLIDE_TYPES:
                continue
            errors.append(f"{tid}: missing contentForm")
            continue

        if not isinstance(cf, dict):
            errors.append(f"{tid}: contentForm must be an object, got {type(cf).__name__}")
            continue

        ftype = cf.get("type")
        if ftype not in CONTENT_FORM_TYPES:
            errors.append(
                f"{tid}: contentForm.type {ftype!r} not in catalog "
                f"(see workflow-step4.md § Form Type Catalog)"
            )
            continue

        required = CONTENT_FORM_TYPES[ftype]
        for field in required:
            if field not in cf:
                errors.append(f"{tid}: contentForm[{ftype}] missing field '{field}'")
                continue
            value = cf[field]
            # Numeric count fields must be positive integers; string fields just non-empty.
            if field in {"chartType"}:
                if not isinstance(value, str) or not value.strip():
                    errors.append(f"{tid}: contentForm.{field} must be non-empty string")
            else:
                if not isinstance(value, int) or value < 1:
                    errors.append(
                        f"{tid}: contentForm.{field} must be a positive integer, "
                        f"got {value!r}"
                    )
    return errors


def check_speaker_notes(blueprint: dict, content: dict) -> list[str]:
    """Every slide must have non-empty speakerNotes (Step 4 cue)."""
    del blueprint  # signature compatibility; coverage is now universal
    errors: list[str] = []
    for slide in content.get("slides", []):
        tid = slide.get("taskId")
        notes = slide.get("speakerNotes")
        if not notes or not str(notes).strip():
            errors.append(f"{tid}: missing or empty speakerNotes")
    return errors


def check_source_traceability(content: dict) -> list[str]:
    """document-mode slides need either slide-level sourceRef or
    SourcedPoint supportingPoints."""
    errors: list[str] = []
    for slide in content.get("slides", []):
        if slide.get("contentSource") != "document":
            continue
        tid = slide.get("taskId", "?")
        if slide.get("sourceRef"):
            continue
        sps = slide.get("supportingPoints") or []
        if sps and all(isinstance(p, dict) and p.get("sourceRef") for p in sps):
            continue
        # contentBody-only document slides still need a slide-level sourceRef
        errors.append(
            f"{tid}: contentSource='document' but no sourceRef "
            f"(slide-level or per supportingPoint)"
        )
    return errors


def check_registry_shape(registry: dict) -> list[str]:
    """Mirror the s06 structural guard so Step 4 fails fast on bad shape."""
    errors: list[str] = []
    named = registry.get("namedEntities", {})
    if not isinstance(named, dict):
        return [
            "terminology-registry.namedEntities must be a dict keyed by "
            f"entity id, got {type(named).__name__}. "
            "See schemas/s04a-terminology-registry.example.json."
        ]
    for eid, entity in named.items():
        if not isinstance(entity, dict):
            errors.append(
                f"namedEntities[{eid!r}] must be an object "
                f"{{canonical, rejected}}, got {type(entity).__name__}"
            )
            continue
        if not entity.get("canonical"):
            errors.append(f"namedEntities[{eid!r}] missing 'canonical'")
        rejected = entity.get("rejected", [])
        if not isinstance(rejected, list):
            errors.append(
                f"namedEntities[{eid!r}].rejected must be a list, "
                f"got {type(rejected).__name__}"
            )
    return errors


def check_data_point_grounding(registry: dict) -> tuple[list[str], list[str]]:
    """Every dataPoint needs verificationTier + confidence; low-conf
    precise numbers need qualitativeForm."""
    errors: list[str] = []
    warnings: list[str] = []
    dps = registry.get("dataPoints", {})
    if isinstance(dps, list):
        items = {f"dp_{i}": dp for i, dp in enumerate(dps)}
    else:
        items = dps if isinstance(dps, dict) else {}

    valid_tiers = {"verified", "common-knowledge", "unverified"}
    for dp_id, dp in items.items():
        if not isinstance(dp, dict):
            errors.append(f"dataPoints[{dp_id!r}] must be an object")
            continue
        tier = dp.get("verificationTier")
        if tier not in valid_tiers:
            errors.append(
                f"dataPoints[{dp_id!r}]: verificationTier must be one of "
                f"{sorted(valid_tiers)}, got {tier!r}"
            )
        conf = dp.get("confidence")
        try:
            conf_f = float(conf) if conf is not None else None
        except (TypeError, ValueError):
            conf_f = None
        if conf_f is None or not (0.0 <= conf_f <= 1.0):
            errors.append(
                f"dataPoints[{dp_id!r}]: confidence must be float in [0.0, 1.0], "
                f"got {conf!r}"
            )
            continue
        if conf_f < DEFAULT_CONFIDENCE_THRESHOLD:
            value = str(dp.get("value", ""))
            qual = dp.get("qualitativeForm")
            if value and not _APPROX_MARKERS.search(value) and not qual:
                warnings.append(
                    f"dataPoints[{dp_id!r}] ({value}): "
                    f"confidence={conf_f} < {DEFAULT_CONFIDENCE_THRESHOLD} but no "
                    f"qualitativeForm — Step 6 will flag missing fallback"
                )
        if tier == "unverified":
            warnings.append(
                f"dataPoints[{dp_id!r}] ({dp.get('value', '?')}): "
                f"verificationTier='unverified' — will be listed in generation report"
            )
    return errors, warnings


def check_illustration_spec(content: dict) -> list[str]:
    errors: list[str] = []
    for slide in content.get("slides", []):
        tid = slide.get("taskId", "?")
        spec = slide.get("illustrationSpec")
        if not spec:
            continue
        if not isinstance(spec, dict):
            errors.append(f"{tid}: illustrationSpec must be an object")
            continue
        src = spec.get("source")
        if src not in ILLUSTRATION_SOURCES:
            errors.append(
                f"{tid}: illustrationSpec.source must be one of "
                f"{sorted(s for s in ILLUSTRATION_SOURCES if s)} or null, got {src!r}"
            )
        if src == "to-generate":
            subject = spec.get("subject")
            if not subject or not str(subject).strip():
                errors.append(f"{tid}: illustrationSpec.source='to-generate' requires non-empty subject")
            count = spec.get("imageCount")
            if isinstance(count, int) and count > 1:
                per = spec.get("perImageSubject")
                if not per or not isinstance(per, list) or len(per) != count:
                    errors.append(
                        f"{tid}: imageCount={count} requires perImageSubject list of length {count}, "
                        f"got {per!r}"
                    )
    return errors


# ── Main ────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Step 4 checkpoint validator for narrative-pptx-composer"
    )
    parser.add_argument("session_dir", type=Path)
    parser.add_argument("--strict", action="store_true",
                        help="Treat warnings as errors (exit 1 on any issue)")
    args = parser.parse_args()

    session = args.session_dir.resolve()

    required = {
        "s03-presentation-blueprint.json": "blueprint",
        "s04-content-draft.json": "content",
        "s04a-terminology-registry.json": "registry",
    }
    artifacts: dict[str, dict] = {}
    for filename, key in required.items():
        path = session / filename
        if not path.exists():
            print(f"FAIL: {filename} not found in {session}")
            return 1
        artifacts[key] = load_json(path)

    blueprint = artifacts["blueprint"]
    content = artifacts["content"]
    registry = artifacts["registry"]

    # Derive contentMetrics from content body / media before validating.
    # `wordCount` / `bulletCount` / `dataPointCount` / `hasImage` are
    # deterministic derivations — the LLM should not hand-fill them.
    metrics_changed, metrics_notes = sync_content_metrics(content)
    if metrics_changed:
        with open(session / "s04-content-draft.json", "w", encoding="utf-8") as f:
            json.dump(content, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print(f"ⓘ Auto-derived contentMetrics for {len(metrics_notes)} slide(s):")
        for note in metrics_notes:
            print(f"  - {note}")
        print()

    print(f"Validating Step 4 checkpoint in: {session.name}")
    print(f"  Blueprint slides: {len(blueprint.get('slides', []))}")
    print(f"  Content entries:  {len(content.get('slides', []))}")
    print(f"  Registry entities: {len(registry.get('namedEntities', {}))}")
    print(f"  Registry data points: {len(registry.get('dataPoints', {}))}")
    print()

    all_errors: list[str] = []
    all_warnings: list[str] = []

    def run(name: str, fn, *args_):
        result = fn(*args_)
        if isinstance(result, tuple):
            errors, warnings = result
        else:
            errors, warnings = result, []
        if errors:
            print(f"✗ {name}")
            for e in errors:
                print(f"  ERROR: {e}")
            all_errors.extend(errors)
        elif warnings:
            print(f"⚠ {name}")
            for w in warnings:
                print(f"  WARN: {w}")
            all_warnings.extend(warnings)
        else:
            print(f"✓ {name}")

    run("Slide coverage",          check_slide_coverage,        blueprint, content)
    run("Schema (jsonschema)",     check_schema,                content,
        Path(__file__).parent.parent / "schemas" / "s04-content-draft.schema.json")
    run("Headline verbatim",       check_headline_verbatim,     blueprint, content)
    run("contentForm shape",       check_content_form,          content)
    run("Speaker notes",           check_speaker_notes,         blueprint, content)
    run("Source traceability",     check_source_traceability,   content)
    run("Registry shape",          check_registry_shape,        registry)
    run("Data-point grounding",    check_data_point_grounding,  registry)
    run("Illustration spec",       check_illustration_spec,     content)

    total = len(all_errors) + (len(all_warnings) if args.strict else 0)
    print()
    if total == 0:
        print("═══ PASS — Step 4 checkpoint validated ═══")
        return 0
    print(f"═══ FAIL — {len(all_errors)} error(s), {len(all_warnings)} warning(s) ═══")
    return 1


if __name__ == "__main__":
    sys.exit(main())
