#!/usr/bin/env python3
"""Step 6 checkpoint validator — s06-slide-content.json + s04a-terminology-registry.json.

Template-free redesign. Verifies:
  1. Every taskId in s05-slide-visual-design.json has a matching entry in s06-slide-content.json
  2. Every slide has non-empty speakerNotes (no divider exemption)
  3. No rejected terminology variants from s04a-terminology-registry.json
  4. Slot zone names match plan layoutSpec zone roles (no orphan slots, no empty text zones)
  5. No leftover placeholder text (xxxx, lorem, ipsum, TBD, click to add) anywhere on slides
  6. Numeric tokens in slide text cross-checked against s04a-terminology-registry.json → dataPoints
  7. Title slot text shares substantial overlap with blueprint's headlineMessage
     (Step 6a permits light shortening; < 40% token overlap is flagged as drift)
  8. Prints the headline sequence for manual narrative coherence review
  9. Content grounding — every dataPoint has a verificationTier (verified/common-knowledge/unverified);
     unverified items are flagged for inclusion in the generation report
  10. Confidence threshold — low-confidence precise numbers must provide a qualitativeForm;
      slides should use qualitativeForm instead of raw value for low-confidence data points

Usage:
  python s06_validate_content.py <session_dir>
  python s06_validate_content.py .                       # from inside session dir
  python s06_validate_content.py . --strict              # exit 1 on any warning
  python s06_validate_content.py . --min-term-length 5   # skip short rejected terms
"""

from __future__ import annotations

import argparse
import json
import re
import sys

# Force UTF-8 stdout on Windows so check-mark / cross / warning glyphs
# don't crash the validator on the default cp1252 console.
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass
from pathlib import Path


def load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def check_task_coverage(plan: dict, content: dict) -> list[str]:
    """Every taskId in slide-visual-design must have a matching slide-content entry."""
    plan_ids = {s["taskId"] for s in plan["slides"]}
    content_ids = {s["taskId"] for s in content["slides"]}
    errors = []
    missing = plan_ids - content_ids
    extra = content_ids - plan_ids
    if missing:
        errors.append(f"Missing from slide-content: {sorted(missing)}")
    if extra:
        errors.append(f"Extra in slide-content (not in plan): {sorted(extra)}")
    return errors


def check_speaker_notes(plan: dict, content: dict) -> list[str]:
    """Every slide must have non-empty speakerNotes.

    The `plan` argument is unused but kept in the signature for backwards
    compatibility with callers that pre-date the divider-exemption removal.
    """
    del plan  # signature compatibility
    errors = []
    for slide in content["slides"]:
        tid = slide["taskId"]
        notes = slide.get("speakerNotes")
        if not notes or not notes.strip():
            errors.append(f"{tid}: missing or empty speakerNotes")
    return errors


def check_rejected_terms(
    content: dict, registry: dict, min_length: int = 4
) -> list[str]:
    """No rejected terminology variants should appear in slot text or notes.

    To avoid false positives where a rejected term is a substring of its
    own canonical form (e.g. "pointer net" inside "Pointer Network"),
    we mask out all canonical occurrences before scanning for rejected terms.

    Structural validation: namedEntities must be a dict keyed by stable
    id, with each value an object {canonical, rejected}. The legacy
    {canonical:[...], rejected:[...]} flat shape is rejected with a
    pointer to the canonical example file (see retrospective I-03).
    """
    # Structural guard — give a useful error instead of AttributeError.
    named = registry.get("namedEntities", {})
    if not isinstance(named, dict):
        return [
            "terminology-registry namedEntities must be a dict keyed by "
            f"entity id, got {type(named).__name__}. "
            "See schemas/s04a-terminology-registry.example.json for the canonical shape."
        ]
    for eid, entity in named.items():
        if not isinstance(entity, dict):
            return [
                f"terminology-registry namedEntities[{eid!r}] must be an "
                f"object {{canonical, rejected}}, got {type(entity).__name__}. "
                "Did you nest 'canonical' as a list at the top level? "
                "See schemas/s04a-terminology-registry.example.json."
            ]

    # Build (rejected, canonical) pairs and a set of all canonical forms
    rejected_terms: list[tuple[str, str]] = []  # (rejected, canonical)
    canonical_forms: list[str] = []
    for entity in named.values():
        canonical = entity.get("canonical", "")
        if canonical:
            canonical_forms.append(canonical)
        for term in entity.get("rejected", []):
            if len(term) >= min_length:
                rejected_terms.append((term, canonical))

    errors = []
    for slide in content["slides"]:
        all_text_parts = [slot.get("text", "") for slot in slide.get("slots", [])]
        notes = slide.get("speakerNotes") or ""
        combined = " ".join(all_text_parts) + " " + notes
        combined_lower = combined.lower()

        # Mask canonical forms so their substrings don't trigger
        # false positives. Replace with a same-length placeholder
        # to preserve position/length properties.
        masked = combined_lower
        for canon in canonical_forms:
            masked = masked.replace(canon.lower(), "\x00" * len(canon))

        for term, canonical in rejected_terms:
            if term.lower() in masked:
                errors.append(
                    f"{slide['taskId']}: rejected term '{term}' found "
                    f"(canonical: '{canonical}')"
                )
    return errors


