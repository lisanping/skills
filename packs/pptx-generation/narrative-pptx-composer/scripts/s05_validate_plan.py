#!/usr/bin/env python3
"""Step 5 checkpoint validator — s05-slide-visual-design.json + s05b-style-policy.json.

Template-free redesign. Verifies:
  1. Every blueprint slide has a matching entry in s05-slide-visual-design.json
  2. All dividers share the same layoutPattern
  3. Dividers use same layoutPattern as structuralFamily.dividerPattern (consistency)
  4. Every slide has a valid layoutSpec with typed zones
  5. Geometric validation: overlap, margins, bounds
  6. s05b-style-policy.json contains all required fields (no mode)
  7. visualTone has all required dimensions (D0-D7 + designAmbition passthrough)
  8. Body slides use structured designRationale (narrative + narrativeLink
     + focalPoint + eyePath + aestheticMove). Legacy free-form `aesthetic`
     field is no longer accepted.
  9. Universal Design Floor quotas (variety, hero cadence, color, typography)
 10. Image resources exist and are not reused across slides
 11. Hard-ban: no centered/short horizontal dash directly beneath title text

Usage:
  python s05_validate_plan.py <session_dir>
  python s05_validate_plan.py . --strict
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

# Force UTF-8 stdout on Windows so the check-mark / cross / warning glyphs
# don't crash the validator on the default cp1252 console.
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

SLIDE_W = 10.0
SLIDE_H = 5.625
MIN_MARGIN = 0.5


def load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def resolve_coord(val, dimension: float) -> float:
    """Resolve a layout coordinate to inches.

    Coordinate convention (since v2 — was percent-by-default before):
      - bare number (int/float) → absolute inches
      - string "<N>in"          → absolute inches (explicit; backward compat)
      - string "<N>%"           → percent of `dimension` (new explicit syntax)
      - bare numeric string     → absolute inches (treated like a number)

    Rationale: the schema and example.json have always shown coordinates
    as inches (e.g. `"w": 8.0` on a 10-inch slide). Treating bare numbers
    as percent silently turned every body-slide layout into a postage
    stamp and made geometry/UDF checks meaningless. Bare numbers now
    mean inches; use the explicit "<N>%" suffix when percent is intended.
    """
    if isinstance(val, str):
        s = val.strip()
        if s.endswith("in"):
            return float(s[:-2])
        if s.endswith("%"):
            return (float(s[:-1]) / 100.0) * dimension
        try:
            return float(s)
        except ValueError as exc:
            raise ValueError(f"Unresolvable coord value: {val!r}") from exc
    if isinstance(val, (int, float)):
        return float(val)
    raise ValueError(f"Unsupported coord type: {type(val).__name__} ({val!r})")


def resolve_zone(zone: dict, slide_w: float, slide_h: float) -> dict:
    """Return zone with x/y/w/h resolved to inches."""
    return {
        **zone,
        "x": resolve_coord(zone.get("x", 0), slide_w),
        "y": resolve_coord(zone.get("y", 0), slide_h),
        "w": resolve_coord(zone.get("w", 0), slide_w),
        "h": resolve_coord(zone.get("h", 0), slide_h),
    }


def check_blueprint_coverage(plan: dict, blueprint: dict) -> list[str]:
    """Every blueprint slide must have a matching slide-visual-design entry."""
    bp_ids = {s["slideId"] for s in blueprint["slides"]}
    plan_ids = {s.get("taskId") or s.get("slideId") for s in plan["slides"]}
    errors = []
    missing = bp_ids - plan_ids
    extra = plan_ids - bp_ids
    if missing:
        errors.append(f"Blueprint slides missing from plan: {sorted(missing)}")
    if extra:
        errors.append(f"Plan entries not in blueprint: {sorted(extra)}")
    return errors


def check_divider_consistency(plan: dict) -> list[str]:
    """All dividers must share the same layoutPattern (errors)."""
    dividers = [s for s in plan["slides"] if s.get("slideType") == "divider"]
    errors = []
    if len(dividers) < 2:
        return errors
    patterns = {s.get("layoutPattern") for s in dividers}
    if len(patterns) > 1:
        detail = [f"{s.get('taskId') or s.get('slideId', '?')}={s.get('layoutPattern')}" for s in dividers]
        errors.append(f"Dividers use inconsistent layoutPatterns: {detail}")
    return errors


# (Earlier this file had a near-duplicate `check_role_layout_consistency`
# that re-checked dividers and produced the same warning. It was removed —
# `check_divider_consistency` above is the single source of truth.)


def check_layout_spec(plan: dict) -> list[str]:
    """Every slide must have a layoutSpec with typed zones — bookends included."""
    valid_types = {"text", "shape", "chart", "image", "icon", "formula"}
    errors = []
    for s in plan["slides"]:
        tid = s.get("taskId", "?")
        spec = s.get("layoutSpec")
        if spec is None:
            errors.append(f"{tid}: missing layoutSpec")
            continue
        if "zones" not in spec or not spec["zones"]:
            errors.append(f"{tid}: layoutSpec has no zones")
            continue
        for i, zone in enumerate(spec["zones"]):
            prefix = f"{tid}/zone[{i}]({zone.get('role', '?')})"
            # Required fields
            for field in ("role", "type", "x", "y", "w", "h"):
                if field not in zone:
                    errors.append(f"{prefix}: missing '{field}'")
            # Type validation
            ztype = zone.get("type", "")
            if ztype and ztype not in valid_types:
                errors.append(f"{prefix}: invalid type '{ztype}'")
    return errors


def _rects_overlap(a: dict, b: dict) -> bool:
    """Check if two zone rectangles overlap (non-trivially)."""
    eps = 0.02  # tolerance for touching edges
    ax1, ay1 = a["x"], a["y"]
    ax2, ay2 = ax1 + a["w"], ay1 + a["h"]
    bx1, by1 = b["x"], b["y"]
    bx2, by2 = bx1 + b["w"], by1 + b["h"]
    return ax1 < bx2 - eps and ax2 > bx1 + eps and ay1 < by2 - eps and ay2 > by1 + eps


def check_geometry(plan: dict, slide_w: float = SLIDE_W, slide_h: float = SLIDE_H) -> tuple[list[str], list[str]]:
    """Check zones are within slide bounds and text zones don't overlap.

    Zone coordinates are absolute inches by default. Strings ending in
    "in" are also inches; strings ending in "%" are percent of the slide
    dimension. See `resolve_coord` for the full convention.

    Returns (errors, warnings). Errors: bounds violations and text-zone
    overlaps (hard failures). Warnings: image/non-decorative-shape
    overlaps tighter than `IMAGE_OVERLAP_TOLERANCE_IN` — these are
    visually crowded but not broken (see retrospective P2-9).
    """
    errors = []
    warnings: list[str] = []
    IMAGE_OVERLAP_TOLERANCE_IN = 0.10
    DECORATIVE_ROLE_TOKENS = (
        "scrim", "stripe", "bar", "ring", "divider", "band-bg",
        "card-bg", "footer", "thin", "accent",
    )

    def is_decorative_shape(zone: dict) -> bool:
        if zone.get("type") != "shape":
            return False
        role = (zone.get("role") or "").lower()
        return any(tok in role for tok in DECORATIVE_ROLE_TOKENS)
    for s in plan["slides"]:
        tid = s.get("taskId", "?")
        spec = s.get("layoutSpec")
        if not spec or "zones" not in spec:
            continue
        try:
            resolved = [resolve_zone(z, slide_w, slide_h) for z in spec["zones"]]
        except ValueError as exc:
            errors.append(f"{tid}: coord resolution failed — {exc}")
            continue
        for zone in resolved:
            role = zone.get("role", "?")
            x, y, w, h = zone["x"], zone["y"], zone["w"], zone["h"]
            # Bounds check (in inches)
            if x + w > slide_w + 0.01:
                errors.append(
                    f"{tid}/{role}: exceeds slide width "
                    f"(x={x:.2f} + w={w:.2f} = {x+w:.2f} > {slide_w})"
                )
            if y + h > slide_h + 0.01:
                errors.append(
                    f"{tid}/{role}: exceeds slide height "
                    f"(y={y:.2f} + h={h:.2f} = {y+h:.2f} > {slide_h})"
                )
        # Overlap check for text zones only (hard error)
        text_zones = [z for z in resolved if z.get("type") == "text"]
        for i in range(len(text_zones)):
            for j in range(i + 1, len(text_zones)):
                if _rects_overlap(text_zones[i], text_zones[j]):
                    errors.append(
                        f"{tid}: text zones '{text_zones[i].get('role')}' and "
                        f"'{text_zones[j].get('role')}' overlap"
                    )

        # Light overlap check for image / content shape collisions.
        # We only flag image-vs-image, image-vs-content-shape, and
        # content-shape-vs-content-shape overlaps. Decorative shapes
        # (accent bars, scrims, card backgrounds, dividers) are
        # intentionally allowed to underlay other elements.
        content_visuals = [
            z for z in resolved
            if z.get("type") == "image"
            or (z.get("type") == "shape" and not is_decorative_shape(z))
        ]
        for i in range(len(content_visuals)):
            for j in range(i + 1, len(content_visuals)):
                a, b = content_visuals[i], content_visuals[j]
                # Use a stricter tolerance for non-text overlaps so very
                # small touching/overlap doesn't flood with warnings.
                ax2, ay2 = a["x"] + a["w"], a["y"] + a["h"]
                bx2, by2 = b["x"] + b["w"], b["y"] + b["h"]
                ix = max(0.0, min(ax2, bx2) - max(a["x"], b["x"]))
                iy = max(0.0, min(ay2, by2) - max(a["y"], b["y"]))
                if ix > IMAGE_OVERLAP_TOLERANCE_IN and iy > IMAGE_OVERLAP_TOLERANCE_IN:
                    warnings.append(
                        f"{tid}: visuals '{a.get('role')}' ({a.get('type')}) "
                        f"and '{b.get('role')}' ({b.get('type')}) overlap by "
                        f"{ix:.2f}in × {iy:.2f}in — review for crowding"
                    )
    return errors, warnings


def check_banned_under_title_short_rules(
    plan: dict,
    slide_w: float = SLIDE_W,
    slide_h: float = SLIDE_H,
) -> list[str]:
    """Hard-fail centered/short horizontal rules directly beneath titles.

    Guardrail alignment (design-guardrails.md):
      - banned: decorative short/centered horizontal dash beneath title text
      - allowed: full-width hairline tied to layout grid, left vertical accent bar

    Heuristic:
      * shape zone with thin horizontal geometry (w >= 4*h, h <= 0.12in)
      * not full-width (w < 75% of slide width)
      * located directly below a title/headline text zone with meaningful
        horizontal overlap.
    """
    errors: list[str] = []

    TITLE_ROLE_TOKENS = ("title", "headline")

    for s in plan.get("slides", []):
        tid = s.get("taskId", "?")
        zones = (s.get("layoutSpec") or {}).get("zones") or []
        if not zones:
            continue

        try:
            resolved = [resolve_zone(z, slide_w, slide_h) for z in zones]
        except ValueError:
            # Geometry check already reports coordinate failures.
            continue

        title_zones = []
        for z in resolved:
            if z.get("type") != "text":
                continue
            role = (z.get("role") or "").lower()
            if any(tok in role for tok in TITLE_ROLE_TOKENS):
                title_zones.append(z)

        if not title_zones:
            continue

        for z in resolved:
            if z.get("type") != "shape":
                continue

            role = (z.get("role") or "?").lower()
            x = z["x"]
            y = z["y"]
            w = z["w"]
            h = z["h"]

            if w <= 0 or h <= 0:
                continue

            is_horizontal = w >= (4.0 * h)
            is_short = w < (0.75 * slide_w)
            is_thin = h <= 0.12
            if not (is_horizontal and is_short and is_thin):
                continue

            # Keep only "under-title" candidates:
            # shape sits shortly below the title and overlaps title width.
            near_title = False
            z_x2 = x + w
            for tz in title_zones:
                tz_x = tz["x"]
                tz_x2 = tz_x + tz["w"]
                tz_bottom = tz["y"] + tz["h"]
                vertical_gap = y - tz_bottom
                overlap = max(0.0, min(z_x2, tz_x2) - max(x, tz_x))
                overlap_ratio = overlap / max(0.01, min(w, tz["w"]))
                if -0.05 <= vertical_gap <= 0.45 and overlap_ratio >= 0.35:
                    near_title = True
                    break

            # Role hint catches explicit title-rule naming; still require
            # horizontal/thin/short geometry to avoid false positives.
            role_hints_title_rule = (
                ("title" in role or "headline" in role)
                and any(tok in role for tok in ("rule", "bar", "dash", "underline"))
            )

            if near_title or role_hints_title_rule:
                errors.append(
                    f"{tid}/{z.get('role', '?')}: banned decorative short horizontal "
                    f"under-title rule (x={x:.2f}, y={y:.2f}, w={w:.2f}, h={h:.2f}). "
                    f"Use whitespace, a full-width hairline, or a left vertical accent bar."
                )

    return errors


def check_palette_token_usage(plan: dict, policy: dict) -> list[str]:
    """Warn when zones/backgrounds use raw hex instead of palette tokens.

    Catches the failure mode where the LLM hard-codes a color (e.g.
    `"fill": "FF6B35"`) instead of referencing a palette token
    (`"fill": "accent"`). Raw hex skips theme propagation and breaks
    palette swaps in branded variants.
    """
    import re as _re
    warnings: list[str] = []
    palette_tokens = set((policy.get("palette") or {}).keys())
    hex_re = _re.compile(r"^#?[0-9A-Fa-f]{6}$")

    def is_token(value) -> bool:
        if not isinstance(value, str):
            return True  # numbers/None handled elsewhere
        v = value.strip()
        if not v:
            return True
        if v in palette_tokens:
            return True
        # Tolerate gradient names and a few well-known structural keywords
        if v in {"transparent", "inherit", "default", "none"}:
            return True
        return not hex_re.match(v)

    for s in plan.get("slides", []):
        tid = s.get("taskId", "?")
        spec = s.get("layoutSpec", {})
        bg = spec.get("background")
        if isinstance(bg, dict):
            for key in ("color", "tint", "base"):
                if not is_token(bg.get(key)):
                    warnings.append(
                        f"{tid}: background.{key}={bg.get(key)!r} is raw hex; "
                        f"use palette token ({sorted(palette_tokens)})"
                    )
            for c in bg.get("colors", []) or []:
                if not is_token(c):
                    warnings.append(
                        f"{tid}: background.colors contains raw hex {c!r}; "
                        f"use palette tokens"
                    )
        for z in spec.get("zones", []):
            for key in ("fill", "color", "stroke", "background"):
                v = z.get(key)
                if isinstance(v, str) and not is_token(v):
                    warnings.append(
                        f"{tid}/{z.get('role', '?')}.{key}={v!r} is raw hex; "
                        f"use palette token"
                    )
    return warnings


def check_style_policy(policy: dict) -> list[str]:
    """s05b-style-policy.json must contain all required fields."""
    errors = []
    # Palette with direct hex colors
    palette = policy.get("palette")
    if not palette:
        errors.append("style-policy missing 'palette'")
    else:
        required_colors = {"primary", "background", "text"}
        missing = required_colors - set(palette.keys())
        if missing:
            errors.append(f"palette missing keys: {sorted(missing)}")
        # Check for new recommended tokens (warning only)
        recommended = {"accent2", "surface", "divider"}
        missing_rec = recommended - set(palette.keys())
        # Not enforced as errors for backward compat
        # Check hex format (no #)
        for key, val in palette.items():
            if isinstance(val, str) and val.startswith("#"):
                errors.append(f"palette.{key}: hex color must not start with '#'")

    # Typography — accept both old flat format and new scale format
    typo = policy.get("typography")
    if not typo:
        errors.append("style-policy missing 'typography'")
    else:
        for field in ("headingFont", "bodyFont"):
            if field not in typo:
                errors.append(f"typography missing '{field}'")
        # Accept either old flat sizes or new scale object
        has_scale = "scale" in typo
        has_flat = "bodySize" in typo
        if not has_scale and not has_flat:
            errors.append("typography missing 'scale' object or legacy 'bodySize' field")
        if has_scale:
            scale = typo["scale"]
            for token in ("display", "heading1", "heading2", "body", "caption"):
                if token not in scale:
                    errors.append(f"typography.scale missing '{token}'")

    # Spacing in inches
    spacing = policy.get("spacing")
    if not spacing:
        errors.append("style-policy missing 'spacing'")
    elif "marginEMU" in spacing:
        errors.append("spacing uses EMU — must use inches (marginInches)")

    # designLanguage
    if "designLanguage" not in policy:
        errors.append("style-policy missing 'designLanguage'")

    return errors


def check_visual_tone(policy: dict) -> list[str]:
    """visualTone must contain all required dimensions.

    Three categories:
      - Derived dimensions (D1-D6): computed by Step 5b from content signals
      - Annotation dimensions (D0, D7): detected/composed by 6b, consumed downstream
      - Passthrough parameter: designAmbition (copied from aestheticSignals)
    """
    required_dims = {
        # D0 — annotation (content domain detection)
        "contentDomain",
        # D1–D6 — derived dimensions
        "register",
        "colorTemperature",
        "whitespaceRhythm",
        "contrastStrategy",
        "impactLevels",
        "imageryGuidance",
        # D7 — annotation (rhythm arc per act)
        "rhythmArc",
        # Passthrough from aestheticSignals (not a 6b derivation)
        "designAmbition",
    }
    errors = []

    vt = policy.get("visualTone")
    if vt is None:
        errors.append("style-policy missing 'visualTone' object")
        return errors

    missing = required_dims - set(vt.keys())
    if missing:
        errors.append(f"visualTone missing dimensions: {sorted(missing)}")

    ambition = vt.get("designAmbition")
    if ambition is not None and ambition not in {"expressive", "restrained"}:
        errors.append(
            f"visualTone.designAmbition must be 'expressive' or 'restrained', got '{ambition}'"
        )

    ct = vt.get("colorTemperature", {})
    if isinstance(ct, dict):
        # accentProgression can be nested under colorTemperature or at visualTone top level
        has_progression = "accentProgression" in ct or "accentProgression" in vt
        if not has_progression:
            errors.append("visualTone.colorTemperature missing 'accentProgression' (or visualTone.accentProgression)")

    wr = vt.get("whitespaceRhythm", {})
    if isinstance(wr, dict) and "perAct" not in wr:
        errors.append("visualTone.whitespaceRhythm missing 'perAct'")

    il = vt.get("impactLevels", {})
    if isinstance(il, dict):
        for key in ("cover", "closing"):
            if key not in il:
                errors.append(f"visualTone.impactLevels missing '{key}'")

    return errors


def check_structural_family(plan: dict) -> list[str]:
    """structuralFamily must exist with required fields; dividerPattern must match all dividers."""
    errors = []
    sf = plan.get("structuralFamily")
    if sf is None:
        # Not enforced as hard error for backward compat — warn instead
        return ["structuralFamily not declared (recommended for visual consistency)"]

    required = {"sharedMotif", "coverTreatment", "closingTreatment", "dividerPattern", "motifRationale"}
    missing = required - set(sf.keys())
    if missing:
        errors.append(f"structuralFamily missing fields: {sorted(missing)}")

    divider_pattern = sf.get("dividerPattern", "")
    if divider_pattern:
        dividers = [s for s in plan.get("slides", []) if s.get("slideType") == "divider"]
        for d in dividers:
            if d.get("layoutPattern") != divider_pattern:
                errors.append(
                    f"{d.get('taskId', '?')}: layoutPattern '{d.get('layoutPattern')}' "
                    f"does not match structuralFamily.dividerPattern '{divider_pattern}'"
                )

    rationale = sf.get("motifRationale", "")
    if isinstance(rationale, str) and len(rationale.strip()) < 10:
        errors.append("structuralFamily.motifRationale is too short — must explain why this motif was chosen")

    return errors


def check_bookend_signature(plan: dict) -> tuple[list[str], list[str]]:
    """structuralFamily.bookendSignature is recommended (warning when absent).

    When present, validate field shape AND check that at least one
    decoration / shape zone role token appears on both the cover and
    the closing slide — this prevents the rhyme from being a paper
    claim. Returns (errors, warnings).

    See workflow-step5.md § Bookend signature for the contract.
    """
    errors: list[str] = []
    warnings: list[str] = []

    sf = plan.get("structuralFamily") or {}
    sig = sf.get("bookendSignature")

    if sig is None:
        warnings.append(
            "structuralFamily.bookendSignature is not declared — cover ↔ closing rhyme is implicit. "
            "Declaring it (rhyme + coverExpression + closingExpression + designIntent) makes the deck's "
            "two highest-impact frames answer each other; see workflow-step5.md § Bookend signature."
        )
        return errors, warnings

    if not isinstance(sig, dict):
        errors.append(
            f"structuralFamily.bookendSignature must be an object, got {type(sig).__name__}"
        )
        return errors, warnings

    # Field-shape checks (mirror schema minLengths so the LLM gets a
    # readable error before pydantic / jsonschema would catch it).
    field_specs = (
        ("rhyme", 3),
        ("coverExpression", 10),
        ("closingExpression", 10),
        ("designIntent", 20),
    )
    for field, min_len in field_specs:
        val = sig.get(field)
        if not isinstance(val, str) or len(val.strip()) < min_len:
            errors.append(
                f"structuralFamily.bookendSignature.{field} must be a string of "
                f"≥ {min_len} chars (got: {val!r})"
            )

    # Structural overlap check: cover and closing must share at least
    # one decoration / shape zone role token. Without this, the rhyme
    # is a textual claim with nothing in the geometry to honor it.
    NON_DECORATIVE_ROLES = {
        "title", "subtitle", "headline", "body", "footnote", "footer",
        "caption", "label", "page-number", "speaker-note",
    }

    def _decoration_roles(slide: dict) -> set[str]:
        roles: set[str] = set()
        for z in slide.get("layoutSpec", {}).get("zones", []):
            ztype = z.get("type")
            role = (z.get("role") or "").strip().lower()
            if not role:
                continue
            # text zones with structural roles don't count as decoration
            if ztype == "text" and role in NON_DECORATIVE_ROLES:
                continue
            # Only shape / image / icon roles, plus text zones with
            # decorative role tokens, qualify as visual rhyme carriers.
            if ztype in {"shape", "image", "icon"} or role not in NON_DECORATIVE_ROLES:
                roles.add(role)
        return roles

    cover = next(
        (s for s in plan.get("slides", []) if s.get("slideType") == "cover"),
        None,
    )
    closing = next(
        (s for s in plan.get("slides", []) if s.get("slideType") == "closing"),
        None,
    )

    if cover is None or closing is None:
        # Can't check overlap if one of the bookends is missing; the
        # blueprint-coverage check will flag the missing slide elsewhere.
        return errors, warnings

    cover_roles = _decoration_roles(cover)
    closing_roles = _decoration_roles(closing)
    shared_roles = cover_roles & closing_roles

    if not shared_roles:
        # Token-level fallback: split each role on '-' / '_' and look
        # for any shared token (≥ 4 chars to avoid noise like "bg" / "tr").
        def _tokenize(roles: set[str]) -> set[str]:
            out: set[str] = set()
            for r in roles:
                for tok in r.replace("_", "-").split("-"):
                    if len(tok) >= 4:
                        out.add(tok)
            return out

        cover_toks = _tokenize(cover_roles)
        closing_toks = _tokenize(closing_roles)
        shared_toks = cover_toks & closing_toks
        if not shared_toks:
            errors.append(
                "structuralFamily.bookendSignature is declared but cover and closing share "
                "no decoration / shape zone role token. The rhyme must be visible in the geometry, "
                f"not only in prose. cover roles={sorted(cover_roles)}, "
                f"closing roles={sorted(closing_roles)}."
            )

    return errors, warnings


def check_emphasis_and_rationale(plan: dict) -> list[str]:
    """Every slide should have emphasis and designRationale fields.

    Body-slide rationale shape (object form) is checked here only at the
    structural level — `narrative` is the one always-required prose field.
    The richer structural fields (narrativeLink, focalPoint, eyePath,
    aestheticMove) are validated by `check_designer_rationale_v2`.
    """
    valid_emphasis = {"high", "standard", "low"}
    errors = []
    warnings = []

    for s in plan.get("slides", []):
        tid = s.get("taskId", "?")

        # emphasis field
        emphasis = s.get("emphasis")
        if emphasis is None:
            errors.append(f"{tid}: missing 'emphasis' field")
        elif emphasis not in valid_emphasis:
            errors.append(f"{tid}: invalid emphasis '{emphasis}' (must be high/standard/low)")

        # designRationale field
        rationale = s.get("designRationale")
        role = s.get("slideType", "")
        is_structural = role in {"cover", "closing", "divider"}
        if rationale is None:
            errors.append(f"{tid}: missing 'designRationale'")
        elif isinstance(rationale, str):
            if not rationale.strip():
                errors.append(f"{tid}: empty 'designRationale'")
            elif not is_structural:
                errors.append(
                    f"{tid}: body slide uses string designRationale — must be the "
                    f"structured object form (narrative + narrativeLink + focalPoint "
                    f"+ eyePath + aestheticMove)"
                )
        elif isinstance(rationale, dict):
            narrative = rationale.get("narrative", "")
            if not isinstance(narrative, str) or not narrative.strip():
                errors.append(f"{tid}: designRationale.narrative missing or empty")

    return errors + warnings


# ──────────────────────────────────────────────────────────────────────
# Per-slide rationale v2 — focal point / eye path / aesthetic move
# ──────────────────────────────────────────────────────────────────────

_RATIONALE_BANNED_FOCAL = {
    "clean", "professional", "balanced", "modern", "nice", "good",
    "elegant", "minimal", "simple",
}
_RATIONALE_VALID_AXES = {
    "layout", "color", "form", "scale", "contrast", "type", "motion-implied",
}
_RATIONALE_STOPWORDS = {
    "this", "that", "with", "from", "into", "have", "will", "must", "more",
    "most", "than", "some", "what", "when", "where", "which", "their", "there",
    "would", "should", "could", "about", "these", "those", "your", "ours",
    "them", "they", "been", "were", "such",
}


def check_designer_rationale_v2(plan: dict, blueprint: dict) -> tuple[list[str], list[str]]:
    """Body-slide rationale must engage the four designer questions.

    Per simplified plan B (no designThesis dependency) — every body slide's
    designRationale object MUST carry:
      - narrativeLink: anchored to either narrativeRole or a content word
        (>=4 chars) from the blueprint headlineMessage for this slide
      - focalPoint: a concrete visual element (not generic adjectives)
      - eyePath: 2–4 ordered visual stops
      - aestheticMove: structured {move, axes, reason}

    The legacy `aesthetic` string field is no longer accepted —
    `aestheticMove` is required.

    **`emphasis: "low"` relaxation (S6).** Low-emphasis body slides
    may simplify `focalPoint` (slot-name accepted, generic-token
    check skipped) and `eyePath` (length 1 accepted as a single-stop
    list). `narrativeLink` and `aestheticMove` stay mandatory.
    Standard / high-emphasis slides keep the full contract.
    """
    import re as _re

    errors: list[str] = []
    warnings: list[str] = []

    blueprint_by_id = {
        s.get("slideId"): s for s in blueprint.get("slides", []) if s.get("slideId")
    }

    for s in plan.get("slides", []):
        tid = s.get("taskId", "?")
        role = s.get("slideType", "")
        if role in {"cover", "closing", "divider"}:
            continue
        r = s.get("designRationale")
        if not isinstance(r, dict):
            # structural failures already surfaced by check_emphasis_and_rationale
            continue

        is_low_emphasis = (s.get("emphasis") == "low")

        # ── narrativeLink ──
        nl = (r.get("narrativeLink") or "").strip()
        if not nl:
            errors.append(f"{tid}: designRationale.narrativeLink missing or empty")
        else:
            nl_lower = nl.lower()
            anchored = False
            narrative_role = (s.get("narrativeRole") or "").lower()
            if narrative_role and narrative_role in nl_lower:
                anchored = True
            else:
                bp = blueprint_by_id.get(tid, {})
                headline = (bp.get("headlineMessage") or "").lower()
                content_words = [
                    w for w in _re.findall(r"[a-z]{4,}", headline)
                    if w not in _RATIONALE_STOPWORDS
                ]
                for w in content_words:
                    if w in nl_lower:
                        anchored = True
                        break
            if not anchored:
                errors.append(
                    f"{tid}: designRationale.narrativeLink does not reference the "
                    f"slide's narrativeRole or any content word from its "
                    f"headlineMessage — link must explicitly anchor to this "
                    f"slide's narrative purpose, not generic phrasing"
                )

        # ── focalPoint ──
        fp = (r.get("focalPoint") or "").strip()
        if not fp:
            errors.append(f"{tid}: designRationale.focalPoint missing or empty")
        elif not is_low_emphasis:
            # Generic-token check applies only to standard/high emphasis;
            # low-emphasis slides may use slot names like "primary text zone".
            tokens = [t for t in _re.findall(r"[a-z]+", fp.lower())]
            if tokens and all(t in _RATIONALE_BANNED_FOCAL for t in tokens):
                errors.append(
                    f"{tid}: designRationale.focalPoint='{fp}' is generic — "
                    f"name a concrete visual element (e.g. 'central architecture "
                    f"diagram', 'left-side stat block')"
                )

        # ── eyePath ──
        ep = r.get("eyePath")
        if not isinstance(ep, list):
            errors.append(
                f"{tid}: designRationale.eyePath must be a list of 2–4 strings "
                f"(or a single-entry list when emphasis='low')"
            )
        elif is_low_emphasis:
            # Low-emphasis slides may collapse to a single visual stop.
            if not (1 <= len(ep) <= 4):
                errors.append(
                    f"{tid}: designRationale.eyePath length {len(ep)} "
                    f"(must be 1–4 for emphasis='low')"
                )
            elif not all(isinstance(x, str) and x.strip() for x in ep):
                errors.append(
                    f"{tid}: designRationale.eyePath has empty or non-string entries"
                )
        else:
            if not (2 <= len(ep) <= 4):
                errors.append(
                    f"{tid}: designRationale.eyePath length {len(ep)} (must be 2–4)"
                )
            elif not all(isinstance(x, str) and x.strip() for x in ep):
                errors.append(
                    f"{tid}: designRationale.eyePath has empty or non-string entries"
                )

        # ── aestheticMove ──
        am = r.get("aestheticMove")
        if not isinstance(am, dict):
            errors.append(
                f"{tid}: designRationale.aestheticMove missing — must be an "
                f"object with move/axes/reason"
            )
        else:
            if not (am.get("move") or "").strip():
                errors.append(f"{tid}: aestheticMove.move missing or empty")
            axes = am.get("axes")
            if not isinstance(axes, list) or not (1 <= len(axes) <= 3):
                errors.append(
                    f"{tid}: aestheticMove.axes must be a list of 1–3 entries"
                )
            else:
                bad = [a for a in axes if a not in _RATIONALE_VALID_AXES]
                if bad:
                    errors.append(
                        f"{tid}: aestheticMove.axes contains invalid entries "
                        f"{bad} (valid: {sorted(_RATIONALE_VALID_AXES)})"
                    )
            if not (am.get("reason") or "").strip():
                errors.append(f"{tid}: aestheticMove.reason missing or empty")
        # Legacy `aesthetic` string field is no longer accepted —
        # `aestheticMove` is required.

    return errors, warnings


def check_image_resources(plan: dict, session_dir: Path) -> tuple[list[str], list[str]]:
    """Validate image zones and image-typed backgrounds.

    For `source: "user-media"` (default): zone must point to an existing
    file via `src` or `path`. No file may be reused across slides.

    For `source: "generated"`: an `imageRequest` block (with `id` and
    `prompt` >= 30 chars) and a `fallback` block are MANDATORY.
    `path` may be null pre-Step-6f and resolved (or absent on failure)
    after generation. Generated images are exempt from the no-reuse
    rule (the image generator may legitimately produce variants of a
    shared motif).

    Image-typed `background` follows the same rules at the slide level.

    Aspect-ratio match (mandatory for source='generated'):
        |zone_w/zone_h - imageRequest_w/imageRequest_h| / (zone_w/zone_h)
        must be <= ASPECT_TOLERANCE. Mismatch lets add_image_safe
        letterbox the picture inside an oversized zone, leaving large
        empty card regions (retrospective i2).
    """
    ASPECT_TOLERANCE = 0.10

    errors: list[str] = []
    warnings: list[str] = []
    image_usage: dict[str, list[str]] = defaultdict(list)
    # Detect post-6f state: if `imageGenerationLog` exists at deck level,
    # generation has run and every `source: "generated"` zone must be
    # resolved (path exists) OR explicitly marked `fallbackApplied: true`.
    post_6f = isinstance(plan.get("imageGenerationLog"), dict)

    def _check_aspect(tid: str, role: str, req: dict, zone_w, zone_h) -> None:
        """Compare zone aspect to imageRequest aspect; error on >10% drift.

        Skips when zone or request dimensions are missing/zero. Backgrounds
        live on the slide (full canvas) — caller passes slide_w/slide_h.
        """
        rw = req.get("width")
        rh = req.get("height")
        if not (isinstance(rw, (int, float)) and isinstance(rh, (int, float))):
            return  # already warned/erred in width/height block
        if rw <= 0 or rh <= 0:
            return
        try:
            zw = float(zone_w)
            zh = float(zone_h)
        except (TypeError, ValueError):
            return
        if zw <= 0 or zh <= 0:
            return
        zone_aspect = zw / zh
        req_aspect = rw / rh
        drift = abs(zone_aspect - req_aspect) / zone_aspect
        if drift > ASPECT_TOLERANCE:
            errors.append(
                f"{tid}/{role}: zone aspect {zw:.2f}:{zh:.2f} ({zone_aspect:.2f}) "
                f"differs from imageRequest aspect {rw}x{rh} ({req_aspect:.2f}) "
                f"by {drift*100:.0f}% (tolerance {int(ASPECT_TOLERANCE*100)}%). "
                f"add_image_safe will letterbox the picture inside the zone, "
                f"leaving empty card space. Either resize the zone to match "
                f"the request, or change the request dimensions to match the zone."
            )

    def validate_image_request(tid: str, role: str, zone: dict) -> None:
        req = zone.get("imageRequest")
        if not isinstance(req, dict):
            errors.append(
                f"{tid}/{role}: source='generated' but no `imageRequest` block "
                f"(needs id + prompt)"
            )
            return
        if not req.get("id"):
            errors.append(f"{tid}/{role}: imageRequest missing `id`")
        prompt = req.get("prompt", "")
        if not isinstance(prompt, str) or len(prompt.strip()) < 30:
            errors.append(
                f"{tid}/{role}: imageRequest.prompt too short "
                f"({len(prompt.strip())} chars; require >= 30). "
                f"Composer prompts must encode subject + composition + color + style."
            )
        if not zone.get("fallback"):
            errors.append(
                f"{tid}/{role}: source='generated' requires a `fallback` block "
                f"(text-reflow / gradient / solid). Missing fallback breaks "
                f"s07-build.py when generation fails."
            )

        # Background-specific sizing check: must be slide-aspect AND >= 1920
        # on the long edge so set_slide_bg_image (fit='cover') doesn't have to
        # crop heavily or upscale a small image.
        if role == "background":
            w_px = req.get("width")
            h_px = req.get("height")
            if w_px is None or h_px is None:
                # C-3 (Phase C): promoted from warning to error.
                errors.append(
                    f"{tid}/background: imageRequest missing width/height. "
                    f"Required: 1920x1080 (16:9) for full-bleed backgrounds."
                )
            else:
                try:
                    w_px = int(w_px)
                    h_px = int(h_px)
                except (TypeError, ValueError):
                    errors.append(
                        f"{tid}/background: imageRequest width/height not integers"
                    )
                    return
                slide_aspect = SLIDE_W / SLIDE_H  # 16:9 by default
                req_aspect = w_px / h_px if h_px else 0
                # Allow ~3% tolerance
                if not (0.97 * slide_aspect <= req_aspect <= 1.03 * slide_aspect):
                    warnings.append(
                        f"{tid}/background: imageRequest aspect "
                        f"{w_px}x{h_px} ({req_aspect:.3f}) doesn't match slide "
                        f"aspect ({slide_aspect:.3f}). set_slide_bg_image with "
                        f"fit='cover' will crop the mismatch; prefer 1920x1080."
                    )
                if max(w_px, h_px) < 1920:
                    warnings.append(
                        f"{tid}/background: imageRequest {w_px}x{h_px} long edge "
                        f"< 1920 px. Backgrounds upscale poorly — use >= 1920."
                    )

    for s in plan.get("slides", []):
        tid = s.get("taskId", "?")
        spec = s.get("layoutSpec", {})

        # Slide-level background: `image-generated` follows the same contract.
        bg = spec.get("background")
        if isinstance(bg, dict) and bg.get("type") == "image-generated":
            validate_image_request(tid, "background", bg)
            if post_6f:
                src = bg.get("path") or bg.get("src")
                if not src and not bg.get("fallbackApplied"):
                    errors.append(
                        f"{tid}/background: post-6f generated background has no "
                        f"`path` and no `fallbackApplied: true`. Either patch "
                        f"the path (run s05f_patch_image_paths.py) or mark fallback."
                    )
                elif src:
                    full = (session_dir / src).resolve()
                    if not full.exists() and not bg.get("fallbackApplied"):
                        errors.append(
                            f"{tid}/background: generated image '{src}' missing "
                            f"and no `fallbackApplied: true` recorded"
                        )

        for z in spec.get("zones", []):
            if z.get("type") != "image":
                continue
            role = z.get("role", "?")
            source = z.get("source", "user-media")
            if source == "generated":
                validate_image_request(tid, role, z)
                # Aspect-ratio match between zone and imageRequest (fix i2)
                req = z.get("imageRequest")
                if isinstance(req, dict):
                    _check_aspect(tid, role, req, z.get("w"), z.get("h"))
                src = z.get("src") or z.get("path")
                if post_6f:
                    if not src and not z.get("fallbackApplied"):
                        errors.append(
                            f"{tid}/{role}: post-6f generated zone has no "
                            f"`path` and no `fallbackApplied: true`. Run "
                            f"s05f_patch_image_paths.py or mark fallback."
                        )
                    elif src:
                        full = (session_dir / src).resolve()
                        if not full.exists() and not z.get("fallbackApplied"):
                            errors.append(
                                f"{tid}/{role}: generated image '{src}' missing "
                                f"and no `fallbackApplied: true` recorded"
                            )
                else:
                    if src:
                        full = (session_dir / src).resolve()
                        if not full.exists():
                            warnings.append(
                                f"{tid}/{role}: generated image path '{src}' missing — "
                                f"6f may not have completed (or generation failed)"
                            )
                continue
            # source == 'user-media' (default): existing behavior
            src = z.get("src") or z.get("path")
            if not src:
                warnings.append(
                    f"{tid}/{role}: image zone has no src/path "
                    f"(deferred to build — verify before run)"
                )
                continue
            full = (session_dir / src).resolve()
            if not full.exists():
                errors.append(f"{tid}/{role}: image '{src}' not found in session")
                continue
            image_usage[src].append(tid)
    for src, slides in image_usage.items():
        if len(slides) > 1:
            errors.append(
                f"image '{src}' reused on slides {slides} — "
                f"violates no-reuse rule (build-script-template.md)"
            )

    # Surface VLM-absent zones as warnings — they were patched from raw
    # generation output, not from a curated selection. Step 8 QA should
    # visually verify each. See retrospective I-06 / R-06.
    unvetted: list[tuple[str, str]] = []
    for s in plan.get("slides", []):
        tid = s.get("taskId", "?")
        spec = s.get("layoutSpec", {})
        bg = spec.get("background")
        if isinstance(bg, dict) and bg.get("type") in ("image", "image-generated"):
            if bg.get("vlmSelectionApplied") is False and bg.get("path"):
                unvetted.append((tid, "background"))
        for z in spec.get("zones", []):
            if z.get("type") == "image" and z.get("source") == "generated":
                if z.get("vlmSelectionApplied") is False and z.get("path"):
                    unvetted.append((tid, z.get("role", "?")))
    if unvetted:
        sample = ", ".join(f"{t}/{r}" for t, r in unvetted[:6])
        more = f" (+{len(unvetted)-6} more)" if len(unvetted) > 6 else ""
        warnings.append(
            f"{len(unvetted)} generated-image zone(s) lack VLM selection — "
            f"patch_image_paths fell back to lowest-numbered variation. "
            f"Step 8 QA should visually verify: {sample}{more}"
        )

    return errors, warnings


def check_formula_resources(plan: dict, policy: dict) -> tuple[list[str], list[str]]:
    """Validate `type: "formula"` zones and (when present) the deck-wide
    `typography.mathFontset` selector.

    Per sessions/formula-svg-design-2026-05-01.md § 5.1:
      * Every formula zone must declare `notation` (Phase 1: only "mathtext"),
        `source` (Phase 1: only "authored"), and a `fallback` block with
        `kind == "text"` and non-empty text.
      * `colorToken`, when present, must exist in the style policy palette.
        (Absent = inherit from palette.body / palette.ink — the build
        helper's `resolve_formula_color` chain handles it.)
      * `mathFontset`, when present in `style-policy.typography`, must be
        one of {"dejavusans", "dejavuserif", "cm", "stix", "stixsans"}.
      * `fontPt`, when present, must be a positive number.
    """
    errors: list[str] = []
    warnings: list[str] = []

    valid_notations = {"mathtext"}
    valid_sources = {"authored"}
    valid_fontsets = {"dejavusans", "dejavuserif", "cm", "stix", "stixsans"}

    palette_keys = set(((policy or {}).get("palette") or {}).keys())

    fontset = ((policy or {}).get("typography") or {}).get("mathFontset")
    if fontset is not None and fontset not in valid_fontsets:
        errors.append(
            f"style-policy.typography.mathFontset={fontset!r} not in "
            f"{sorted(valid_fontsets)}"
        )

    for s in plan.get("slides", []):
        tid = s.get("taskId", "?")
        spec = s.get("layoutSpec") or {}
        for z in spec.get("zones", []):
            if z.get("type") != "formula":
                continue
            role = z.get("role", "?")
            prefix = f"{tid}/{role}(formula)"

            notation = z.get("notation")
            if not notation:
                errors.append(f"{prefix}: missing 'notation' (required for formula zones)")
            elif notation not in valid_notations:
                errors.append(
                    f"{prefix}: notation={notation!r} not in {sorted(valid_notations)} (Phase 1)"
                )

            source = z.get("source")
            if not source:
                errors.append(f"{prefix}: missing 'source' (required for formula zones)")
            elif source not in valid_sources:
                errors.append(
                    f"{prefix}: source={source!r} not in {sorted(valid_sources)} (Phase 1)"
                )

            fallback = z.get("fallback")
            if not isinstance(fallback, dict):
                errors.append(
                    f"{prefix}: missing 'fallback' block (required: kind+text Unicode degradation)"
                )
            else:
                kind = fallback.get("kind")
                if kind != "text":
                    errors.append(
                        f"{prefix}: fallback.kind={kind!r} must be 'text' (Phase 1)"
                    )
                text = fallback.get("text")
                if not isinstance(text, str) or not text.strip():
                    errors.append(f"{prefix}: fallback.text empty or missing")

            color_token = z.get("colorToken")
            if color_token and palette_keys and color_token not in palette_keys:
                errors.append(
                    f"{prefix}: colorToken={color_token!r} not found in style-policy.palette "
                    f"(known: {sorted(palette_keys)})"
                )

            font_pt = z.get("fontPt")
            if font_pt is not None and (not isinstance(font_pt, (int, float)) or font_pt <= 0):
                errors.append(f"{prefix}: fontPt must be a positive number, got {font_pt!r}")

            fit_mode = z.get("fitMode")
            if fit_mode is not None and fit_mode not in ("scale-to-zone", "natural"):
                errors.append(
                    f"{prefix}: fitMode={fit_mode!r} not in ['scale-to-zone', 'natural']"
                )

    return errors, warnings


def check_quota_waivers(plan: dict) -> tuple[list[str], list[str]]:
    """Hard-fail when quotaWaiver is abused.

    Rules:
      - Each waiver MUST carry a reason of >= 20 characters.
        Short / empty reasons (e.g. "n/a", "ok", "skip") are rejected.
      - A deck may carry at most 2 waivers in total. Beyond that, the
        designer is bypassing the Floor systematically — fail.

    Returns (errors, warnings).
    """
    errors: list[str] = []
    warnings: list[str] = []
    waivers: list[tuple[str, str]] = []  # (taskId, reason)
    for s in plan.get("slides", []):
        r = s.get("designRationale")
        if not isinstance(r, dict):
            continue
        w = r.get("quotaWaiver")
        if not w:
            continue
        if isinstance(w, str):
            reason = w.strip()
        elif isinstance(w, dict):
            reason = str(w.get("reason", "")).strip()
        else:
            errors.append(
                f"{s.get('taskId', '?')}: quotaWaiver must be a string or "
                f"{{quota, reason}} object, got {type(w).__name__}"
            )
            continue
        if len(reason) < 20:
            errors.append(
                f"{s.get('taskId', '?')}: quotaWaiver reason too short "
                f"({len(reason)} chars; require >= 20). Was: {reason!r}"
            )
            continue
        waivers.append((s.get("taskId", "?"), reason))
    if len(waivers) > 2:
        ids = [w[0] for w in waivers]
        errors.append(
            f"Quota waiver abuse: {len(waivers)} waivers in deck (max 2). "
            f"Slides: {ids}. Universal Design Floor exists to prevent "
            f"systematic blandness — fix the design instead of waiving."
        )
    return errors, warnings


def check_design_floor(
    plan: dict,
    policy: dict,
    slide_w: float = SLIDE_W,
    slide_h: float = SLIDE_H,
) -> tuple[list[str], list[str]]:
    """Universal Design Floor quotas (visual-tone-mapping.md § Universal Design Floor).

    Quota 1 — layout variety: distinct patterns >= 60% body count, no single
              pattern > 30% of body slides (when body > 6).
    Quota 2 — hero cadence: each window of 5 body slides contains >= 1 hero.
    Quota 3 — color-area floor: >= 30% body slides have non-white background
              OR primary/accent shape >= 15% slide area.
    Quota 4 — typographic punch: deck contains >= 2 display titles AND
              >= 1 slide with non-default title color.

    `restrained` ambition halves all thresholds.
    """
    errors: list[str] = []
    warnings: list[str] = []

    vt = policy.get("visualTone", {}) or {}
    ambition = vt.get("designAmbition", "expressive")
    restrained = ambition == "restrained"

    structural_roles = {"cover", "closing", "divider"}
    body = [s for s in plan.get("slides", []) if s.get("slideType") not in structural_roles]
    body_count = len(body)
    if body_count == 0:
        return errors, warnings

    # Helper to check waiver — slides with quotaWaiver in designRationale skip floor checks.
    # Accepts either:
    #   "quotaWaiver": "free-form reason string" (legacy)
    #   "quotaWaiver": { "quota": "Q1|Q2|Q3|Q4", "reason": "..." } (preferred)
    def waiver_text(slide: dict) -> str:
        r = slide.get("designRationale")
        if not isinstance(r, dict):
            return ""
        w = r.get("quotaWaiver")
        if isinstance(w, str):
            return w
        if isinstance(w, dict):
            return str(w.get("reason", ""))
        return ""

    def is_waived(slide: dict) -> bool:
        return bool(waiver_text(slide).strip())

    # ── Quota 1 — variety ─────────────────────────────────────────────
    if body_count > 6 or (body_count >= 4 and restrained is False):
        patterns = [s.get("layoutPattern", "") for s in body]
        distinct = len(set(patterns))
        max_share = max(patterns.count(p) for p in set(patterns))
        if body_count > 6:
            distinct_floor = 0.40 if restrained else 0.60
            share_ceiling = 0.50 if restrained else 0.30
            if distinct < distinct_floor * body_count:
                errors.append(
                    f"Quota 1 (variety): {distinct} distinct patterns across {body_count} body "
                    f"slides — floor is {int(distinct_floor*100)}% ({int(distinct_floor*body_count)+1})"
                )
            if max_share > share_ceiling * body_count:
                top_pat = max(set(patterns), key=patterns.count)
                errors.append(
                    f"Quota 1 (variety): pattern '{top_pat}' used {max_share}/{body_count} times "
                    f"({max_share/body_count*100:.0f}%) — ceiling is {int(share_ceiling*100)}%"
                )
        elif 4 <= body_count <= 6 and not restrained:
            if distinct < 3:
                errors.append(
                    f"Quota 1 (variety): only {distinct} distinct patterns across {body_count} "
                    f"body slides — floor is 3"
                )

    # ── Quota 2 — hero cadence ────────────────────────────────────────
    # Hero detection: explicit isHero flag is authoritative. Background,
    # title size, and large media zones serve as supplementary structural
    # signals only when the LLM omits the flag (treated as a soft-fail
    # rather than a hard miss). There is no pattern-name catalog — the
    # LLM designs every layout from scratch, so a name lookup would be
    # meaningless.

    def is_hero(slide: dict) -> bool:
        if is_waived(slide):
            return True  # treat waived as satisfied for cadence
        spec = slide.get("layoutSpec", {})
        # Explicit isHero flag is authoritative — the LLM MUST set this
        # when it intends a slide to function as a hero.
        if spec.get("isHero") is True:
            return True
        # Inspect background type
        bg = spec.get("background")
        if isinstance(bg, dict):
            bt = bg.get("type")
            if bt == "gradient":
                return True
            if bt == "solid":
                color = bg.get("color", "")
                if color in {"primary", "accent"}:
                    return True
        # Display-scale title
        for z in spec.get("zones", []):
            if z.get("role") == "title" and z.get("size") == "display":
                return True
        # Chart / image zone occupying >= 40% slide area (data hero fallback)
        slide_area = slide_w * slide_h
        for z in spec.get("zones", []):
            if z.get("type") not in ("chart", "image"):
                continue
            try:
                wi = resolve_coord(z.get("w", 0), slide_w)
                hi = resolve_coord(z.get("h", 0), slide_h)
            except ValueError:
                continue
            if wi * hi >= 0.40 * slide_area:
                return True
        return False

    window = 8 if restrained else 5
    if body_count >= window:
        for i in range(body_count - window + 1):
            window_slides = body[i:i + window]
            if not any(is_hero(s) for s in window_slides):
                ids = [s.get("taskId", "?") for s in window_slides]
                errors.append(
                    f"Quota 2 (hero cadence): window {ids} has no hero slide "
                    f"(window size = {window})"
                )

    # ── Quota 3 — color-area floor ────────────────────────────────────
    # Derive the "counts as color" palette token set from the actual style
    # policy, not a hard-coded list. Any token whose key starts with
    # "primary", "accent", "secondary" carries visual weight; the rest
    # (background*, surface, text*, divider, textOnDark) doesn't.
    # See retrospective I-04 / R-04.
    palette_keys = set((policy.get("palette") or {}).keys())
    def _is_color_token(name: str) -> bool:
        n = (name or "").lower()
        return n.startswith("primary") or n.startswith("accent") or n.startswith("secondary")
    color_palette_keys = {k for k in palette_keys if _is_color_token(k)}
    if not color_palette_keys:
        # Defensive fallback: empty palette → use historical defaults
        color_palette_keys = {"primary", "accent"}
    nonwhite_bg = color_palette_keys | {"backgroundAlt"}

    def has_color_presence(slide: dict) -> bool:
        spec = slide.get("layoutSpec", {})
        # Check background at both layoutSpec level and top level
        bg = spec.get("background") or slide.get("background")
        if isinstance(bg, dict):
            bt = bg.get("type")
            if bt in {"gradient", "tinted", "image-generated"}:
                return True
            if bt == "solid" and bg.get("color") in nonwhite_bg:
                return True
        # Color-token shape >= 15% slide area, in real inches
        slide_area = slide_w * slide_h
        threshold = 0.15 * slide_area
        for z in spec.get("zones", []):
            if z.get("type") != "shape":
                continue
            if z.get("fill") not in color_palette_keys:
                continue
            try:
                wi = resolve_coord(z.get("w", 0), slide_w)
                hi = resolve_coord(z.get("h", 0), slide_h)
            except ValueError:
                continue
            if wi * hi >= threshold:
                return True
        return False

    color_floor = 0.15 if restrained else 0.30
    color_count = sum(1 for s in body if has_color_presence(s) or is_waived(s))
    if color_count < color_floor * body_count:
        errors.append(
            f"Quota 3 (color-area floor): only {color_count}/{body_count} body slides have "
            f"color presence — floor is {int(color_floor*100)}% ({int(color_floor*body_count)+1})"
        )

    # ── Quota 4 — typographic punch ───────────────────────────────────
    display_count = 0
    nondefault_color_count = 0
    for s in plan.get("slides", []):
        # Check layoutSpec zones
        for z in s.get("layoutSpec", {}).get("zones", []):
            if z.get("role") == "title":
                if z.get("size") == "display":
                    display_count += 1
                if z.get("color") not in (None, "text"):
                    nondefault_color_count += 1

    display_floor = 1 if restrained else 2
    has_display_waiver = any(
        "Quota 4" in waiver_text(s) for s in plan.get("slides", [])
    )
    if display_count < display_floor:
        msg = (
            f"Quota 4 (typographic punch): only {display_count} display-scale title(s) — "
            f"floor is {display_floor}"
        )
        if has_display_waiver:
            warnings.append(msg + " [WAIVED]")
        else:
            errors.append(msg)
    if not restrained and nondefault_color_count < 1:
        msg = (
            "Quota 4 (typographic punch): no slide has a non-default title color "
            "(needs >= 1 title in primary/accent/background)"
        )
        if has_display_waiver:
            warnings.append(msg + " [WAIVED]")
        else:
            errors.append(msg)

    return errors, warnings


def check_background_types(plan: dict) -> list[str]:
    """Validate background specs — accept both string (legacy) and object format."""
    valid_types = {"solid", "gradient", "tinted", "image-generated"}
    errors = []

    for s in plan.get("slides", []):
        tid = s.get("taskId", "?")
        spec = s.get("layoutSpec")
        if not spec:
            continue

        bg = spec.get("background")
        if bg is None:
            continue

        if isinstance(bg, str):
            # Legacy format — always valid
            continue

        if isinstance(bg, dict):
            bg_type = bg.get("type")
            if bg_type not in valid_types:
                errors.append(
                    f"{tid}: background.type '{bg_type}' invalid "
                    f"(must be one of: {sorted(valid_types)})"
                )
            if bg_type == "solid" and "color" not in bg:
                errors.append(f"{tid}: solid background missing 'color'")
            if bg_type == "gradient":
                if "colors" not in bg:
                    errors.append(f"{tid}: gradient background missing 'colors'")
                elif not isinstance(bg["colors"], list) or len(bg["colors"]) < 2:
                    errors.append(f"{tid}: gradient background 'colors' must be a list of 2 palette keys")
            if bg_type == "tinted":
                if "base" not in bg:
                    errors.append(f"{tid}: tinted background missing 'base'")
                if "tint" not in bg:
                    errors.append(f"{tid}: tinted background missing 'tint'")
                opacity = bg.get("tintOpacity", 0)
                if opacity > 0.20:
                    errors.append(
                        f"{tid}: tinted background tintOpacity={opacity} exceeds 0.20 "
                        f"(this is a subtle wash, not a color fill)"
                    )
            if bg_type == "image-generated":
                fit = bg.get("fit")
                if fit is not None and fit not in {"cover", "contain"}:
                    errors.append(
                        f"{tid}: background.fit='{fit}' invalid (must be 'cover' or 'contain')"
                    )
                scrim = bg.get("scrim")
                if scrim is not None:
                    if not isinstance(scrim, dict):
                        errors.append(f"{tid}: background.scrim must be an object")
                    else:
                        if "color" not in scrim:
                            errors.append(f"{tid}: background.scrim missing 'color'")
                        if "alpha" not in scrim:
                            errors.append(f"{tid}: background.scrim missing 'alpha'")
                        else:
                            a = scrim.get("alpha")
                            if not isinstance(a, (int, float)) or a < 0 or a > 0.85:
                                errors.append(
                                    f"{tid}: background.scrim.alpha={a} out of range "
                                    f"(0.0–0.85)"
                                )
            # image-generated structural fields (imageRequest + fallback)
            # are validated in check_image_resources.

    return errors


def check_full_canvas_image_zones(
    plan: dict,
    slide_w: float = SLIDE_W,
    slide_h: float = SLIDE_H,
) -> list[str]:
    """Warn when an image-typed zone occupies ~the full canvas.

    A zone covering >= 90% of slide area is logically a full-bleed
    background and should live in `layoutSpec.background` with
    `type: "image-generated"`. Modeling it as a `hero-image` zone forces
    the build path through `add_image_with_overlay`, which respects zone
    bounds — any aspect-ratio mismatch produces a centered, letterboxed
    picture instead of a true full-bleed fill.
    """
    warnings = []
    canvas_area = slide_w * slide_h
    threshold = 0.90

    for s in plan.get("slides", []):
        tid = s.get("taskId", "?")
        spec = s.get("layoutSpec") or {}
        bg = spec.get("background")
        bg_is_image = (
            isinstance(bg, dict)
            and bg.get("type") in ("image", "image-generated")
        )

        for z in spec.get("zones", []):
            if z.get("type") != "image":
                continue
            try:
                w = float(z.get("w", 0))
                h = float(z.get("h", 0))
            except (TypeError, ValueError):
                continue
            if w <= 0 or h <= 0:
                continue
            ratio = (w * h) / canvas_area
            if ratio < threshold:
                continue

            role = z.get("role", "?")
            if bg_is_image:
                warnings.append(
                    f"{tid}: zone '{role}' covers {ratio:.0%} of canvas AND "
                    f"the slide already declares an image-generated background. "
                    f"Remove the redundant zone — full-bleed imagery belongs "
                    f"in layoutSpec.background only."
                )
            else:
                warnings.append(
                    f"{tid}: image zone '{role}' covers {ratio:.0%} of canvas. "
                    f"Express this as layoutSpec.background "
                    f"(type='image-generated') so s07-build.py renders it via "
                    f"set_slide_bg_image (true full-bleed). Modeling it as a "
                    f"zone forces add_image_with_overlay, which letterboxes "
                    f"on aspect-ratio mismatch."
                )

    return warnings


def check_bookend_background_consistency(plan: dict) -> list[str]:
    """When structuralFamily declares *BackgroundType, every cover/closing/divider
    slide's layoutSpec.background.type must match the declaration.

    Skipped when the declarative fields are absent (backward compat).
    `motif-shape` (divider only) maps to a non-image background — solid/tinted
    are both acceptable when it is declared.
    """
    errors: list[str] = []
    sf = plan.get("structuralFamily")
    if not isinstance(sf, dict):
        return errors

    role_to_field = {
        "cover": "coverBackgroundType",
        "closing": "closingBackgroundType",
        "divider": "dividerBackgroundType",
        "recap": "recapBackgroundType",
    }

    def actual_bg_type(spec: dict) -> str | None:
        bg = spec.get("background") if isinstance(spec, dict) else None
        if isinstance(bg, str):
            return "solid"
        if isinstance(bg, dict):
            return bg.get("type")
        return None

    for s in plan.get("slides", []):
        role = s.get("slideType")
        field = role_to_field.get(role)
        if not field:
            continue
        declared = sf.get(field)
        if not declared:
            continue  # not declared — skip
        actual = actual_bg_type(s.get("layoutSpec", {}))
        tid = s.get("taskId", "?")
        if declared == "motif-shape":
            # Divider with motif-shape declaration: accept solid/tinted/gradient
            # backgrounds as long as it is not image-generated.
            if actual == "image-generated":
                errors.append(
                    f"{tid}: structuralFamily.{field}='motif-shape' but slide "
                    f"background.type='image-generated'. Either change the "
                    f"declaration or remove the generated background."
                )
            continue
        if actual != declared:
            errors.append(
                f"{tid}: structuralFamily.{field}='{declared}' but slide "
                f"background.type='{actual}'. Declaration and actual must match."
            )
    return errors


# (Aesthetic-topic keyword inference removed; `imageryDemand` is now
# resolved in Step 3a sub-task 6 and read directly from
# s05b-style-policy.json → visualTone.imageryDemand, which mirrors
# s03-presentation-blueprint.json → architecture.imageryDemand.)


def _resolve_imagery_demand(policy: dict | None) -> str | None:
    """Return the resolved `imageryDemand` from
    `s05b-style-policy.json → visualTone.imageryDemand`.

    This is the sole canonical source (decided in Step 3a sub-task 6,
    mirrored into the style policy by Step 5b). Returns one of
    {'high','medium','low','none'} or None when the field is
    missing/invalid (caller treats as a hard error).
    """
    if not isinstance(policy, dict):
        return None
    vt = policy.get("visualTone") or {}
    declared = vt.get("imageryDemand")
    if declared in {"high", "medium", "low", "none"}:
        return declared
    return None


def check_imagery_floor(
    plan: dict,
    policy: dict,
    query_intent: dict | None,
    brief: dict | None,
) -> tuple[list[str], list[str]]:
    """Enforce the Imagery Floor (visual-tone-mapping.md § Dimension 6).

    Reads the resolved `imageryDemand` from
    `s05b-style-policy.json → visualTone.imageryDemand` (decided in
    Step 3a sub-task 6, mirrored by Step 5b) and the resolved
    `visualTone.contentDomain`/`register`, then checks bookend background
    types and body-slide image-zone share.

    Skipped when no slides exist or the deck explicitly carries an
    `imageryFloorWaiver` deck-level field with a reason >= 20 chars.
    """
    errors: list[str] = []
    warnings: list[str] = []

    waiver = plan.get("imageryFloorWaiver")
    if isinstance(waiver, dict) and len((waiver.get("reason") or "").strip()) >= 20:
        return errors, [f"imageryFloorWaiver applied: {waiver.get('reason')}"]

    demand = _resolve_imagery_demand(policy)
    if demand is None:
        errors.append(
            "s05b-style-policy.json → visualTone.imageryDemand is "
            "missing or invalid; Step 5b must mirror one of "
            "{'high','medium','low','none'} from "
            "s03 → architecture.imageryDemand (resolved by Step 3a "
            "sub-task 6; see workflow-step3.md § Phase 3a sub-task 6 "
            "Imagery Demand cascade)."
        )
        return errors, warnings
    if demand == "none":
        return errors, []

    vt = (policy.get("visualTone") or {}) if isinstance(policy, dict) else {}
    register = vt.get("register") or ""
    domain = vt.get("contentDomain") or ""

    # Resolve register family
    is_creative = register in {"inspirational"} or domain == "creative-portfolio"
    is_conversational = register == "conversational"

    # Body-slide quota by demand × register family
    if is_creative:
        quotas = {"high": 0.50, "medium": 0.30, "low": 0.20, "none": 0.0}
    elif is_conversational:
        quotas = {"high": 0.30, "medium": 0.20, "low": 0.0, "none": 0.0}
    else:
        quotas = {"high": 0.0, "medium": 0.0, "low": 0.0, "none": 0.0}
    body_quota = quotas.get(demand, 0.0)

    slides = plan.get("slides", [])
    body = [s for s in slides if s.get("slideType") in {"content_text", "content_data", "content_mixed"}]

    def has_image_zone(s: dict) -> bool:
        spec = s.get("layoutSpec") or {}
        bg = spec.get("background")
        if isinstance(bg, dict) and bg.get("type") == "image-generated":
            return True
        for z in spec.get("zones", []) or []:
            if z.get("type") == "image":
                return True
        return False

    if body and body_quota > 0:
        with_image = sum(1 for s in body if has_image_zone(s))
        share = with_image / len(body)
        if share < body_quota:
            msg = (
                f"Imagery Floor: body slides with image zones "
                f"{with_image}/{len(body)} ({share:.0%}) below required "
                f"{body_quota:.0%} for register='{register or '?'}' / "
                f"domain='{domain or '?'}' / imageryDemand='{demand}'. "
                f"Add image zones in Step 5d or queue generation in 6f."
            )
            errors.append(msg)

    # Bookend requirements
    sf = plan.get("structuralFamily") or {}
    if demand == "high" and is_creative:
        for role, field in (("cover", "coverBackgroundType"), ("closing", "closingBackgroundType")):
            declared = sf.get(field)
            if declared and declared != "image-generated":
                errors.append(
                    f"Imagery Floor: structuralFamily.{field}='{declared}' but "
                    f"demand='high' + creative-portfolio requires 'image-generated'."
                )

    # Demand=medium: cover AND closing must be image-generated OR gradient
    # for inspirational/creative, conversational, and authoritative/analytical
    # registers (visual-tone-mapping.md § Imagery Floor — N3 upgrade).
    # instructional-rich at medium relaxes to "cover OR closing".
    if demand == "medium":
        non_solid = {"image-generated", "gradient"}
        if is_creative or is_conversational or register in {"authoritative", "analytical"}:
            for role, field in (("cover", "coverBackgroundType"),
                                ("closing", "closingBackgroundType")):
                declared = sf.get(field)
                if declared and declared not in non_solid:
                    errors.append(
                        f"Imagery Floor: structuralFamily.{field}='{declared}' but "
                        f"demand='medium' + register='{register}' requires "
                        f"{role} background ∈ {{image-generated, gradient}}."
                    )
        elif register == "instructional-rich":
            cover = sf.get("coverBackgroundType")
            closing = sf.get("closingBackgroundType")
            # Skip when neither field is declared (legacy decks)
            if cover or closing:
                cover_ok = (cover or "") in non_solid
                closing_ok = (closing or "") in non_solid
                if not (cover_ok or closing_ok):
                    errors.append(
                        f"Imagery Floor: instructional-rich at demand='medium' "
                        f"requires cover OR closing background ∈ "
                        f"{{image-generated, gradient}}; got cover='{cover}', "
                        f"closing='{closing}'."
                    )

    if demand in {"high", "medium"}:
        # Dividers
        declared = sf.get("dividerBackgroundType")
        if demand == "high" and declared and declared not in {"image-generated"}:
            warnings.append(
                f"Imagery Floor: dividerBackgroundType='{declared}' — demand='high' "
                f"recommends 'image-generated' for all dividers."
            )

    return errors, warnings


# ── Phase A: Title-choreography validator ─────────────────────────

# Allowed move ids — keep in sync with style-policy schema's
# titleChoreography.movesAvailable enum and workflow-step5.md Rule 4.
TITLE_MOVES = {
    "mixed-weight-run",
    "oversized-numeral",
    "multi-line-break",
    "display-color-shift",
    "dual-typeface",
    "vertical-act-label",
    "wide-tracking",
    "drop-cap",
    "split-highlight",
}


def check_title_choreography(plan: dict, policy: dict,
                             content: dict | None = None) -> tuple[list[str], list[str]]:
    """Validate the deck-wide titleChoreography editorial plan (Phase A,
    permissive). Phase C will add per-slide execution verification.

    Args:
        plan: parsed s05-slide-visual-design.json.
        policy: parsed s05b-style-policy.json.
        content: optional parsed s06-slide-content.json. When supplied,
            the multi-line-break execution-evidence check verifies that
            the title slot text actually carries >= 1 newline (Phase C).
            When omitted (Step 5 checkpoint, s06 not yet authored), the
            check falls back to the layout-only flag heuristic.

    Rules enforced now:
      1. visualTone.titleChoreography MUST exist (deck-wide mandatory).
      2. movesAvailable is a non-empty subset of TITLE_MOVES.
      3. perSlidePlan is required: >= 1 entry; >= 3 entries when
         bodyCount >= 8.
      4. Each perSlidePlan.taskId MUST exist in the plan.
      5. Each perSlidePlan.move MUST be in movesAvailable.
      6. No single move may be used > 2 times across perSlidePlan.
      7. deckWideMoves entries (when present) MUST be in movesAvailable.
      8. When a deck claims `dual-typeface` anywhere, typography MUST
         define `secondaryFont`.
      9. (Phase C) For each perSlidePlan entry, the referenced slide's
         layoutSpec MUST show evidence of the declared move (errors,
         not warnings):
            - mixed-weight-run    -> at least one zone with `runs[]`
            - oversized-numeral   -> a zone with role containing
                                     'numeral' and area >= 0.04 * canvas
                                     (1–3 char glyph at 100–180pt)
            - multi-line-break    -> when s06 is available, the title
                                     slot text contains \\n; otherwise
                                     the layoutSpec carries a
                                     `multiLine: true` / `breakHint`
                                     hint (warning only at Step 5).
            - display-color-shift -> title zone color in
                                     {primary, accent, accent2, secondary}
            - dual-typeface       -> >= 2 text zones with different fonts
            - vertical-act-label  -> a zone with role containing
                                     'act-label' and `rotation` in {90, 270}
            - wide-tracking       -> a title-like text zone with
                                     `tracking: "wide"` or `letterSpacing >= 0.15`
            - drop-cap            -> a zone with role containing
                                     'drop-cap' and `size` >= 2x adjacent body
            - split-highlight     -> a shape zone with role containing
                                     'highlight' overlapping a title text zone
    """
    errors: list[str] = []
    warnings: list[str] = []

    visual_tone = (policy.get("visualTone") or {})
    chor = visual_tone.get("titleChoreography")

    body_slides = [
        s for s in plan.get("slides", [])
        if s.get("slideType") in {"content_text", "content_data", "content_mixed"}
    ]
    body_count = len(body_slides)
    plan_ids = {s.get("taskId") or s.get("slideId") for s in plan.get("slides", [])}

    # 1. Mandatory presence.
    if not chor or not isinstance(chor, dict):
        errors.append(
            "visualTone.titleChoreography is required (deck-wide). "
            "Declare movesAvailable, perSlidePlan, and (optionally) deckWideMoves "
            "in s05b-style-policy.json. See workflow-step5.md Rule 4."
        )
        return errors, warnings

    # 2. movesAvailable is sane.
    moves_available_raw = chor.get("movesAvailable") or []
    if not isinstance(moves_available_raw, list) or not moves_available_raw:
        errors.append("titleChoreography.movesAvailable must be a non-empty list.")
        moves_available = set()
    else:
        moves_available = set(moves_available_raw)
        unknown = moves_available - TITLE_MOVES
        if unknown:
            errors.append(
                f"titleChoreography.movesAvailable contains unknown moves: "
                f"{sorted(unknown)}. Allowed: {sorted(TITLE_MOVES)}."
            )

    # 3. perSlidePlan size.
    per_slide = chor.get("perSlidePlan") or []
    if not isinstance(per_slide, list):
        errors.append("titleChoreography.perSlidePlan must be a list.")
        per_slide = []
    min_required = 3 if body_count >= 8 else 1
    if len(per_slide) < min_required:
        errors.append(
            f"titleChoreography.perSlidePlan has {len(per_slide)} entries; "
            f"need >= {min_required} (bodyCount={body_count})."
        )

    # 4–6. Per-entry validation + use-count cap.
    use_counts: dict[str, int] = {}
    for i, entry in enumerate(per_slide):
        if not isinstance(entry, dict):
            errors.append(f"titleChoreography.perSlidePlan[{i}] must be an object.")
            continue
        tid = entry.get("taskId")
        move = entry.get("move")
        if not tid:
            errors.append(f"titleChoreography.perSlidePlan[{i}] missing taskId.")
        elif tid not in plan_ids:
            errors.append(
                f"titleChoreography.perSlidePlan[{i}].taskId='{tid}' not present "
                f"in plan slides ({sorted(plan_ids)})."
            )
        if not move:
            errors.append(f"titleChoreography.perSlidePlan[{i}] missing move.")
        else:
            if moves_available and move not in moves_available:
                errors.append(
                    f"titleChoreography.perSlidePlan[{i}].move='{move}' not in "
                    f"movesAvailable ({sorted(moves_available)})."
                )
            elif move not in TITLE_MOVES:
                errors.append(
                    f"titleChoreography.perSlidePlan[{i}].move='{move}' is not a "
                    f"recognized title move. Allowed: {sorted(TITLE_MOVES)}."
                )
            use_counts[move] = use_counts.get(move, 0) + 1

    overused = {m: n for m, n in use_counts.items() if n > 2}
    if overused:
        errors.append(
            "titleChoreography moves overused (max 2 per deck): "
            + ", ".join(f"{m}={n}" for m, n in sorted(overused.items()))
        )

    # 7. deckWideMoves sanity.
    deck_wide = chor.get("deckWideMoves") or []
    if deck_wide:
        if not isinstance(deck_wide, list):
            errors.append("titleChoreography.deckWideMoves must be a list.")
        else:
            for m in deck_wide:
                if moves_available and m not in moves_available:
                    errors.append(
                        f"titleChoreography.deckWideMoves contains '{m}' which is "
                        f"not in movesAvailable."
                    )

    # 8. dual-typeface requires secondaryFont.
    declared_moves = set(use_counts.keys()) | set(deck_wide)
    if "dual-typeface" in declared_moves:
        typography = policy.get("typography") or {}
        if not typography.get("secondaryFont"):
            errors.append(
                "titleChoreography uses 'dual-typeface' but typography.secondaryFont "
                "is not defined in style-policy."
            )

    # 9. Phase-C-lite execution evidence (warnings only at this stage).
    plan_by_id = {s.get("taskId") or s.get("slideId"): s for s in plan.get("slides", [])}
    canvas_area = SLIDE_W * SLIDE_H
    palette_color_tokens = {"primary", "accent", "accent2", "background", "secondary"}

    for entry in per_slide:
        tid = entry.get("taskId")
        move = entry.get("move")
        slide = plan_by_id.get(tid)
        if not slide:
            continue
        zones = (slide.get("layoutSpec") or {}).get("zones") or []
        try:
            resolved_zones = [resolve_zone(z, SLIDE_W, SLIDE_H) for z in zones]
        except ValueError:
            resolved_zones = []

        if move == "mixed-weight-run":
            ok = any(isinstance(z.get("runs"), list) and z.get("runs") for z in zones)
            if not ok:
                # C-1 (Phase C): promoted from warning to error.
                errors.append(
                    f"{tid}: declared 'mixed-weight-run' but no zone has a non-empty "
                    f"runs[] field. Add `runs: [...]` to the title text zone."
                )
        elif move == "oversized-numeral":
            big_enough = False
            for z in resolved_zones:
                role = (z.get("role") or "").lower()
                if "numeral" in role:
                    area = z["w"] * z["h"]
                    if area >= 0.04 * canvas_area:
                        big_enough = True
                        break
            if not big_enough:
                # C-1 (Phase C): promoted from warning to error.
                errors.append(
                    f"{tid}: declared 'oversized-numeral' but no zone with role "
                    f"containing 'numeral' is >= 4% of the canvas. Add a numeral "
                    f"zone (1–3 char glyph at 100–180pt, area >= 0.225 in² on a 10x5.625 deck)."
                )
        elif move == "multi-line-break":
            # Plan-time + content-time check.
            #
            # When s06-slide-content.json is available (post-Step-6),
            # we verify the actual title slot text carries >= 1
            # newline. This is the authoritative signal: a layout flag
            # is just a hint, but the slot text is what the build
            # script renders. When s06 is not yet present (Step 5
            # checkpoint), we fall back to checking the layoutSpec
            # flag/breakHint as a forward-looking signal.
            slot_text = None
            if content:
                for c_slide in content.get("slides", []):
                    if c_slide.get("taskId") == tid:
                        for slot in c_slide.get("slots", []):
                            zone_name = (slot.get("zone") or "").lower()
                            if "title" in zone_name or "headline" in zone_name:
                                slot_text = slot.get("text") or ""
                                break
                        break
            if slot_text is not None:
                if "\n" not in slot_text:
                    # C-1 (Phase C): when s06 is available, missing newline
                    # is conclusive — promote from warning to error.
                    errors.append(
                        f"{tid}: declared 'multi-line-break' but the title slot "
                        f"text in s06-slide-content.json does not contain any "
                        f"newline characters (\\n). Add `\\n` between the lines "
                        f"in the slot text."
                    )
            else:
                ok = any(
                    z.get("multiLine") is True or z.get("breakHint")
                    for z in zones
                    if z.get("type") == "text"
                )
                if not ok:
                    # No s06 yet — keep as warning (forward-looking signal).
                    warnings.append(
                        f"{tid}: declared 'multi-line-break' but no text zone carries "
                        f"`multiLine: true` or a `breakHint` field — Step 6 should set "
                        f"this when authoring the slot text."
                    )
        elif move == "display-color-shift":
            ok = False
            for z in zones:
                if z.get("type") != "text":
                    continue
                role = (z.get("role") or "").lower()
                if "title" not in role and "headline" not in role:
                    continue
                color = (z.get("color") or "").strip()
                if color in palette_color_tokens or color in {"text"}:
                    if color in palette_color_tokens - {"text"}:
                        ok = True
                        break
            if not ok:
                # C-1 (Phase C): promoted from warning to error.
                errors.append(
                    f"{tid}: declared 'display-color-shift' but no title-like text "
                    f"zone uses a non-default color token from {sorted(palette_color_tokens)}."
                )
        elif move == "dual-typeface":
            fonts = {z.get("font") for z in zones if z.get("type") == "text" and z.get("font")}
            if len(fonts) < 2:
                # C-1 (Phase C): promoted from warning to error.
                errors.append(
                    f"{tid}: declared 'dual-typeface' but fewer than 2 distinct "
                    f"font tokens are present in text zones (found {fonts})."
                )
        elif move == "vertical-act-label":
            ok = any(
                "act-label" in (z.get("role") or "").lower()
                and z.get("rotation") in (90, 270)
                for z in zones
            )
            if not ok:
                # C-1 (Phase C): promoted from warning to error.
                errors.append(
                    f"{tid}: declared 'vertical-act-label' but no zone with role "
                    f"containing 'act-label' and rotation in (90, 270) is present."
                )
        elif move == "wide-tracking":
            ok = any(
                z.get("type") == "text"
                and ("title" in (z.get("role") or "").lower() or "headline" in (z.get("role") or "").lower())
                and (z.get("tracking") == "wide" or (z.get("letterSpacing") or 0) >= 0.15)
                for z in zones
            )
            if not ok:
                errors.append(
                    f"{tid}: declared 'wide-tracking' but no title-like text zone "
                    f"has `tracking: \"wide\"` or `letterSpacing >= 0.15`."
                )
        elif move == "drop-cap":
            ok = any(
                "drop-cap" in (z.get("role") or "").lower()
                for z in zones
            )
            if not ok:
                errors.append(
                    f"{tid}: declared 'drop-cap' but no zone with role containing "
                    f"'drop-cap' is present."
                )
        elif move == "split-highlight":
            ok = any(
                z.get("type") == "shape"
                and "highlight" in (z.get("role") or "").lower()
                for z in zones
            )
            if not ok:
                errors.append(
                    f"{tid}: declared 'split-highlight' but no shape zone with role "
                    f"containing 'highlight' is present."
                )

    return errors, warnings


# ── Phase A: Motif-palette validator ──────────────────────────────

# Allowed values for motif `expression` and `deckRole` fields. Keep
# in sync with workflow-step5.md Rule 5 § Field reference.
MOTIF_EXPRESSIONS = {"shape-only", "shape-cluster", "image-accent", "generated-svg"}
MOTIF_DECK_ROLES = {"ambient", "structural"}
MOTIF_INTENSITIES = {"low", "medium", "high"}


def check_motif_palette(plan: dict, policy: dict) -> tuple[list[str], list[str]]:
    """Validate the deck-wide motifPalette (workflow-step5.md Rule 5).

    motifPalette is **recommended, not required**. Returns a single
    warning when absent so legacy sessions and minimalist decks pass.
    When present, validates field shape, vocabulary discipline,
    perSlidePlan grounding, and budget arithmetic as errors.
    """
    errors: list[str] = []
    warnings: list[str] = []

    visual_tone = (policy.get("visualTone") or {}) if isinstance(policy, dict) else {}
    palette = visual_tone.get("motifPalette")

    if palette is None:
        warnings.append(
            "visualTone.motifPalette is not declared — decoration vocabulary is implicit. "
            "Declaring it (primaryMotif + perSlidePlan + budget) makes the deck's "
            "decoration a deliberate signature instead of N independent shape choices; "
            "see workflow-step5.md Rule 5."
        )
        return errors, warnings

    if not isinstance(palette, dict):
        errors.append(
            f"visualTone.motifPalette must be an object, got {type(palette).__name__}"
        )
        return errors, warnings

    body_slides = [
        s for s in plan.get("slides", [])
        if s.get("slideType") in {"content_text", "content_data", "content_mixed"}
    ]
    body_count = len(body_slides)
    plan_ids = {s.get("taskId") or s.get("slideId") for s in plan.get("slides", [])}

    # Resolve mode for the reproduce/beautify exemption.
    mode = None
    cp = visual_tone.get("compositionPalette") or []
    if isinstance(cp, list) and cp and isinstance(cp[0], dict):
        mode_note = cp[0].get("modeNote") or ""
        for m in ("reproduce", "beautify", "expand", "generate"):
            if m in mode_note:
                mode = m
                break

    # Validate primaryMotif (required when palette is declared).
    primary = palette.get("primaryMotif")
    if not isinstance(primary, dict):
        errors.append("motifPalette.primaryMotif is required (object).")
        return errors, warnings

    motifs_by_name: dict[str, dict] = {}

    def _validate_motif(motif: dict, slot: str, require_rationale: bool) -> None:
        prefix = f"motifPalette.{slot}"
        name = motif.get("name")
        if not isinstance(name, str) or len(name.strip()) < 3:
            errors.append(f"{prefix}.name must be a string of >= 3 chars.")
            return
        if name in motifs_by_name:
            errors.append(
                f"{prefix}.name='{name}' duplicates another motif's name; "
                f"each motif must be uniquely named."
            )
        motifs_by_name[name] = motif

        vocab = motif.get("vocabulary")
        if not isinstance(vocab, list) or not (2 <= len(vocab) <= 5):
            errors.append(
                f"{prefix}.vocabulary must be a list of 2–5 named instances "
                f"(got {len(vocab) if isinstance(vocab, list) else 'non-list'})."
            )
        else:
            seen = set()
            for inst in vocab:
                if not isinstance(inst, str) or len(inst.strip()) < 3:
                    errors.append(
                        f"{prefix}.vocabulary contains an invalid entry: {inst!r}"
                    )
                elif inst in seen:
                    errors.append(
                        f"{prefix}.vocabulary contains duplicate instance '{inst}'."
                    )
                seen.add(inst)

        expr = motif.get("expression")
        if expr not in MOTIF_EXPRESSIONS:
            errors.append(
                f"{prefix}.expression='{expr}' invalid; "
                f"must be one of {sorted(MOTIF_EXPRESSIONS)}."
            )

        role = motif.get("deckRole")
        if role not in MOTIF_DECK_ROLES:
            errors.append(
                f"{prefix}.deckRole='{role}' invalid; "
                f"must be one of {sorted(MOTIF_DECK_ROLES)}."
            )

        if require_rationale:
            rationale = motif.get("rationale")
            if not isinstance(rationale, str) or len(rationale.strip()) < 20:
                errors.append(
                    f"{prefix}.rationale must be a string of >= 20 chars "
                    f"and reference narrative architecture (coreArgument, "
                    f"contentDomain, audience, or aestheticSignals)."
                )

    _validate_motif(primary, "primaryMotif", require_rationale=True)

    secondary = palette.get("secondaryMotif")
    if secondary is not None:
        if not isinstance(secondary, dict):
            errors.append(
                f"motifPalette.secondaryMotif must be an object when present, "
                f"got {type(secondary).__name__}"
            )
        else:
            _validate_motif(secondary, "secondaryMotif", require_rationale=False)

    # Validate perSlidePlan
    per_slide = palette.get("perSlidePlan") or []
    if not isinstance(per_slide, list):
        errors.append("motifPalette.perSlidePlan must be a list.")
        per_slide = []

    motif_use_counts: dict[str, int] = {}
    instance_use_counts: dict[str, int] = {}

    for i, entry in enumerate(per_slide):
        prefix = f"motifPalette.perSlidePlan[{i}]"
        if not isinstance(entry, dict):
            errors.append(f"{prefix} must be an object.")
            continue
        tid = entry.get("taskId")
        motif_name = entry.get("motif")
        instance = entry.get("instance")
        intensity = entry.get("intensity")

        if not tid:
            errors.append(f"{prefix} missing taskId.")
        elif tid not in plan_ids:
            errors.append(
                f"{prefix}.taskId='{tid}' not present in plan slides "
                f"({sorted(plan_ids)})."
            )
        if not motif_name:
            errors.append(f"{prefix} missing motif.")
        elif motif_name not in motifs_by_name:
            errors.append(
                f"{prefix}.motif='{motif_name}' not declared as primaryMotif "
                f"or secondaryMotif (declared: {sorted(motifs_by_name)})."
            )
        else:
            motif_use_counts[motif_name] = motif_use_counts.get(motif_name, 0) + 1
            vocab = (motifs_by_name[motif_name].get("vocabulary") or [])
            if instance and instance not in vocab:
                errors.append(
                    f"{prefix}.instance='{instance}' not in motif "
                    f"'{motif_name}' vocabulary {vocab}."
                )
            elif not instance:
                errors.append(f"{prefix} missing instance.")
        if intensity and intensity not in MOTIF_INTENSITIES:
            errors.append(
                f"{prefix}.intensity='{intensity}' invalid; "
                f"must be one of {sorted(MOTIF_INTENSITIES)}."
            )
        if instance:
            instance_use_counts[instance] = instance_use_counts.get(instance, 0) + 1

    # Budget validation
    budget = palette.get("budget") or {}
    if not isinstance(budget, dict):
        errors.append("motifPalette.budget must be an object.")
        budget = {}

    ambient_max_fraction = budget.get("ambientMaxFraction", 0.6)
    decoration_free_min = budget.get("decorationFreeMin", 2)

    if not isinstance(ambient_max_fraction, (int, float)) or not (0.1 <= ambient_max_fraction <= 1.0):
        errors.append(
            f"motifPalette.budget.ambientMaxFraction must be a number in "
            f"[0.1, 1.0] (got {ambient_max_fraction!r})."
        )
        ambient_max_fraction = 0.6
    if not isinstance(decoration_free_min, int) or decoration_free_min < 0:
        errors.append(
            f"motifPalette.budget.decorationFreeMin must be a non-negative "
            f"integer (got {decoration_free_min!r})."
        )
        decoration_free_min = 2

    # Cross-rule: secondaryMotif declared → must spend >= 1 perSlidePlan entry.
    if secondary is not None and motif_use_counts:
        secondary_name = secondary.get("name") if isinstance(secondary, dict) else None
        if secondary_name and motif_use_counts.get(secondary_name, 0) == 0:
            errors.append(
                f"motifPalette.secondaryMotif='{secondary_name}' is declared "
                f"but never used in perSlidePlan — declaring a secondary motif "
                f"without spending it is decoration drift; either remove the "
                f"declaration or assign it to at least one slide."
            )

    # reproduce/beautify mode relaxations
    if mode == "reproduce":
        return errors, warnings  # Suspend remaining sizing checks
    if mode == "beautify":
        ambient_max_fraction = max(ambient_max_fraction, 0.75)
        decoration_free_min = max(decoration_free_min, 2)

    # Body-slide accounting
    if body_count > 0 and per_slide:
        max_motif_uses = int(round(ambient_max_fraction * body_count))
        for motif_name, count in motif_use_counts.items():
            if count > max_motif_uses:
                errors.append(
                    f"motifPalette: motif '{motif_name}' used {count} times in "
                    f"perSlidePlan, exceeds ambientMaxFraction={ambient_max_fraction} "
                    f"× bodyCount({body_count}) = {max_motif_uses}."
                )
        if len(per_slide) > body_count - decoration_free_min:
            errors.append(
                f"motifPalette: perSlidePlan has {len(per_slide)} entries but "
                f"decorationFreeMin={decoration_free_min} requires at least "
                f"{decoration_free_min} body slides to carry no motif "
                f"(bodyCount={body_count}, max plan size = "
                f"{body_count - decoration_free_min})."
            )

    # Identical-instance cap (Rule 4 cadence: <= 40% of body slides may
    # share the same decoration composition).
    if body_count > 0:
        max_instance_uses = int(round(0.4 * body_count))
        for instance, count in instance_use_counts.items():
            if count > max_instance_uses:
                errors.append(
                    f"motifPalette: instance '{instance}' used {count} times "
                    f"in perSlidePlan, exceeds Rule 4 cadence cap of "
                    f"40% × bodyCount({body_count}) = {max_instance_uses}. "
                    f"Spread the motif across more vocabulary instances."
                )

    return errors, warnings


# ── Phase B: Accent-imagery validator ─────────────────────────────

# Required prompt-constraint keywords for imageRole='accent' zones.
ACCENT_PROMPT_TOKENS = (
    "abstract", "texture", "wash", "gradient", "motif", "organic",
    "pattern", "non-representational", "color field",
)


def check_accent_imagery(plan: dict, policy: dict,
                         slide_w: float = SLIDE_W,
                         slide_h: float = SLIDE_H) -> tuple[list[str], list[str]]:
    """Validate accent-imagery zones (Phase B, permissive).

    Rules enforced now:
      1. accentImageryAllowance, when present, must declare a numeric
         maxPerDeck and maxAreaFraction.
      2. Zones with imageRole='accent':
         - area MUST be <= maxAreaFraction * canvas (default 0.30);
         - MUST NOT overlap any zone whose role contains 'title' or
           'headline';
         - imageRequest.prompt MUST contain at least one
           ACCENT_PROMPT_TOKENS keyword.
      3. Total accent-zone count MUST be <= maxPerDeck (default 2).
      4. Zones with imageRole='atmospheric' SHOULD use background
         placement (full-bleed); area >= 0.85 * canvas — warning only.
      5. Zones with imageRole='narrative' SHOULD have area between
         0.20 and 0.80 of canvas — warning only.
    """
    errors: list[str] = []
    warnings: list[str] = []

    canvas_area = slide_w * slide_h
    allowance = (policy.get("visualTone") or {}).get("accentImageryAllowance") or {}
    max_per_deck = allowance.get("maxPerDeck", 2)
    max_area_fraction = allowance.get("maxAreaFraction", 0.30)

    if allowance:
        if not isinstance(max_per_deck, int) or max_per_deck < 0:
            errors.append(
                f"accentImageryAllowance.maxPerDeck must be a non-negative int "
                f"(got {max_per_deck!r})."
            )
        if not isinstance(max_area_fraction, (int, float)) or not (0 < max_area_fraction <= 1):
            errors.append(
                f"accentImageryAllowance.maxAreaFraction must be in (0, 1] "
                f"(got {max_area_fraction!r})."
            )

    accent_count = 0
    for s in plan.get("slides", []):
        tid = s.get("taskId") or s.get("slideId", "?")
        zones = (s.get("layoutSpec") or {}).get("zones") or []
        try:
            resolved = [resolve_zone(z, slide_w, slide_h) for z in zones]
        except ValueError:
            continue

        title_rects = [
            z for z in resolved
            if z.get("type") == "text"
            and any(tok in (z.get("role") or "").lower()
                    for tok in ("title", "headline"))
        ]

        for raw_zone, rz in zip(zones, resolved):
            if raw_zone.get("type") != "image":
                continue
            role_class = raw_zone.get("imageRole")
            area_frac = (rz["w"] * rz["h"]) / canvas_area if canvas_area else 0

            # Infer role when omitted (backward compatibility).
            if not role_class:
                if area_frac >= 0.85:
                    role_class = "atmospheric"
                elif area_frac >= 0.35:
                    role_class = "narrative"
                else:
                    role_class = "accent"

            if role_class == "accent":
                accent_count += 1
                # 2a. Area cap.
                if area_frac > max_area_fraction + 0.01:
                    errors.append(
                        f"{tid}/{raw_zone.get('role', '?')}: accent image area "
                        f"{area_frac*100:.1f}% > allowance maxAreaFraction "
                        f"{max_area_fraction*100:.0f}%. Reclassify as 'narrative' "
                        f"or shrink the zone."
                    )
                # 2b. Title overlap.
                for tr in title_rects:
                    if _rects_overlap(rz, tr):
                        errors.append(
                            f"{tid}/{raw_zone.get('role', '?')}: accent image overlaps "
                            f"title zone '{tr.get('role')}'. Accent imagery must clear "
                            f"the title bbox (Phase B Rule 2b)."
                        )
                        break
                # 2c. Prompt constraint keyword.
                req = raw_zone.get("imageRequest") or {}
                prompt = (req.get("prompt") or "").lower()
                if prompt and not any(tok in prompt for tok in ACCENT_PROMPT_TOKENS):
                    # C-2 (Phase C): promoted from warning to error.
                    errors.append(
                        f"{tid}/{raw_zone.get('role', '?')}: accent imageRequest.prompt "
                        f"does not contain an abstract-style keyword "
                        f"({list(ACCENT_PROMPT_TOKENS)}). Risk of generating a "
                        f"representational image. Add at least one keyword such as "
                        f"'abstract', 'wash', 'texture', 'gradient', 'motif'."
                    )
            elif role_class == "atmospheric":
                if area_frac < 0.85:
                    warnings.append(
                        f"{tid}/{raw_zone.get('role', '?')}: imageRole='atmospheric' "
                        f"but area is {area_frac*100:.1f}% (< 85%). Atmospheric "
                        f"zones should be full-bleed background."
                    )
            elif role_class == "narrative":
                if area_frac < 0.20 or area_frac > 0.80:
                    warnings.append(
                        f"{tid}/{raw_zone.get('role', '?')}: imageRole='narrative' "
                        f"area {area_frac*100:.1f}% outside the 20-80% recommended "
                        f"band. Reclassify or resize."
                    )

    # 3. Deck-wide accent count cap.
    if accent_count > max_per_deck:
        errors.append(
            f"Deck has {accent_count} accent image zones; "
            f"accentImageryAllowance.maxPerDeck = {max_per_deck}. "
            f"Either remove accent zones or raise the allowance."
        )

    return errors, warnings


# ── Structural-slide imagery uplift simplicity validator ──────────

# Required prompt-constraint keywords for image-generated backgrounds
# on cover / closing / divider slides when the structural-slide
# imagery uplift applies (visual-tone-mapping.md § Structural-slide
# imagery uplift). Keeps the imagery legible-as-abstract — no people,
# no scenes, no realistic objects competing with the structural type.
STRUCTURAL_SIMPLICITY_TOKENS = (
    "abstract", "geometric", "grid", "mesh", "topographic", "circuit",
    "schematic", "isometric pattern", "isometric", "gradient", "monochrome",
    "wireframe", "contour", "low-poly", "low poly", "noise field",
    "dot matrix", "line art", "blueprint",
)

STRUCTURAL_SIMPLICITY_DOMAINS = (
    "technical-instructional", "data-analytical", "general",
)

STRUCTURAL_SLIDE_TYPES = ("cover", "closing", "divider", "recap")


def check_structural_imagery_simplicity(
    plan: dict, policy: dict
) -> tuple[list[str], list[str]]:
    """Validate that structural slides taking the imagery-uplift permission
    keep their image-generated backgrounds simple / abstract.

    Trigger conditions (visual-tone-mapping.md § Structural-slide imagery
    uplift) — when ALL hold, every image-generated background on a
    structural slide MUST contain at least one keyword from
    STRUCTURAL_SIMPLICITY_TOKENS in its prompt:
      - imageryDemand ∈ {low, medium}
      - contentDomain ∈ STRUCTURAL_SIMPLICITY_DOMAINS
      - formalityLevel ≠ regulatory
      - imageryHint ≠ avoid-imagery
      - audience.role ∉ {compliance, audit, legal-internal}

    Outside the trigger, this validator is a no-op.
    """
    errors: list[str] = []
    warnings: list[str] = []

    visual_tone = policy.get("visualTone") or {}
    demand = visual_tone.get("imageryDemand")
    domain = visual_tone.get("contentDomain")
    if demand not in ("low", "medium"):
        return errors, warnings
    if domain not in STRUCTURAL_SIMPLICITY_DOMAINS:
        return errors, warnings

    # Hard suppressors — defer to design intent.
    formality = (visual_tone.get("formalityLevel")
                 or (policy.get("constraints") or {}).get("formalityLevel"))
    if formality == "regulatory":
        return errors, warnings
    imagery_hint = (visual_tone.get("imageryHint")
                    or (policy.get("aestheticSignals") or {}).get("imageryHint"))
    if imagery_hint == "avoid-imagery":
        return errors, warnings

    for slide in plan.get("slides", []):
        if slide.get("slideType") not in STRUCTURAL_SLIDE_TYPES:
            continue
        spec = slide.get("layoutSpec") or {}
        bg = spec.get("background")
        if not isinstance(bg, dict) or bg.get("type") != "image-generated":
            continue
        req = bg.get("imageRequest") or {}
        prompt_text = (req.get("prompt") or "").lower()
        if not prompt_text:
            continue
        if not any(tok in prompt_text for tok in STRUCTURAL_SIMPLICITY_TOKENS):
            errors.append(
                f"{slide.get('taskId', '?')} ({slide.get('slideType')}): "
                f"image-generated background prompt does not contain any "
                f"simplicity keyword "
                f"({', '.join(STRUCTURAL_SIMPLICITY_TOKENS[:6])}, …). "
                f"Structural-slide imagery uplift requires abstract / "
                f"geometric / topographic style — no scenes, no people, "
                f"no realistic objects. Add a keyword or switch the "
                f"background to gradient / motif-shape."
            )
        neg = (req.get("negative_prompt") or "").lower()
        if neg and not any(tok in neg for tok in (
            "no people", "no faces", "no scenes", "no logos",
            "no text", "no realistic objects", "no recognizable",
        )):
            warnings.append(
                f"{slide.get('taskId', '?')} ({slide.get('slideType')}): "
                f"image-generated background has a negative_prompt but no "
                f"explicit suppression of people / scenes / logos / text. "
                f"Recommended: 'no people, no logos, no scenes, no text, "
                f"no realistic objects'."
            )

    return errors, warnings


def check_structural_imagery_uplift(
    plan: dict, policy: dict
) -> tuple[list[str], list[str]]:
    """Enforce coverage of the Structural-slide imagery uplift
    (visual-tone-mapping.md § Structural-slide imagery uplift).

    When the same trigger conditions as `check_structural_imagery_simplicity`
    hold AND `imageryDemand == "medium"`, the uplift is REQUIRED:

      - Cover AND closing: background.type ∈ {image-generated, gradient}.
      - Every recap slide: background.type == image-generated.
      - At least one divider slide: background.type == image-generated.
      - Every agenda slide carries ≥ 1 shape zone (motif decoration)
        when `structuralFamily.agendaDecorationFromMotif` is true OR
        when sharedMotif is non-empty (default-on for technical/analytical).

    At `imageryDemand == "low"` the uplift is ENCOURAGED only — emit
    warnings instead of errors. Outside the trigger this validator is
    a no-op.
    """
    errors: list[str] = []
    warnings: list[str] = []

    visual_tone = policy.get("visualTone") or {}
    demand = visual_tone.get("imageryDemand")
    domain = visual_tone.get("contentDomain")
    if demand not in ("low", "medium"):
        return errors, warnings
    if domain not in STRUCTURAL_SIMPLICITY_DOMAINS:
        return errors, warnings

    formality = (visual_tone.get("formalityLevel")
                 or (policy.get("constraints") or {}).get("formalityLevel"))
    if formality == "regulatory":
        return errors, warnings
    imagery_hint = (visual_tone.get("imageryHint")
                    or (policy.get("aestheticSignals") or {}).get("imageryHint"))
    if imagery_hint == "avoid-imagery":
        return errors, warnings

    sink = errors if demand == "medium" else warnings
    label = "REQUIRED at medium demand" if demand == "medium" else "RECOMMENDED at low demand"

    def actual_bg_type(spec: dict) -> str | None:
        bg = spec.get("background") if isinstance(spec, dict) else None
        if isinstance(bg, str):
            return "solid"
        if isinstance(bg, dict):
            return bg.get("type")
        return None

    slides = plan.get("slides", [])
    by_type: dict[str, list[dict]] = {}
    for s in slides:
        by_type.setdefault(s.get("slideType") or "", []).append(s)

    # Cover + closing: must be image-generated or gradient
    for role in ("cover", "closing"):
        for s in by_type.get(role, []):
            bg = actual_bg_type(s.get("layoutSpec", {}))
            if bg not in ("image-generated", "gradient"):
                sink.append(
                    f"{s.get('taskId', '?')} ({role}): background.type='{bg}' "
                    f"violates structural-slide imagery uplift ({label}). "
                    f"Use 'image-generated' (abstract/geometric) or 'gradient'."
                )

    # Every recap: image-generated
    for s in by_type.get("recap", []):
        bg = actual_bg_type(s.get("layoutSpec", {}))
        if bg != "image-generated":
            sink.append(
                f"{s.get('taskId', '?')} (recap): background.type='{bg}' "
                f"violates structural-slide imagery uplift ({label}). "
                f"Recap slides serve as rhythmic pauses — use 'image-generated' "
                f"(abstract/geometric)."
            )

    # At least one divider: image-generated
    dividers = by_type.get("divider", [])
    if dividers:
        with_image = [s for s in dividers
                      if actual_bg_type(s.get("layoutSpec", {})) == "image-generated"]
        if not with_image:
            sink.append(
                f"divider coverage: 0/{len(dividers)} dividers use "
                f"'image-generated' background. Structural-slide imagery "
                f"uplift ({label}) requires at least one divider to carry "
                f"an image-generated (abstract/geometric) background."
            )

    # Agenda: ≥ 1 shape zone when motif decoration is opted-in
    sf = plan.get("structuralFamily") or {}
    motif = (sf.get("sharedMotif") or "").strip()
    decoration_required = bool(sf.get("agendaDecorationFromMotif")) or bool(motif)
    if decoration_required:
        for s in by_type.get("agenda", []):
            spec = s.get("layoutSpec") or {}
            zones = spec.get("zones") or []
            shape_zones = [z for z in zones if z.get("type") == "shape"]
            bg = actual_bg_type(spec)
            if bg == "solid" and not shape_zones:
                sink.append(
                    f"{s.get('taskId', '?')} (agenda): bare 'solid' background "
                    f"with zero shape zones. Structural-slide imagery uplift "
                    f"({label}) requires the agenda to carry ≥ 1 shape zone "
                    f"derived from sharedMotif='{motif or '(unset)'}' so it "
                    f"inherits the deck's visual DNA."
                )

    return errors, warnings


def _has_unpatched_generated_zones(plan: dict) -> bool:
    """True when at least one generated image zone/background has neither a
    resolved `path` nor an explicit `fallbackApplied: true`. This is the
    signal that 5f-2 produced images but 5f-4 (path patching) has not run
    yet — the failure mode that previously shipped silently empty slides.
    """
    for s in plan.get("slides", []):
        spec = s.get("layoutSpec") or {}
        bg = spec.get("background")
        if isinstance(bg, dict) and bg.get("type") == "image-generated":
            if not (bg.get("path") or bg.get("src")) and not bg.get("fallbackApplied"):
                return True
        for z in spec.get("zones", []) or []:
            if z.get("type") == "image" and z.get("source") == "generated":
                if not (z.get("path") or z.get("src")) and not z.get("fallbackApplied"):
                    return True
    return False


def _generation_artifacts_exist(session: Path) -> bool:
    """True when 5f-2 / 5f-3 produced any of the recognised output files."""
    return any(
        (session / name).exists()
        for name in (
            "s05f-image-selection.json",
            "s05f-image_generation_output.json",
            "image_generation_output.json",
        )
    )


def auto_patch_image_paths(session: Path, plan_path: Path) -> dict | None:
    """Deprecated. Step 5 validate is read-only; use the dedicated 5f-Step 4
    script `s05f_patch_image_paths.py "$SESSION"` instead.

    Retained as a thin shim for any external caller that imports the
    symbol; new code MUST NOT use it.
    """
    raise NotImplementedError(
        "auto_patch_image_paths was removed in P2 of the Step 5 audit. "
        "Run s05f_patch_image_paths.py explicitly as 5f-Step 4 before "
        "invoking the Step 5 validator. See workflow-step5.md § 5f-Step 4."
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Step 5 checkpoint validator for narrative-pptx-composer (template-free)"
    )
    parser.add_argument("session_dir", type=Path)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    session = args.session_dir.resolve()

    plan_path = session / "s05-slide-visual-design.json"
    policy_path = session / "s05b-style-policy.json"
    blueprint_path = session / "s03-presentation-blueprint.json"
    design_path = session / "s01d-design-config.json"
    query_intent_path = session / "s01b-query-intent.json"
    brief_path = session / "s02-communication-brief.json"
    content_path = session / "s06-slide-content.json"

    for p in [plan_path, policy_path, blueprint_path]:
        if not p.exists():
            print(f"FAIL: {p.name} not found in {session}")
            return 1

    plan = load_json(plan_path)
    # Validate is read-only. Run s05f_patch_image_paths.py explicitly
    # as part of the 5f workflow before invoking this checkpoint when
    # 5f-2 has produced generation output but 5f-4 has not folded the
    # paths back into the plan yet.
    if _generation_artifacts_exist(session) and _has_unpatched_generated_zones(plan):
        print(
            "✗ Image-path patching missing\n"
            "  ERROR: generation output detected (s05f-image-selection.json or "
            "s05f-image_generation_output.json) but the plan still has unpatched "
            "`source: generated` zones.\n"
            "  Run `python .claude/skills/narrative-pptx-composer/scripts/"
            "s05f_patch_image_paths.py \"$SESSION\"` (5f-Step 4), then re-run "
            "this validator. See workflow-step5.md § 5f-Step 4 — Patch image paths."
        )
        return 1
    policy = load_json(policy_path)
    blueprint = load_json(blueprint_path)

    # Normalize: ensure every plan slide has taskId (accept slideId as alias)
    for s in plan.get("slides", []):
        if "taskId" not in s and "slideId" in s:
            s["taskId"] = s["slideId"]
        # Ensure layoutSpec.background mirrors top-level background if missing
        spec = s.get("layoutSpec", {})
        if "background" not in spec and "background" in s:
            spec["background"] = s["background"]
            s["layoutSpec"] = spec
    query_intent = load_json(query_intent_path) if query_intent_path.exists() else None
    brief = load_json(brief_path) if brief_path.exists() else None
    content = load_json(content_path) if content_path.exists() else None
    slide_w, slide_h = SLIDE_W, SLIDE_H
    if design_path.exists():
        design = load_json(design_path)
        dims = design.get("dimensions") or {}
        slide_w = float(dims.get("width", SLIDE_W))
        slide_h = float(dims.get("height", SLIDE_H))

    print(f"Validating Step 5 checkpoint in: {session.name}")
    print(f"  Plan slides: {len(plan['slides'])}")
    print(f"  Blueprint slides: {len(blueprint['slides'])}")
    print(f"  Slide dimensions: {slide_w} x {slide_h} in")
    print()

    all_errors: list[str] = []
    all_warnings: list[str] = []

    # 1. Blueprint coverage
    errors = check_blueprint_coverage(plan, blueprint)
    if errors:
        print("\u2717 Blueprint coverage")
        for e in errors:
            print(f"  ERROR: {e}")
        all_errors.extend(errors)
    else:
        print(f"\u2713 Blueprint coverage \u2014 {len(plan['slides'])}/{len(blueprint['slides'])} mapped")

    # 2. Divider consistency
    errors = check_divider_consistency(plan)
    if errors:
        print("\u2717 Divider consistency")
        for e in errors:
            print(f"  ERROR: {e}")
        all_errors.extend(errors)
    else:
        divider_count = sum(
            1 for s in plan["slides"] if s.get("slideType") == "divider"
        )
        print(f"\u2713 Divider consistency \u2014 {divider_count} dividers share same pattern")

    # 3. Layout spec validity
    errors = check_layout_spec(plan)
    if errors:
        print("\u2717 Layout spec validity")
        for e in errors:
            print(f"  ERROR: {e}")
        all_errors.extend(errors)
    else:
        total_zones = sum(
            len(s.get("layoutSpec", {}).get("zones", []))
            for s in plan["slides"]
        )
        print(f"\u2713 Layout spec validity \u2014 {total_zones} zones across {len(plan['slides'])} slides")

    # 4. Geometric validation
    errors, geo_warnings = check_geometry(plan, slide_w, slide_h)
    if errors:
        print("\u2717 Geometric validation")
        for e in errors:
            print(f"  ERROR: {e}")
        all_errors.extend(errors)
    elif geo_warnings:
        print(f"\u2713 Geometric validation \u2014 no bounds violations; "
              f"{len(geo_warnings)} crowding warning(s)")
    else:
        print(f"\u2713 Geometric validation \u2014 no overlaps or bounds violations")
    if geo_warnings:
        for w in geo_warnings:
            print(f"  WARN: {w}")
        all_warnings.extend(geo_warnings)

    # 4b. Hard-ban: short horizontal rule beneath title text
    errors = check_banned_under_title_short_rules(plan, slide_w, slide_h)
    if errors:
        print("\u2717 Under-title short-rule ban")
        for e in errors:
            print(f"  ERROR: {e}")
        all_errors.extend(errors)
    else:
        print("\u2713 Under-title short-rule ban - no banned title dashes detected")

    # 5. Style policy structure
    errors = check_style_policy(policy)
    if errors:
        print("\u2717 Style policy structure")
        for e in errors:
            print(f"  ERROR: {e}")
        all_errors.extend(errors)
    else:
        print(f"\u2713 Style policy structure \u2014 palette + typography + spacing + designLanguage")

    # 5b. Palette token usage (warning only — raw hex breaks palette swaps)
    pt_warnings = check_palette_token_usage(plan, policy)
    if pt_warnings:
        print("⚠ Palette token usage")
        for w in pt_warnings:
            print(f"  WARN: {w}")
        all_warnings.extend(pt_warnings)
    else:
        print("✓ Palette token usage — no raw hex in zone fills")

    # 6. Visual tone dimensions
    errors = check_visual_tone(policy)
    if errors:
        print("\u2717 Visual tone dimensions")
        for e in errors:
            print(f"  ERROR: {e}")
        all_errors.extend(errors)
    else:
        vt = policy.get("visualTone", {})
        print(
            f"\u2713 Visual tone \u2014 register={vt.get('register')}, "
            f"contrast={vt.get('contrastStrategy')}"
        )

    # 7. Structural family declaration
    issues = check_structural_family(plan)
    sf = plan.get("structuralFamily")
    if sf is None:
        # Warn but don't fail
        print("\u26a0 Structural family")
        for w in issues:
            print(f"  WARN: {w}")
        all_warnings.extend(issues)
    elif issues:
        print("\u2717 Structural family")
        for e in issues:
            print(f"  ERROR: {e}")
        all_errors.extend(issues)
    else:
        print(
            f"\u2713 Structural family \u2014 motif={sf.get('sharedMotif')}, "
            f"divider={sf.get('dividerPattern')}"
        )

    # 7b. Bookend signature (recommended; warn when absent)
    bs_errors, bs_warnings = check_bookend_signature(plan)
    if bs_errors:
        print("\u2717 Bookend signature")
        for e in bs_errors:
            print(f"  ERROR: {e}")
        all_errors.extend(bs_errors)
    elif bs_warnings:
        print("\u26a0 Bookend signature")
        for w in bs_warnings:
            print(f"  WARN: {w}")
        all_warnings.extend(bs_warnings)
    else:
        sig = (plan.get("structuralFamily") or {}).get("bookendSignature") or {}
        print(f"\u2713 Bookend signature \u2014 rhyme='{sig.get('rhyme')}' "
              f"echoed across cover ↔ closing")

    # 8. Emphasis and design rationale
    issues = check_emphasis_and_rationale(plan)
    if issues:
        # Separate errors from warnings (warnings contain "typically has")
        emph_errors = [i for i in issues if "typically has" not in i]
        emph_warns = [i for i in issues if "typically has" in i]
        if emph_errors:
            print("\u2717 Emphasis & rationale")
            for e in emph_errors:
                print(f"  ERROR: {e}")
            all_errors.extend(emph_errors)
        if emph_warns:
            print("\u26a0 Emphasis expectations")
            for w in emph_warns:
                print(f"  WARN: {w}")
            all_warnings.extend(emph_warns)
        if not emph_errors and not emph_warns:
            print(f"\u2713 Emphasis & rationale \u2014 all slides have emphasis + designRationale")
    else:
        print(f"\u2713 Emphasis & rationale \u2014 all slides have emphasis + designRationale")

    # 8b. Designer rationale v2 \u2014 focal point / eye path / aesthetic move
    rv2_errors, rv2_warnings = check_designer_rationale_v2(plan, blueprint)
    if rv2_errors:
        print("\u2717 Designer rationale (v2)")
        for e in rv2_errors:
            print(f"  ERROR: {e}")
        all_errors.extend(rv2_errors)
    elif rv2_warnings:
        print("\u26a0 Designer rationale (v2)")
        for w in rv2_warnings:
            print(f"  WARN: {w}")
        all_warnings.extend(rv2_warnings)
    else:
        body_count = sum(
            1 for s in plan.get("slides", [])
            if s.get("slideType") not in {"cover", "closing", "divider"}
        )
        print(f"\u2713 Designer rationale (v2) \u2014 {body_count} body slide(s) anchor to narrative + name focal point + eyePath + aestheticMove")

    # 9. Background types
    errors = check_background_types(plan)
    if errors:
        print("\u2717 Background types")
        for e in errors:
            print(f"  ERROR: {e}")
        all_errors.extend(errors)
    else:
        # Count background types used
        bg_types = set()
        for s in plan.get("slides", []):
            bg = s.get("layoutSpec", {}).get("background")
            if isinstance(bg, str):
                bg_types.add("solid")
            elif isinstance(bg, dict):
                bg_types.add(bg.get("type", "solid"))
        print(f"\u2713 Background types \u2014 types used: {sorted(bg_types)}")

    # 9b. Full-canvas image zones (warn-only)
    fc_warns = check_full_canvas_image_zones(plan)
    if fc_warns:
        print("\u26a0 Full-canvas image zones")
        for w in fc_warns:
            print(f"  WARN: {w}")
        all_warnings.extend(fc_warns)
    else:
        print("\u2713 Full-canvas image zones \u2014 none miscoded as zones")

    # 10. Quota waiver discipline (must run before floor check so abuse is reported)
    waiver_errors, waiver_warnings = check_quota_waivers(plan)
    if waiver_errors:
        print("✗ Quota waiver discipline")
        for e in waiver_errors:
            print(f"  ERROR: {e}")
        all_errors.extend(waiver_errors)
    else:
        print("✓ Quota waiver discipline — no abuse")

    # 11. Universal Design Floor quotas
    floor_errors, floor_warnings = check_design_floor(plan, policy, slide_w, slide_h)
    if floor_errors:
        print("\u2717 Universal Design Floor")
        for e in floor_errors:
            print(f"  ERROR: {e}")
        all_errors.extend(floor_errors)
    elif floor_warnings:
        print("\u26a0 Universal Design Floor")
        for w in floor_warnings:
            print(f"  WARN: {w}")
        all_warnings.extend(floor_warnings)
    else:
        ambition = (policy.get("visualTone") or {}).get("designAmbition", "expressive")
        print(f"\u2713 Universal Design Floor \u2014 all quotas pass (ambition={ambition})")

    # 12. Image resources
    img_errors, img_warnings = check_image_resources(plan, session)
    if img_errors:
        print("\u2717 Image resources")
        for e in img_errors:
            print(f"  ERROR: {e}")
        all_errors.extend(img_errors)
    elif img_warnings:
        print("\u26a0 Image resources")
        for w in img_warnings:
            print(f"  WARN: {w}")
        all_warnings.extend(img_warnings)
    else:
        image_count = sum(
            1 for s in plan.get("slides", [])
            for z in s.get("layoutSpec", {}).get("zones", [])
            if z.get("type") == "image"
        )
        print(f"\u2713 Image resources \u2014 {image_count} image zone(s) verified")

    # 12b. Formula resources (mathtext zones)
    formula_errors, formula_warnings = check_formula_resources(plan, policy)
    formula_count = sum(
        1 for s in plan.get("slides", [])
        for z in s.get("layoutSpec", {}).get("zones", [])
        if z.get("type") == "formula"
    )
    if formula_errors:
        print("\u2717 Formula resources")
        for e in formula_errors:
            print(f"  ERROR: {e}")
        all_errors.extend(formula_errors)
    elif formula_warnings:
        print("\u26a0 Formula resources")
        for w in formula_warnings:
            print(f"  WARN: {w}")
        all_warnings.extend(formula_warnings)
    elif formula_count:
        print(f"\u2713 Formula resources \u2014 {formula_count} formula zone(s) verified")

    # 13. Bookend background-type consistency
    errors = check_bookend_background_consistency(plan)
    if errors:
        print("\u2717 Bookend background consistency")
        for e in errors:
            print(f"  ERROR: {e}")
        all_errors.extend(errors)
    else:
        print("\u2713 Bookend background consistency \u2014 declarations match actual backgrounds")

    # 14. Imagery Floor (Dimension 6)
    floor_errors2, floor_warnings2 = check_imagery_floor(plan, policy, query_intent, brief)
    if floor_errors2:
        print("\u2717 Imagery Floor")
        for e in floor_errors2:
            print(f"  ERROR: {e}")
        all_errors.extend(floor_errors2)
    elif floor_warnings2:
        print("\u26a0 Imagery Floor")
        for w in floor_warnings2:
            print(f"  WARN: {w}")
        all_warnings.extend(floor_warnings2)
    else:
        demand = _resolve_imagery_demand(policy) or "?"
        print(f"\u2713 Imagery Floor \u2014 demand={demand} satisfied")

    # 15. Title choreography (Phase A — deck-wide mandatory)
    tc_errors, tc_warnings = check_title_choreography(plan, policy, content)
    if tc_errors:
        print("\u2717 Title choreography")
        for e in tc_errors:
            print(f"  ERROR: {e}")
        all_errors.extend(tc_errors)
    elif tc_warnings:
        print("\u26a0 Title choreography")
        for w in tc_warnings:
            print(f"  WARN: {w}")
        all_warnings.extend(tc_warnings)
    else:
        chor = (policy.get("visualTone") or {}).get("titleChoreography") or {}
        n_moves = len(chor.get("perSlidePlan") or [])
        print(f"\u2713 Title choreography \u2014 {n_moves} per-slide move(s) declared")

    # 15b. Motif palette (Rule 5 — recommended)
    mp_errors, mp_warnings = check_motif_palette(plan, policy)
    if mp_errors:
        print("\u2717 Motif palette")
        for e in mp_errors:
            print(f"  ERROR: {e}")
        all_errors.extend(mp_errors)
    elif mp_warnings:
        print("\u26a0 Motif palette")
        for w in mp_warnings:
            print(f"  WARN: {w}")
        all_warnings.extend(mp_warnings)
    else:
        mp = (policy.get("visualTone") or {}).get("motifPalette") or {}
        prim = (mp.get("primaryMotif") or {}).get("name") or "?"
        n_uses = len(mp.get("perSlidePlan") or [])
        print(f"\u2713 Motif palette \u2014 primary='{prim}', {n_uses} body-slide use(s)")

    # 16. Accent imagery (Phase B — permissive allowance)
    ai_errors, ai_warnings = check_accent_imagery(plan, policy, slide_w, slide_h)
    if ai_errors:
        print("\u2717 Accent imagery")
        for e in ai_errors:
            print(f"  ERROR: {e}")
        all_errors.extend(ai_errors)
    elif ai_warnings:
        print("\u26a0 Accent imagery")
        for w in ai_warnings:
            print(f"  WARN: {w}")
        all_warnings.extend(ai_warnings)
    else:
        accent_n = sum(
            1 for s in plan.get("slides", [])
            for z in s.get("layoutSpec", {}).get("zones", [])
            if z.get("type") == "image" and z.get("imageRole") == "accent"
        )
        print(f"\u2713 Accent imagery \u2014 {accent_n} accent zone(s) within allowance")

    # 17. Structural-slide imagery uplift simplicity
    si_errors, si_warnings = check_structural_imagery_simplicity(plan, policy)
    if si_errors:
        print("\u2717 Structural-slide imagery simplicity")
        for e in si_errors:
            print(f"  ERROR: {e}")
        all_errors.extend(si_errors)
    elif si_warnings:
        print("\u26a0 Structural-slide imagery simplicity")
        for w in si_warnings:
            print(f"  WARN: {w}")
        all_warnings.extend(si_warnings)
    else:
        print("\u2713 Structural-slide imagery simplicity \u2014 no violations")

    # 17b. Structural-slide imagery uplift coverage
    su_errors, su_warnings = check_structural_imagery_uplift(plan, policy)
    if su_errors:
        print("\u2717 Structural-slide imagery uplift coverage")
        for e in su_errors:
            print(f"  ERROR: {e}")
        all_errors.extend(su_errors)
    elif su_warnings:
        print("\u26a0 Structural-slide imagery uplift coverage")
        for w in su_warnings:
            print(f"  WARN: {w}")
        all_warnings.extend(su_warnings)
    else:
        print("\u2713 Structural-slide imagery uplift coverage \u2014 OK")

    # Summary
    print()
    total = len(all_errors) + (len(all_warnings) if args.strict else 0)
    if total == 0:
        print("\u2550\u2550\u2550 PASS \u2014 Step 5 checkpoint validated \u2550\u2550\u2550")
        return 0
    else:
        print(
            f"\u2550\u2550\u2550 FAIL \u2014 {len(all_errors)} errors, "
            f"{len(all_warnings)} warnings \u2550\u2550\u2550"
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
