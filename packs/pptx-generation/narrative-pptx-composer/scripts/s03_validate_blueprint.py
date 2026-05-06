#!/usr/bin/env python3
"""Step 3 checkpoint validator — s03-presentation-blueprint.json.

Verifies:
  1. totalSlides matches actual slide array length; if
     s01b-query-intent.json carries explicitSignals.slideCountConstraint
     (exact/range), also checks against that target
  2. First slide is cover/opening, last slide is closing/resolution
  3. Every body slide has a non-null headlineMessage (structural slides
     — cover, divider, agenda, executive-summary, recap, appendix —
     are exempt)
  4. transitionOut[N] and transitionIn[N+1] both exist (pair completeness)
  5. narrativeIntent matches content (no data-visualization without data points)
  6. When structuralScaffold.sectionDividers is true, divider slide
     count equals act count (one leading divider per act, including
     Act 1's after cover/agenda)
  7. Every informationHierarchy.cut[] entry has a non-empty `reason`
     so downstream steps don't re-include the item
  8. Slides with contentSource in {document, hybrid} carry source
     traceability — slide-level sourceRef OR every supportingPoint as
     a SourcedPoint object

  Note: narrativeRole sequence coherence with the chosen storytelling
  pattern is left to manual review — patterns vary too widely for a
  canonical machine check.

Usage:
  python s03_validate_blueprint.py <session_dir>
  python s03_validate_blueprint.py . --strict
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Force UTF-8 stdout on Windows so check-mark / cross / warning glyphs
# don't crash the validator on the default cp1252 console.
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass


def load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        text = f.read()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Some files may contain concatenated JSON objects from
        # multiple generation passes — try parsing just the first one
        decoder = json.JSONDecoder()
        obj, _ = decoder.raw_decode(text)
        return obj


def check_slide_count(blueprint: dict, query_intent: dict | None) -> list[str]:
    """totalSlides must match actual slides array; check slideCountConstraint if present.

    Source of truth for slideCountConstraint is
    s01b-query-intent.json → explicitSignals.slideCountConstraint
    (Step 2 is forbidden from carrying this field)."""
    errors = []
    total = blueprint.get("totalSlides", len(blueprint["slides"]))
    actual = len(blueprint["slides"])

    if total != actual:
        errors.append(
            f"totalSlides ({total}) != actual slide count ({actual})"
        )

    if not query_intent:
        return errors
    constraint = (
        query_intent.get("explicitSignals", {}).get("slideCountConstraint")
    )
    if constraint and isinstance(constraint, dict):
        ctype = constraint.get("type")
        if ctype == "exact":
            target = constraint.get("value")
            if target is not None and actual != target:
                errors.append(
                    f"Slide count ({actual}) != slideCountConstraint exact value ({target})"
                )
        elif ctype == "range":
            lo = constraint.get("min", 0)
            hi = constraint.get("max", 999)
            if actual < lo or actual > hi:
                errors.append(
                    f"Slide count ({actual}) outside slideCountConstraint range [{lo}, {hi}]"
                )
    return errors


def check_bookends(blueprint: dict) -> list[str]:
    """First slide = cover/opening, last slide = closing/resolution.
    Single-slide decks are exempt — the one slide serves all roles."""
    errors = []
    slides = blueprint["slides"]
    if not slides:
        errors.append("No slides in blueprint")
        return errors

    # Single-slide deck: skip bookend checks
    if len(slides) == 1:
        return errors

    first = slides[0]
    if first.get("slideType") != "cover":
        errors.append(
            f"First slide ({first['slideId']}) slideType is "
            f"'{first.get('slideType')}', expected 'cover'"
        )
    if first.get("narrativeRole") != "opening":
        errors.append(
            f"First slide ({first['slideId']}) narrativeRole is "
            f"'{first.get('narrativeRole')}', expected 'opening'"
        )

    last = slides[-1]
    if last.get("slideType") != "closing":
        errors.append(
            f"Last slide ({last['slideId']}) slideType is "
            f"'{last.get('slideType')}', expected 'closing'"
        )
    if last.get("narrativeRole") != "resolution":
        errors.append(
            f"Last slide ({last['slideId']}) narrativeRole is "
            f"'{last.get('narrativeRole')}', expected 'resolution'"
        )
    return errors


def check_headline_messages(blueprint: dict) -> list[str]:
    """Every non-cover, non-divider slide must have a non-null headlineMessage."""
    errors = []
    structural_roles = {
        "cover",
        "divider",
        "agenda",
        "executive-summary",
        "recap",
        "appendix",
    }
    for s in blueprint["slides"]:
        if s.get("slideType") in structural_roles:
            continue
        hm = s.get("headlineMessage")
        if hm is None or (isinstance(hm, str) and not hm.strip()):
            errors.append(
                f"{s['slideId']} ({s.get('title', '?')}): "
                f"missing headlineMessage — slide may lack clear purpose"
            )
    return errors


def check_transition_pairs(blueprint: dict) -> list[str]:
    """Adjacent slides must have matching transitionOut/transitionIn pairs."""
    errors = []
    slides = blueprint["slides"]
    for i in range(len(slides) - 1):
        curr = slides[i]
        next_s = slides[i + 1]
        out_val = curr.get("transitionOut")
        in_val = next_s.get("transitionIn")

        if not out_val and curr.get("slideType") != "closing":
            errors.append(
                f"{curr['slideId']}: missing transitionOut "
                f"(next: {next_s['slideId']})"
            )
        if not in_val and next_s.get("slideType") != "cover":
            errors.append(
                f"{next_s['slideId']}: missing transitionIn "
                f"(prev: {curr['slideId']})"
            )
    return errors


def check_breathing_cadence(blueprint: dict) -> list[str]:
    """Every span of 6–8 consecutive body slides must contain at least
    one breathing slide (informationDensity == 'minimal').

    Step 3 owns this cadence; Step 5 may not insert breathing slides.
    See workflow-step3.md § Slide count determination, sanity check #4
    and workflow-step5.md § Rule 3.
    """
    errors: list[str] = []
    body_types = {
        "content_text",
        "content_data",
        "content_mixed",
    }
    body_slides = [
        s for s in blueprint.get("slides", [])
        if s.get("slideType") in body_types
    ]
    if len(body_slides) < 6:
        return errors

    window = 8
    for start in range(0, len(body_slides) - window + 1):
        span = body_slides[start : start + window]
        has_breathing = any(
            (s.get("informationDensity") == "minimal") for s in span
        )
        if not has_breathing:
            ids = ", ".join(s["slideId"] for s in span)
            errors.append(
                f"Breathing-slide cadence violated in body-slide span "
                f"[{ids}]: every 6–8 consecutive body slides must "
                f"contain at least one slide with "
                f"informationDensity == 'minimal'. Either compress an "
                f"existing pivot/callback/setup slide or split a dense "
                f"evidence slide into a setup + detail pair "
                f"(see workflow-step3.md § Slide count determination)."
            )
            break  # one finding per deck is enough; LLM will fix and re-run
    return errors


def check_architecture(blueprint: dict) -> tuple[list[str], list[str]]:
    """Verify the embedded narrative architecture block (Phases 3a/3b).

    - architecture exists
    - coreArgument is a complete, non-trivial claim (>=40 chars, has whitespace,
      doesn't look like a vague topic label)
    - structuralScaffold exists with a non-empty rationale (>=10 chars)
    - actStructure has >= 2 acts
    - openingHook, closingAnchor, interActHandoffs are present (non-empty)
    """
    errors: list[str] = []
    warnings: list[str] = []

    arch = blueprint.get("architecture")
    if not isinstance(arch, dict):
        errors.append(
            "blueprint.architecture is missing or not an object — "
            "Phases 3a/3b must write the embedded architecture block."
        )
        return errors, warnings

    # coreArgument
    core = arch.get("coreArgument")
    if not isinstance(core, str) or not core.strip():
        errors.append("architecture.coreArgument is missing or empty.")
    else:
        text = core.strip()
        if len(text) < 40 or " " not in text:
            errors.append(
                f"architecture.coreArgument looks like a topic label, not a "
                f"falsifiable claim: '{text}'. Rewrite as a complete sentence "
                f"(>=40 chars) that can be argued for or against."
            )

    # structuralScaffold + rationale
    scaffold = arch.get("structuralScaffold")
    if not isinstance(scaffold, dict):
        errors.append(
            "architecture.structuralScaffold is missing — Phase 3b must "
            "record decisions on executive summary, agenda, dividers, recap, "
            "and appendix."
        )
    else:
        rationale = scaffold.get("rationale", "")
        if not isinstance(rationale, str) or len(rationale.strip()) < 10:
            errors.append(
                "architecture.structuralScaffold.rationale is missing or too "
                "short — explain why these structural choices fit the audience "
                "and narrative."
            )

    # actStructure >= 2
    acts = arch.get("actStructure")
    if not isinstance(acts, list) or len(acts) < 2:
        errors.append(
            f"architecture.actStructure must have >= 2 acts "
            f"(found {len(acts) if isinstance(acts, list) else 0})."
        )

    # openingHook / closingAnchor — required strings (Phase 3a sub-task #4)
    for fname in ("openingHook", "closingAnchor"):
        val = arch.get(fname)
        if not isinstance(val, str) or not val.strip():
            errors.append(
                f"architecture.{fname} is missing or empty — Phase 3a "
                f"sub-task #4 requires both bookend beats."
            )

    # interActHandoffs — required (Phase 3a sub-task #3). Accept either a
    # non-empty string or a non-empty list/object describing per-boundary
    # handoff strategies.
    handoffs = arch.get("interActHandoffs")
    if handoffs is None:
        errors.append(
            "architecture.interActHandoffs is missing — Phase 3a sub-task #3 "
            "requires the inter-act handoff strategy."
        )
    elif isinstance(handoffs, str) and not handoffs.strip():
        errors.append("architecture.interActHandoffs is an empty string.")
    elif isinstance(handoffs, (list, dict)) and len(handoffs) == 0:
        errors.append("architecture.interActHandoffs is empty.")

    # contentDomain / imageryDemand — required (Phase 3a sub-task #6).
    # These are read by Step 4 (contentForm) and Step 5b (visualTone
    # propagation). Step 5 may not derive or override them.
    domain = arch.get("contentDomain")
    valid_domains = {
        "technical-instructional",
        "data-analytical",
        "creative-portfolio",
        "general",
    }
    if not isinstance(domain, str) or domain not in valid_domains:
        errors.append(
            "architecture.contentDomain is missing or not one of "
            f"{sorted(valid_domains)} — Phase 3a sub-task #6 must "
            "resolve it."
        )

    demand = arch.get("imageryDemand")
    valid_demands = {"high", "medium", "low", "none"}
    if not isinstance(demand, str) or demand not in valid_demands:
        errors.append(
            "architecture.imageryDemand is missing or not one of "
            f"{sorted(valid_demands)} — Phase 3a sub-task #6 must "
            "resolve it via the cascade in workflow-step3.md."
        )

    return errors, warnings


def _tokenize(text: str) -> set[str]:
    """Lowercase word tokens of length >= 4 — used for fuzzy essential↔message match."""
    import re as _re
    return {w for w in _re.findall(r"[a-zA-Z\u4e00-\u9fff]+", (text or "").lower()) if len(w) >= 4}


def check_essential_to_keymessages(
    blueprint: dict, brief: dict
) -> tuple[list[str], list[str]]:
    """Every essential item in the information hierarchy should map to at
    least one keyMessage in the brief. Token-overlap heuristic — emits
    warnings (not errors) because the LLM may legitimately phrase the
    same concept differently.
    """
    errors: list[str] = []
    warnings: list[str] = []

    arch = blueprint.get("architecture") or {}
    hierarchy = arch.get("informationHierarchy") or {}
    essential = hierarchy.get("essential") or []
    if not essential:
        return errors, warnings

    key_msgs = brief.get("keyMessages") or []
    if not key_msgs:
        warnings.append(
            "brief has no keyMessages — cannot verify essential→keyMessage mapping."
        )
        return errors, warnings

    msg_tokens = [_tokenize(m.get("message", "")) for m in key_msgs]

    for item in essential:
        text = item if isinstance(item, str) else (item.get("item") or item.get("text") or "")
        item_tokens = _tokenize(text)
        if not item_tokens:
            continue
        # Match if any keyMessage shares >= 1 non-stopword token of length >= 4.
        if not any(item_tokens & mt for mt in msg_tokens):
            warnings.append(
                f"essential item '{text[:60]}...' has no token overlap with "
                f"any keyMessage — verify it maps to one (or move to supporting)."
            )

    return errors, warnings


def check_cut_reasons(blueprint: dict) -> list[str]:
    """Every informationHierarchy.cut[] item must be an object with a
    non-empty `reason`. Bare strings are rejected because the reason is
    what prevents downstream steps (Step 4 / Step 6) from re-including
    the cut content."""
    errors: list[str] = []
    arch = blueprint.get("architecture") or {}
    hierarchy = arch.get("informationHierarchy") or {}
    cuts = hierarchy.get("cut")
    if cuts is None:
        return errors  # absence is handled by schema-level required
    if not isinstance(cuts, list):
        errors.append(
            "architecture.informationHierarchy.cut must be an array."
        )
        return errors
    for i, c in enumerate(cuts):
        if not isinstance(c, dict):
            errors.append(
                f"informationHierarchy.cut[{i}] is a bare value "
                f"({type(c).__name__}); must be an object with `item` "
                f"and a non-empty `reason`."
            )
            continue
        item = c.get("item") or "(unnamed)"
        reason = c.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            errors.append(
                f"informationHierarchy.cut[{i}] '{item}' is missing a "
                f"non-empty `reason` — required so downstream steps don't "
                f"re-include this item."
            )
    return errors


def check_source_traceability(blueprint: dict) -> list[str]:
    """For slides with contentSource in {document, hybrid}, require source
    traceability: either slide-level `sourceRef` is non-empty, OR every
    supportingPoint is a SourcedPoint object with a non-empty `sourceRef`.

    Structural slides (cover, divider, agenda, executive-summary, recap,
    appendix) are exempt — their content is structural framing, not a
    source-derived claim.
    """
    errors: list[str] = []
    structural = {
        "cover", "divider", "agenda",
        "executive-summary", "recap", "appendix",
    }
    for s in blueprint.get("slides", []):
        if s.get("slideType") in structural:
            continue
        cs = s.get("contentSource")
        if cs not in ("document", "hybrid"):
            continue

        slide_ref = s.get("sourceRef")
        if isinstance(slide_ref, str) and slide_ref.strip():
            continue  # slide-level reference satisfies traceability

        # Otherwise every supportingPoint must be a SourcedPoint
        pts = s.get("supportingPoints") or []
        if not pts:
            errors.append(
                f"{s.get('slideId', '?')}: contentSource='{cs}' but no "
                f"sourceRef on slide and no supportingPoints to carry one. "
                f"Add a slide-level sourceRef."
            )
            continue
        bad: list[str] = []
        for i, p in enumerate(pts):
            if isinstance(p, dict):
                ref = p.get("sourceRef")
                if not isinstance(ref, str) or not ref.strip():
                    bad.append(f"point[{i}]")
            else:
                # bare string — has no sourceRef at all
                bad.append(f"point[{i}]")
        if bad:
            errors.append(
                f"{s.get('slideId', '?')}: contentSource='{cs}' but "
                f"slide-level sourceRef is empty AND these supportingPoints "
                f"lack sourceRef: {', '.join(bad)}. Set slide.sourceRef OR "
                f"convert supportingPoints to {{point, sourceRef}} objects."
            )
    return errors


def check_divider_symmetry(blueprint: dict) -> tuple[list[str], list[str]]:
    """When structuralScaffold.sectionDividers is true, every act gets a
    leading divider (3b's "divider symmetry" rule). Robust check: just
    count, don't infer act boundaries.

      expected divider count == len(actStructure)

    Equality holds because 3b mandates a leading divider per act,
    including Act 1 (placed after cover/agenda). The check is independent
    of narrativeRole sequencing and slide-to-act mapping (neither is
    represented in the schema), so it cannot misjudge those.

    - count < acts → asymmetric (some acts missing divider) → ERROR
    - count > acts → likely a non-divider slide mistagged as divider → WARN
    - count == 0 with acts >= 2 → ERROR (covered by the < case)
    """
    errors: list[str] = []
    warnings: list[str] = []

    arch = blueprint.get("architecture") or {}
    scaffold = arch.get("structuralScaffold") or {}
    if not scaffold.get("sectionDividers"):
        return errors, warnings

    acts = arch.get("actStructure") or []
    slides = blueprint.get("slides") or []
    expected = len(acts)
    actual = sum(1 for s in slides if s.get("slideType") == "divider")

    if expected < 2:
        # Single-act deck with sectionDividers=true is itself suspect,
        # but it's a 3b decision; surface as a warning.
        if actual > 0:
            warnings.append(
                "structuralScaffold.sectionDividers=true but actStructure "
                "has only one act — dividers are unnecessary."
            )
        return errors, warnings

    if actual < expected:
        errors.append(
            f"Divider symmetry: expected {expected} divider slides "
            f"(one per act in actStructure) but found {actual}. "
            f"Either add leading dividers for the missing acts or set "
            f"structuralScaffold.sectionDividers=false."
        )
    elif actual > expected:
        warnings.append(
            f"Divider symmetry: found {actual} divider slides but "
            f"actStructure has only {expected} acts. Verify no body slide "
            f"is mistagged as slideType='divider'."
        )

    return errors, warnings


def check_narrative_intent_vs_content(blueprint: dict) -> list[str]:
    """narrativeIntent='data-visualization' requires at least one numeric token
    in title or supportingPoints — guards against decorative chart claims with
    no underlying numbers.
    """
    import re as _re
    errors: list[str] = []
    NUMBER_RE = _re.compile(r"\d")
    for s in blueprint.get("slides", []):
        if s.get("narrativeIntent") != "data-visualization":
            continue
        haystack = " ".join(
            [s.get("title") or "", s.get("headlineMessage") or ""]
            + [
                (p if isinstance(p, str) else (p.get("point") or ""))
                for p in (s.get("supportingPoints") or [])
            ]
        )
        if not NUMBER_RE.search(haystack):
            errors.append(
                f"{s.get('slideId', '?')}: narrativeIntent='data-visualization' "
                f"but no numeric values found in title/headline/supportingPoints. "
                f"Either add data points or change narrativeIntent."
            )
    return errors


def print_narrative_flow(blueprint: dict) -> None:
    """Print the narrative role sequence for manual review."""
    print("\n── Narrative Flow ──")
    for s in blueprint["slides"]:
        role = s.get("narrativeRole") or "—"
        st = s.get("slideType", "?")
        hm = s.get("headlineMessage")
        marker = "│" if st not in ("cover", "divider", "closing") else "┃"
        if hm:
            display = hm[:70] + ("…" if len(hm) > 70 else "")
        else:
            display = f"[{st}]"
        print(f"  {marker} {s['slideId']} {role:14s} {display}")
    print("── End ──\n")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Step 3 checkpoint validator for narrative-pptx-composer"
    )
    parser.add_argument("session_dir", type=Path)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    session = args.session_dir.resolve()

    # Load artifacts
    blueprint_path = session / "s03-presentation-blueprint.json"
    if not blueprint_path.exists():
        print(f"FAIL: s03-presentation-blueprint.json not found in {session}")
        return 1
    blueprint = load_json(blueprint_path)

    # Brief is mandatory: Step 2 always runs and writes
    # s02-communication-brief.json. A missing brief means Step 2 was
    # bypassed — fail loud rather than degrading silently and risking
    # incorrect downstream slide-count arbitration.
    brief_path = session / "s02-communication-brief.json"
    if not brief_path.exists():
        print(
            f"FAIL: s02-communication-brief.json not found in {session}. "
            f"Step 2 must always run before this checkpoint."
        )
        return 1
    brief = load_json(brief_path)

    # s01b is the sole source of truth for slideCountConstraint
    # (Step 2 is forbidden from carrying it). Missing s01b means
    # Step 1b was bypassed — fail loud.
    query_intent_path = session / "s01b-query-intent.json"
    if not query_intent_path.exists():
        print(
            f"FAIL: s01b-query-intent.json not found in {session}. "
            f"Step 1b must always run before this checkpoint."
        )
        return 1
    query_intent = load_json(query_intent_path)

    architecture = blueprint.get("architecture")

    print(f"Validating Step 3 checkpoint in: {session.name}")
    print(f"  Slides: {len(blueprint['slides'])}")
    print(f"  Architecture embedded: {architecture is not None}")
    print()

    all_errors: list[str] = []
    all_warnings: list[str] = []

    # 1. Slide count
    errors = check_slide_count(blueprint, query_intent)
    if errors:
        print("✗ Slide count")
        for e in errors:
            print(f"  ERROR: {e}")
        all_errors.extend(errors)
    else:
        print(f"✓ Slide count — {len(blueprint['slides'])} slides")

    # 2. Bookend structure — every deck has a cover/closing pair.
    errors = check_bookends(blueprint)
    if errors:
        print("✗ Bookend structure")
        for e in errors:
            print(f"  ERROR: {e}")
        all_errors.extend(errors)
    else:
        print("✓ Bookend structure — cover/opening → closing/resolution")

    # 3. Headline messages
    errors = check_headline_messages(blueprint)
    if errors:
        print("✗ Headline messages")
        for e in errors:
            print(f"  ERROR: {e}")
        all_errors.extend(errors)
    else:
        content_count = sum(
            1 for s in blueprint["slides"]
            if s.get("slideType") not in ("cover", "divider")
        )
        print(f"✓ Headline messages — {content_count} content slides all have headlines")

    # 4. Transition pairs
    errors = check_transition_pairs(blueprint)
    if errors:
        print("✗ Transition pairs")
        for e in errors:
            print(f"  ERROR: {e}")
        all_errors.extend(errors)
    else:
        print(f"✓ Transition pairs — {len(blueprint['slides']) - 1} pairs complete")

    # 4b. Breathing-slide cadence
    errors = check_breathing_cadence(blueprint)
    if errors:
        print("✗ Breathing-slide cadence")
        for e in errors:
            print(f"  ERROR: {e}")
        all_errors.extend(errors)
    else:
        print("✓ Breathing-slide cadence — every body span has a minimal-density beat")

    # 5. Architecture block (Phases 3a/3b)
    arch_errors, arch_warnings = check_architecture(blueprint)
    if arch_errors:
        print("✗ Architecture block")
        for e in arch_errors:
            print(f"  ERROR: {e}")
        all_errors.extend(arch_errors)
    else:
        print("✓ Architecture block — coreArgument + structuralScaffold + actStructure present")
    if arch_warnings:
        for w in arch_warnings:
            print(f"  WARN: {w}")
        all_warnings.extend(arch_warnings)

    # 6. Essential → keyMessage mapping (warning-level)
    em_errors, em_warnings = check_essential_to_keymessages(blueprint, brief)
    if em_errors:
        print("✗ Essential → keyMessage mapping")
        for e in em_errors:
            print(f"  ERROR: {e}")
        all_errors.extend(em_errors)
    elif em_warnings:
        print("⚠ Essential → keyMessage mapping")
        for w in em_warnings:
            print(f"  WARN: {w}")
        all_warnings.extend(em_warnings)
    else:
        print("✓ Essential → keyMessage mapping")

    # 7. cut[].reason presence
    errors = check_cut_reasons(blueprint)
    if errors:
        print("✗ informationHierarchy.cut reasons")
        for e in errors:
            print(f"  ERROR: {e}")
        all_errors.extend(errors)
    else:
        print("✓ informationHierarchy.cut reasons")

    # 8. source traceability for document/hybrid slides
    errors = check_source_traceability(blueprint)
    if errors:
        print("✗ Source traceability")
        for e in errors:
            print(f"  ERROR: {e}")
        all_errors.extend(errors)
    else:
        print("✓ Source traceability — document/hybrid slides carry sourceRef")

    # 9. Divider symmetry (count-based)
    sym_errors, sym_warnings = check_divider_symmetry(blueprint)
    if sym_errors:
        print("✗ Divider symmetry")
        for e in sym_errors:
            print(f"  ERROR: {e}")
        all_errors.extend(sym_errors)
    elif sym_warnings:
        print("⚠ Divider symmetry")
        for w in sym_warnings:
            print(f"  WARN: {w}")
        all_warnings.extend(sym_warnings)
    else:
        print("✓ Divider symmetry")

    # 10. narrativeIntent vs content
    errors = check_narrative_intent_vs_content(blueprint)
    if errors:
        print("✗ narrativeIntent vs content")
        for e in errors:
            print(f"  ERROR: {e}")
        all_errors.extend(errors)
    else:
        print("✓ narrativeIntent vs content — data-visualization slides carry numeric content")

    # Narrative flow for review
    print_narrative_flow(blueprint)

    # Summary
    total = len(all_errors) + (len(all_warnings) if args.strict else 0)
    if total == 0:
        print("═══ PASS — Step 3 checkpoint validated ═══")
        return 0
    else:
        print(
            f"═══ FAIL — {len(all_errors)} errors, "
            f"{len(all_warnings)} warnings ═══"
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