PLACEHOLDER_PATTERN = re.compile(
    r"\b(xxxx+|lorem|ipsum|click to (add|edit|insert)|insert (text|title|here)|TBD|TODO|FIXME|placeholder)\b",
    re.IGNORECASE,
)

# Numeric tokens worth cross-checking against the registry:
# - currency:           $4.2B, $500K, $1,200
# - decimals:           61.2, 3.14, 180.5
# - percentages:        23%, 0.5%
# - basis points:       180bp, 50bps
# - large integers ≥4 digits but NOT plausible years (1900–2099)
NUMBER_TOKEN_PATTERN = re.compile(
    r"\$\d[\d,]*(?:\.\d+)?[BMK]?"           # currency
    r"|\b\d+\.\d+%?"                          # decimals (and percent decimals)
    r"|\b\d{1,3}%"                            # integer percentages 0-999%
    r"|\b\d+bps?\b"                           # basis points
    r"|\b\d{4,}\b"                            # 4+ digit integers (filter years below)
)
YEAR_PATTERN = re.compile(r"^(19|20)\d{2}$")


def check_placeholders(content: dict) -> list[str]:
    """Hard fail on leftover placeholder text in any slot or speaker note.

    Catches the failure mode where Step 4/7 left scaffolding text behind
    (e.g. agenda page numbers stuck on "TBD", forgotten lorem ipsum,
    template prompts like "Click to add title").
    """
    errors: list[str] = []
    for slide in content.get("slides", []):
        tid = slide.get("taskId", "?")
        for slot in slide.get("slots", []):
            text = slot.get("text", "")
            if PLACEHOLDER_PATTERN.search(text):
                hits = sorted({m.group(0) for m in PLACEHOLDER_PATTERN.finditer(text)})
                errors.append(
                    f"{tid} zone='{slot.get('zone', '?')}': "
                    f"placeholder text {hits} in slot text"
                )
        notes = slide.get("speakerNotes") or ""
        if PLACEHOLDER_PATTERN.search(notes):
            hits = sorted({m.group(0) for m in PLACEHOLDER_PATTERN.finditer(notes)})
            errors.append(f"{tid}: placeholder text {hits} in speakerNotes")
    return errors


def _registry_value_strings(registry: dict) -> set[str]:
    """Collect every dataPoint value as a normalized string for membership tests."""
    out: set[str] = set()
    data_points = registry.get("dataPoints", {})
    if isinstance(data_points, list):
        items = data_points
    else:
        items = list(data_points.values())
    for dp in items:
        if not isinstance(dp, dict):
            continue
        value = dp.get("value")
        if value is None or value == "":
            continue
        # Stringify and strip trailing punctuation; keep currency/percent symbols.
        s = str(value).strip().rstrip(".,;:")
        if s:
            out.add(s)
        # Also allow registry to declare alternative renderings.
        for alt in dp.get("aliases", []) or []:
            alt_s = str(alt).strip().rstrip(".,;:")
            if alt_s:
                out.add(alt_s)
    return out


def check_data_point_consistency(content: dict, registry: dict) -> list[str]:
    """Warn on numeric tokens in slide text or speaker notes that don't
    appear in the registry.

    Catches the failure mode where the LLM invents or restates a number
    that drifted from the canonical registry value. Speaker notes are
    scanned because Step 6b Stage 2 demotes content (including precise
    figures) from slide into notes — those demoted numbers must remain
    registry-grounded just like on-slide numbers.

    Skips:
      - Plausible 4-digit years (1900–2099)
      - Numbers ≤ 2 digits with no symbol (slide indices, "3 steps") —
        not matched by NUMBER_TOKEN_PATTERN
    """
    warnings: list[str] = []
    registry_values = _registry_value_strings(registry)
    if not registry_values:
        return warnings

    # Build a normalized set for tolerant matching.
    registry_normalized = {v.replace(",", "").lower() for v in registry_values}

    def scan(text: str, sink: set[tuple[str, str]], source: str) -> None:
        """Collect (token, source) pairs for any numeric token not traced
        to a registry value."""
        for m in NUMBER_TOKEN_PATTERN.finditer(text):
            tok = m.group(0)
            if YEAR_PATTERN.match(tok):
                continue
            norm = tok.replace(",", "").lower()
            if tok in registry_values or norm in registry_normalized:
                continue
            # Allow tokens that are substrings of any registry value
            # (e.g. registry says "$4.2B", slide says "4.2").
            if any(norm in v for v in registry_normalized):
                continue
            sink.add((tok, source))

    for slide in content.get("slides", []):
        tid = slide.get("taskId", "?")
        unknown: set[tuple[str, str]] = set()
        for slot in slide.get("slots", []):
            scan(slot.get("text", ""), unknown, "slot")
        scan(slide.get("speakerNotes") or "", unknown, "notes")
        if unknown:
            slot_hits = sorted({tok for tok, src in unknown if src == "slot"})
            note_hits = sorted({tok for tok, src in unknown if src == "notes"})
            parts = []
            if slot_hits:
                parts.append(f"slots={slot_hits}")
            if note_hits:
                parts.append(f"notes={note_hits}")
            warnings.append(
                f"{tid}: numeric tokens not in terminology-registry → "
                f"dataPoints: {' '.join(parts)}"
            )
    return warnings


def check_slot_zone_alignment(plan: dict, content: dict) -> tuple[list[str], list[str]]:
    """slot.zone names must match plan layoutSpec zone roles.

    Catches the silent failure where a renamed/typo'd slot is dropped at
    build time, leaving an empty rectangle in the rendered slide.

    Errors: orphan slots (slot.zone not in any plan zone.role).
    Warnings: text-type plan zones with no matching content slot
              (excluding structural decoration zones like accent-bar).
    """
    errors: list[str] = []
    warnings: list[str] = []
    plan_by_id = {s["taskId"]: s for s in plan.get("slides", [])}
    structural_text = {
        "accent", "accent-bar", "side-stripe", "divider", "line",
        "act-label",
    }
    for cs in content.get("slides", []):
        tid = cs.get("taskId", "?")
        ps = plan_by_id.get(tid)
        if not ps:
            continue  # check_task_coverage handles missing plan entries
        zones = ps.get("layoutSpec", {}).get("zones", [])
        plan_roles = {z.get("role") for z in zones if z.get("role")}
        text_roles = {z.get("role") for z in zones if z.get("type") == "text"}
        slot_zones = {sl.get("zone") for sl in cs.get("slots", []) if sl.get("zone")}

        orphan = slot_zones - plan_roles
        if orphan:
            errors.append(
                f"{tid}: slot zones {sorted(orphan)} not present in plan layoutSpec roles"
            )
        unfilled = (text_roles - slot_zones) - structural_text
        if unfilled:
            warnings.append(
                f"{tid}: text zones {sorted(unfilled)} have no content slot — "
                f"will render empty"
            )
    return errors, warnings


# ── Content grounding checks ────────────────────────────────────────────

# Confidence threshold below which a precise numeric value triggers a
# warning unless the registry entry provides a ``qualitativeForm``.
DEFAULT_CONFIDENCE_THRESHOLD = 0.7

# Tokens that indicate the value is already approximate / qualitative
# and therefore exempt from the threshold warning.
_APPROX_MARKERS = re.compile(r"^[~≈≲≳<>]|about|approx|roughly|nearly|around|估计|约", re.IGNORECASE)


def check_formula_slots(plan: dict, content: dict) -> tuple[list[str], list[str]]:
    """Validate formula slots against `type: "formula"` zones in the plan.

    Per sessions/formula-svg-design-2026-05-01.md § 5.2:
      * Every plan zone with `type: "formula"` MUST have a matching slot
        carrying `formulaSource` (non-empty) and `alt` (non-empty, ≥10 chars).
      * `formulaSource` MUST parse under matplotlib mathtext
        (`s07_slide_helpers.validate_mathtext`). Hard error.
      * `formulaSource` MUST NOT carry `$…$` / `\\(…\\)` / `\\[…\\]`
        delimiters — the renderer wraps with `$…$` itself; doubled
        delimiters silently produce empty SVGs.
      * `alt` MUST be plain language (no LaTeX backslash commands).

    Returns (errors, warnings). All formula-content failures are errors —
    a broken formula slide is a P0 rendering bug.
    """
    errors: list[str] = []
    warnings: list[str] = []

    # Lazily import the validator helper. When unavailable, skip the
    # mathtext parse check (with a single warning) but keep the rest.
    parse_mathtext = None
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from s07_slide_helpers import validate_mathtext as _vm
        parse_mathtext = _vm
    except Exception as e:
        warnings.append(
            f"could not import s07_slide_helpers.validate_mathtext "
            f"({e}); mathtext syntactic check skipped"
        )

    # Locate every formula zone in the plan, keyed by (taskId, role).
    plan_formula_zones: dict[tuple[str, str], dict] = {}
    for s in plan.get("slides", []):
        tid = s.get("taskId")
        if not tid:
            continue
        for z in (s.get("layoutSpec") or {}).get("zones", []) or []:
            if z.get("type") == "formula":
                plan_formula_zones[(tid, z.get("role"))] = z

    # Map content slots by (taskId, zone) for cross-reference.
    content_slots: dict[tuple[str, str], dict] = {}
    for cs in content.get("slides", []):
        tid = cs.get("taskId")
        if not tid:
            continue
        for slot in cs.get("slots", []) or []:
            content_slots[(tid, slot.get("zone"))] = slot

    delim_re = re.compile(r"^\s*(\$\$?|\\\(|\\\[)|(\$\$?|\\\)|\\\])\s*$")
    backslash_cmd_re = re.compile(r"\\[A-Za-z]+")

    for (tid, role), zone in plan_formula_zones.items():
        prefix = f"{tid}/{role}(formula)"
        slot = content_slots.get((tid, role))
        if slot is None:
            errors.append(f"{prefix}: no matching slot in s06-slide-content.json")
            continue

        source = slot.get("formulaSource")
        if not isinstance(source, str) or not source.strip():
            errors.append(f"{prefix}: missing/empty formulaSource")
            continue

        if delim_re.search(source):
            errors.append(
                f"{prefix}: formulaSource carries delimiters ($…$ / \\(…\\) / \\[…\\]). "
                "The renderer wraps with $…$ itself; remove the outer delimiters."
            )

        if parse_mathtext is not None:
            ok, err = parse_mathtext(source)
            if not ok:
                # Compress multi-line parser output into one line for the log.
                err_line = " | ".join(line.strip() for line in (err or "").splitlines() if line.strip())
                errors.append(f"{prefix}: mathtext parse failed — {err_line}")

        alt = slot.get("alt")
        if not isinstance(alt, str) or not alt.strip():
            errors.append(
                f"{prefix}: missing 'alt' (mandatory for accessibility on formula slots)"
            )
        elif len(alt.strip()) < 10:
            errors.append(
                f"{prefix}: 'alt' too short ({len(alt.strip())} chars; need ≥10) — "
                "must be a plain-language read-out, not a label"
            )
        elif backslash_cmd_re.search(alt):
            errors.append(
                f"{prefix}: 'alt' contains LaTeX commands "
                f"({backslash_cmd_re.findall(alt)[:3]}…); must be plain language"
            )

    return errors, warnings


def check_content_grounding(registry: dict) -> tuple[list[str], list[str]]:
    """Report verification-tier distribution and flag unverified data points.

    Returns (errors, warnings).
    - Errors: none (tier labeling is advisory).
    - Warnings: emitted for every ``unverified`` data point, and for
      ``common-knowledge`` points whose confidence < threshold without
      a ``qualitativeForm``.
    """
    warnings: list[str] = []
    data_points = registry.get("dataPoints", {})
    if isinstance(data_points, list):
        items = {f"dp_{i}": dp for i, dp in enumerate(data_points)}
    else:
        items = data_points

    tier_counts: dict[str, int] = {"verified": 0, "common-knowledge": 0, "unverified": 0, "unlabeled": 0}
    for dp_id, dp in items.items():
        if not isinstance(dp, dict):
            continue
        tier = dp.get("verificationTier", "")
        if tier in tier_counts:
            tier_counts[tier] += 1
        else:
            tier_counts["unlabeled"] += 1
            warnings.append(
                f"dataPoints[{dp_id!r}]: missing or unknown verificationTier "
                f"(got {tier!r}) — default to 'unverified'"
            )
        if tier == "unverified":
            warnings.append(
                f"dataPoints[{dp_id!r}] ({dp.get('value', '?')}): "
                f"verificationTier='unverified' — will be flagged in generation report"
            )
    return [], warnings


def check_confidence_threshold(
    content: dict, registry: dict, threshold: float = DEFAULT_CONFIDENCE_THRESHOLD
) -> list[str]:
    """Warn when a low-confidence precise number appears on a slide without
    a qualitative fallback.

    A data point with ``confidence < threshold`` that does NOT provide
    ``qualitativeForm`` AND whose ``value`` looks like a precise number
    (no approximation markers) triggers a warning.

    The check also verifies that slides actually USE the qualitativeForm
    (not the raw value) for low-confidence points that do supply one.
    """
    warnings: list[str] = []
    data_points = registry.get("dataPoints", {})
    if isinstance(data_points, list):
        items = {f"dp_{i}": dp for i, dp in enumerate(data_points)}
    else:
        items = data_points

    # Collect low-confidence points
    low_conf: dict[str, dict] = {}  # dp_id → dp
    for dp_id, dp in items.items():
        if not isinstance(dp, dict):
            continue
        conf = dp.get("confidence")
        if conf is None:
            continue
        try:
            conf_f = float(conf)
        except (TypeError, ValueError):
            continue
        if conf_f < threshold:
            low_conf[dp_id] = dp

    if not low_conf:
        return warnings

    # Phase 1: check that low-confidence precise values have qualitativeForm
    for dp_id, dp in low_conf.items():
        value = str(dp.get("value", ""))
        qual = dp.get("qualitativeForm")
        if _APPROX_MARKERS.search(value):
            continue  # value is already approximate
        if not qual:
            warnings.append(
                f"dataPoints[{dp_id!r}] ({value}): "
                f"confidence={dp.get('confidence')} < {threshold} but no "
                f"qualitativeForm provided — add a qualitative alternative "
                f"(e.g. \"approximately {value}\") or raise confidence"
            )

    # Phase 2: check slides use qualitativeForm (not raw value) for low-conf points
    if content:
        for dp_id, dp in low_conf.items():
            qual = dp.get("qualitativeForm")
            raw_value = str(dp.get("value", ""))
            if not qual or not raw_value:
                continue
            for slide in content.get("slides", []):
                for slot in slide.get("slots", []):
                    text = slot.get("text", "")
                    if raw_value in text and qual not in text:
                        warnings.append(
                            f"{slide.get('taskId', '?')} zone='{slot.get('zone', '?')}': "
                            f"uses raw value '{raw_value}' for low-confidence "
                            f"dataPoints[{dp_id!r}] — prefer qualitativeForm "
                            f"'{qual}'"
                        )
    return warnings


def _normalize_for_compare(s: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    s = re.sub(r"[^\w\s]", " ", s.lower())
    s = re.sub(r"\s+", " ", s).strip()
    return s


def check_headline_alignment(
    content: dict, blueprint: dict | None
) -> list[str]:
    """Warn when a slide's title slot doesn't faithfully render the
    blueprint's headlineMessage.

    Step 6a allows lightly shortening the headline to fit the title
    zone (drop modifiers / subordinate clauses, preserve core claim).
    A wholesale rewrite — < 40% token overlap with the blueprint
    headline — signals drift and is reported as a warning.
    """
    if not blueprint:
        return []

    bp_headlines = {
        s["slideId"]: s.get("headlineMessage")
        for s in blueprint.get("slides", [])
    }
    warnings: list[str] = []
    for slide in content.get("slides", []):
        tid = slide.get("taskId")
        bp_head = bp_headlines.get(tid)
        if not bp_head:
            continue  # cover/divider/closing — no headline to align with
        title_text = ""
        for slot in slide.get("slots", []):
            if slot.get("zone") == "title":
                title_text = slot.get("text", "")
                break
        if not title_text:
            title_text = slide.get("title") or ""
        if not title_text:
            continue
        bp_norm = _normalize_for_compare(bp_head)
        ti_norm = _normalize_for_compare(title_text)
        if not bp_norm or not ti_norm:
            continue
        bp_tokens = set(bp_norm.split())
        ti_tokens = set(ti_norm.split())
        # Drop short stop-like tokens from the overlap signal
        stop = {"a", "an", "the", "and", "or", "of", "to", "in", "for", "on", "is", "are", "be"}
        bp_tokens -= stop
        ti_tokens -= stop
        if not bp_tokens:
            continue
        overlap = len(bp_tokens & ti_tokens) / len(bp_tokens)
        if overlap < 0.4:
            warnings.append(
                f"{tid}: title {title_text!r} shares only "
                f"{overlap*100:.0f}% of blueprint headline tokens. "
                f"Blueprint says: {bp_head!r}. "
                f"Step 6a allows in-step compression (syntactic, then "
                f"semantic to the core claim with framing demoted to "
                f"speakerNotes); this warning is informational only — "
                f"verify the compressed title still conveys the core "
                f"claim faithfully."
            )
    return warnings


def print_headline_sequence(content: dict, plan: dict) -> None:
    """Print the headline/title sequence for manual narrative coherence review."""
    plan_map = {s["taskId"]: s for s in plan["slides"]}
    print("\n── Headline Sequence (review for narrative coherence) ──")
    for slide in content["slides"]:
        tid = slide["taskId"]
        role = plan_map.get(tid, {}).get("slideType", "?")
        title = slide.get("title", "")
        # Find the title slot text
        title_text = title
        for slot in slide.get("slots", []):
            if slot.get("zone") == "title":
                title_text = slot.get("text", "") or title
                break
        if role in ("cover", "divider", "closing"):
            print(f"  {tid} [{role}] {title_text}")
        else:
            print(f"  {tid} {title_text}")
    print("── End ──\n")


def print_modified_headlines(content: dict, blueprint: dict | None) -> None:
    """Print headlines that differ from blueprint but stayed above the
    40% overlap threshold (Step 6a compression occurred but did not
    trigger the alignment warning). Informational only — for
    presenter review and Step 8 visual QA cross-check.
    """
    if not blueprint:
        return
    bp_heads = {
        s.get("slideId"): s.get("headlineMessage")
        for s in blueprint.get("slides", [])
    }
    stop = {"a", "an", "the", "and", "or", "of", "to", "in", "for", "on", "is", "are", "be"}
    modified: list[tuple[str, float, str, str]] = []
    for slide in content.get("slides", []):
        tid = slide.get("taskId")
        bp = bp_heads.get(tid) or ""
        if not bp:
            continue
        title = ""
        for slot in slide.get("slots", []):
            if slot.get("zone") == "title":
                title = slot.get("text", "") or ""
                break
        if not title:
            continue
        if title.strip() == bp.strip():
            continue  # verbatim — nothing to report
        bp_norm = _normalize_for_compare(bp)
        ti_norm = _normalize_for_compare(title)
        if not bp_norm or not ti_norm:
            continue
        bp_tokens = set(bp_norm.split()) - stop
        ti_tokens = set(ti_norm.split()) - stop
        if not bp_tokens:
            continue
        ovl = len(bp_tokens & ti_tokens) / len(bp_tokens)
        if ovl < 0.4:
            continue  # already surfaced in the warning section
        modified.append((tid, ovl, bp, title))
    if not modified:
        return
    print(
        "── Modified Headlines "
        "(compressed in Step 6, ≥40% overlap — informational) ──"
    )
    for tid, ovl, bp, ti in modified:
        print(f"  {tid}  overlap={ovl*100:.0f}%")
        print(f"    blueprint: {bp!r}")
        print(f"    title    : {ti!r}")
    print("── End ──\n")


def print_self_split_slides(
    content: dict, plan: dict, draft: dict | None
) -> None:
    """Log slides where Step 6 had to split `contentBody` heuristically
    because Step 4 did not provide structured `blocks[]` for a
    multi-zone layout. Informational only — surfaces an opportunity
    to author `blocks[]` upfront for reproducibility.

    Heuristic: a slide is reported when the plan defines 3+ body-text
    zones (excluding title / footer / decorative roles) and the
    corresponding draft entry has no `blocks[]`.
    """
    if not draft:
        return
    draft_map = {s.get("taskId"): s for s in draft.get("slides", [])}
    skip_roles = {
        "title", "subtitle", "footer", "footer-pages", "page-number",
        "footnote", "section-marker", "act-marker", "caption",
        "decoration", "background",
        # Structural/divider decorative chrome (not real body content)
        "act-numeral", "act-label", "act-title", "vertical-act-label",
        "stage-numeral", "stage-label",
    }
    # Skip slides whose plan slideType is purely structural — their
    # "multi-zone" appearance comes from divider/cover chrome, not from
    # body content that needs splitting.
    structural_types = {"cover", "divider", "closing", "agenda"}
    self_split: list[tuple[str, int, list[str]]] = []
    for slide in plan.get("slides", []):
        tid = slide.get("taskId")
        if slide.get("slideType") in structural_types:
            continue
        zones = (slide.get("layoutSpec") or {}).get("zones", []) or []
        body_text_zones = [
            z for z in zones
            if z.get("type") == "text"
            and z.get("role", "") not in skip_roles
        ]
        if len(body_text_zones) < 3:
            continue
        d = draft_map.get(tid) or {}
        blocks = d.get("blocks") or []
        if blocks:
            continue  # explicit upfront split — not self-split
        self_split.append(
            (tid, len(body_text_zones), [z.get("role", "?") for z in body_text_zones])
        )
    if not self_split:
        return
    print(
        "── Step 6 Self-Split Slides "
        "(contentBody split heuristically; consider authoring `blocks[]` upfront) ──"
    )
    for tid, n_zones, roles in self_split:
        roles_preview = ", ".join(roles[:6]) + (" …" if len(roles) > 6 else "")
        print(f"  {tid}  {n_zones} body zones: [{roles_preview}]")
    print("── End ──\n")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Step 6 checkpoint validator for narrative-pptx-composer"
    )
    parser.add_argument(
        "session_dir",
        type=Path,
        help="Path to the session directory containing the JSON artifacts",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as errors (exit 1 on any issue)",
    )
    parser.add_argument(
        "--min-term-length",
        type=int,
        default=4,
        help="Minimum length for rejected terms to check (default: 4)",
    )
    args = parser.parse_args()

    session = args.session_dir.resolve()

    # Load required artifacts
    required_files = {
        "s05-slide-visual-design.json": "slide-plan",
        "s06-slide-content.json": "slide-content",
        "s04a-terminology-registry.json": "terminology-registry",
    }
    artifacts = {}
    for filename, key in required_files.items():
        path = session / filename
        if not path.exists():
            print(f"FAIL: {filename} not found in {session}")
            return 1
        artifacts[key] = load_json(path)

    plan = artifacts["slide-plan"]
    content = artifacts["slide-content"]
    registry = artifacts["terminology-registry"]

    # Also load blueprint if available (for richer reporting)
    blueprint_path = session / "s03-presentation-blueprint.json"
    blueprint = load_json(blueprint_path) if blueprint_path.exists() else None

    # Also load content draft if available (for blocks[] / self-split detection)
    draft_path = session / "s04-content-draft.json"
    draft = load_json(draft_path) if draft_path.exists() else None

    print(f"Validating Step 6 checkpoint in: {session.name}")
    print(f"  Plan tasks: {len(plan['slides'])}")
    print(f"  Content entries: {len(content['slides'])}")
    print(f"  Registry entities: {len(registry.get('namedEntities', {}))}")
    print(f"  Registry data points: {len(registry.get('dataPoints', {}))}")
    print()

    all_errors: list[str] = []
    all_warnings: list[str] = []

    # 1. Task coverage
    errors = check_task_coverage(plan, content)
    if errors:
        print("✗ Task coverage")
        for e in errors:
            print(f"  ERROR: {e}")
        all_errors.extend(errors)
    else:
        print(f"✓ Task coverage — {len(plan['slides'])}/{len(plan['slides'])} matched")

    # 2. Speaker notes
    errors = check_speaker_notes(plan, content)
    if errors:
        print("✗ Speaker notes")
        for e in errors:
            print(f"  ERROR: {e}")
        all_errors.extend(errors)
    else:
        slide_count = len(content["slides"])
        print(f"✓ Speaker notes — {slide_count} slides have notes (no exemptions)")

    # 3. Rejected terminology
    errors = check_rejected_terms(content, registry, args.min_term_length)
    if errors:
        print("✗ Rejected terminology")
        for e in errors:
            print(f"  ERROR: {e}")
        all_errors.extend(errors)
    else:
        total_rejected = sum(
            len(e.get("rejected", []))
            for e in registry.get("namedEntities", {}).values()
        )
        print(
            f"✓ Rejected terminology — 0 violations "
            f"({total_rejected} terms checked, min length {args.min_term_length})"
        )

    # 4. Slot ↔ zone alignment
    align_errors, align_warnings = check_slot_zone_alignment(plan, content)
    if align_errors:
        print("✗ Slot ↔ zone alignment")
        for e in align_errors:
            print(f"  ERROR: {e}")
        all_errors.extend(align_errors)
    elif align_warnings:
        print("⚠ Slot ↔ zone alignment")
        for w in align_warnings:
            print(f"  WARN: {w}")
        all_warnings.extend(align_warnings)
    else:
        total_slots = sum(len(s.get("slots", [])) for s in content.get("slides", []))
        print(f"✓ Slot ↔ zone alignment — {total_slots} slot(s) matched to plan zones")

    # 5. Placeholder text (hard fail)
    errors = check_placeholders(content)
    if errors:
        print("✗ Placeholder text")
        for e in errors:
            print(f"  ERROR: {e}")
        all_errors.extend(errors)
    else:
        print("✓ Placeholder text — none found (xxxx/lorem/TBD/click-to-add)")

    # 5b. Formula slots (mathtext + alt)
    formula_errors, formula_warnings = check_formula_slots(plan, content)
    formula_count = sum(
        1 for s in plan.get("slides", [])
        for z in (s.get("layoutSpec") or {}).get("zones", []) or []
        if z.get("type") == "formula"
    )
    if formula_errors:
        print("✗ Formula slots")
        for e in formula_errors:
            print(f"  ERROR: {e}")
        all_errors.extend(formula_errors)
    elif formula_warnings:
        print("⚠ Formula slots")
        for w in formula_warnings:
            print(f"  WARN: {w}")
        all_warnings.extend(formula_warnings)
    elif formula_count:
        print(f"✓ Formula slots — {formula_count} formula(s) parsed and alt-checked")

    # 6. Data point consistency (warning)
    dp_warnings = check_data_point_consistency(content, registry)
    if dp_warnings:
        print("⚠ Data point consistency")
        for w in dp_warnings:
            print(f"  WARN: {w}")
        all_warnings.extend(dp_warnings)
    else:
        rv_count = len(_registry_value_strings(registry))
        if rv_count:
            print(f"✓ Data point consistency — every numeric token traced to {rv_count} registry value(s)")
        else:
            print("ℹ No registry data points to cross-reference")

    # 7. Headline alignment with blueprint
    ha_warnings = check_headline_alignment(content, blueprint)
    if ha_warnings:
        print("⚠ Headline alignment")
        for w in ha_warnings:
            print(f"  WARN: {w}")
        all_warnings.extend(ha_warnings)
    elif blueprint is None:
        print("ℹ Headline alignment skipped (no blueprint loaded)")
    else:
        print("✓ Headline alignment — every title aligned with blueprint headlineMessage")

    # 8. Headline sequence (manual review)
    print_headline_sequence(content, plan)

    # 8a. Modified headlines (informational — Step 6a compression trace, N5)
    print_modified_headlines(content, blueprint)

    # 8b. Self-split slides (informational — Step 6 split contentBody itself, C2)
    print_self_split_slides(content, plan, draft)

    # 9. Content grounding — verification tier distribution
    grounding_errors, grounding_warnings = check_content_grounding(registry)
    if grounding_warnings:
        print("⚠ Content grounding")
        for w in grounding_warnings:
            print(f"  WARN: {w}")
        all_warnings.extend(grounding_warnings)
    else:
        dp_count = len(registry.get("dataPoints", {}))
        if dp_count:
            print(f"✓ Content grounding — {dp_count} data point(s) all have verificationTier")
        else:
            print("ℹ Content grounding — no data points in registry")

    # 10. Confidence threshold — low-confidence precise numbers
    conf_warnings = check_confidence_threshold(content, registry)
    if conf_warnings:
        print("⚠ Confidence threshold")
        for w in conf_warnings:
            print(f"  WARN: {w}")
        all_warnings.extend(conf_warnings)
    else:
        low_conf_count = sum(
            1 for dp in (registry.get("dataPoints", {}).values()
                         if isinstance(registry.get("dataPoints", {}), dict)
                         else registry.get("dataPoints", []))
            if isinstance(dp, dict) and (dp.get("confidence") or 1.0) < DEFAULT_CONFIDENCE_THRESHOLD
        )
        if low_conf_count:
            print(f"✓ Confidence threshold — {low_conf_count} low-confidence point(s) all have qualitativeForm")
        else:
            print("ℹ Confidence threshold — no low-confidence data points")

    # Summary
    total_issues = len(all_errors) + (len(all_warnings) if args.strict else 0)
    if total_issues == 0:
        print("═══ PASS — Step 6 checkpoint validated ═══")
        return 0
    else:
        print(f"═══ FAIL — {len(all_errors)} errors, {len(all_warnings)} warnings ═══")
        return 1


if __name__ == "__main__":
    sys.exit(main())
