#!/usr/bin/env python3
"""Step 1 checkpoint validator — s01b/s01c/s01d artifacts.

Verifies:
  1. All three required artifacts exist (s01b-query-intent.json,
     s01c-content-digest.json, s01d-design-config.json)
  2. s01b.inputMode is one of {generate, beautify, reproduce, expand}
  3. s01b.inputSources is internally consistent
     (queryOnly => documents/images empty; image-mode requires images;
     generate + images is forbidden — promote to expand)
  4. When s01b.inputSources.images is non-empty, s01c-image-style-extraction.json
     exists with one entry per source image
  5. s01b.inferences entries are whitelisted — only `language` and
     `inputMode` are allowed; everything else (audience/purpose →
     Step 2; design fields → Step 5b) is forbidden (workflow-step1.md § 1b)
  6. Language is set somewhere — either s01b.explicitSignals.language
     or an inferences[] entry with field="language"
  7. s01d.source is one of {user-explicit, reference-image, deferred}
     (the legacy value `content-derived` is rejected — Step 1 no longer
     infers design fields from content)
  8. s01d.dimensions has width/height/unit; values are numeric > 0;
     unit ∈ {inches, cm, emu}
  9. s01d.sourceProvenance MUST cover every leaf in dimensions/palette/
     typography/style (regardless of whether the leaf value is null);
     every value must be one of {user-explicit, reference-image,
     system-default, deferred-step5b} (workflow-step1.md § 1d).
     `content-inferred` is rejected.
 10. Null leaves MUST have provenance `deferred-step5b`; non-null leaves
     MUST NOT have provenance `deferred-step5b`. This forces every value
     to be honestly attributed to user/image/system or explicitly punted.
 11. s01d.typography includes monoFont (defaults to JetBrains Mono if
     omitted by path 1/2)
 12. s01d.typography.secondaryFont is present (string or null — must be
     written explicitly per workflow-step1.md § 1d)

Also verifies (when present):
 12. s01b.explicitSignals.slideCountConstraint, when non-null, has a
     valid shape ({type:exact,value}/{type:range,min,max}/{type:duration,minutes})

Note: imageryDemand is now a Step 5b field (written to
s05b-style-policy.json → visualTone.imageryDemand and validated by
s05_validate_plan.py).

Usage:
  python s01_validate_inputs.py <session_dir>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

VALID_INPUT_MODES = {"generate", "beautify", "reproduce", "expand"}
VALID_DESIGN_SOURCES = {"user-explicit", "reference-image", "deferred"}
VALID_DIMENSION_UNITS = {"inches", "cm", "emu"}
VALID_SLIDE_COUNT_TYPES = {"exact", "range", "duration"}
VALID_PROVENANCE_VALUES = {
    "user-explicit", "reference-image", "system-default",
    "deferred-step5b",
}
# Whitelist of fields allowed in s01b.inferences[]. Step 1 only infers
# language (script detection) and may record an inputMode rationale.
# Everything else is forbidden — see workflow-step1.md § 1b.
INFERENCE_FIELD_WHITELIST = {"language", "inputMode"}
# All sourceProvenance keys that must always be present in s01d,
# regardless of whether the corresponding leaf is null.
REQUIRED_PROVENANCE_KEYS = (
    "dimensions",
    "palette",
    "typography.headingFont",
    "typography.bodyFont",
    "typography.monoFont",
    "typography.secondaryFont",
    "style.contrast",
    "style.motif",
    "style.iconStyle",
)


def validate_slide_count_constraint(c: object) -> str | None:
    """Return error message or None."""
    if c is None:
        return None
    if not isinstance(c, dict):
        return "must be an object or null"
    t = c.get("type")
    if t not in VALID_SLIDE_COUNT_TYPES:
        return f"type={t!r}; must be one of {sorted(VALID_SLIDE_COUNT_TYPES)}"
    if t == "exact":
        if not isinstance(c.get("value"), int) or c["value"] <= 0:
            return "type=exact requires positive int `value`"
    elif t == "range":
        mn, mx = c.get("min"), c.get("max")
        if not (isinstance(mn, int) and isinstance(mx, int) and 0 < mn <= mx):
            return "type=range requires int `min` <= int `max`, both > 0"
    elif t == "duration":
        if not isinstance(c.get("minutes"), (int, float)) or c["minutes"] <= 0:
            return "type=duration requires positive `minutes`"
    return None


def load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("session_dir")
    args = parser.parse_args()

    session = Path(args.session_dir)
    errors: list[str] = []
    warnings: list[str] = []

    # 1. Required artifacts
    s01b_path = session / "s01b-query-intent.json"
    s01c_path = session / "s01c-content-digest.json"
    s01d_path = session / "s01d-design-config.json"

    for label, path in [("s01b", s01b_path), ("s01c", s01c_path),
                        ("s01d", s01d_path)]:
        if not path.exists():
            errors.append(f"missing artifact: {path.name}")

    if errors:
        for e in errors:
            print(f"  ✗ {e}")
        return 1

    s01b = load_json(s01b_path)
    s01d = load_json(s01d_path)

    # 2. inputMode enum
    mode = s01b.get("inputMode")
    if mode not in VALID_INPUT_MODES:
        errors.append(
            f"s01b.inputMode = {mode!r}; must be one of {sorted(VALID_INPUT_MODES)}"
        )

    # 3. inputSources consistency
    sources = s01b.get("inputSources", {}) or {}
    docs = sources.get("documents", []) or []
    imgs = sources.get("images", []) or []
    query_only = bool(sources.get("queryOnly", False))

    if query_only and (docs or imgs):
        errors.append(
            "s01b.inputSources.queryOnly=true but documents/images non-empty"
        )
    if not query_only and not docs and not imgs:
        warnings.append(
            "s01b.inputSources has no documents, no images, and queryOnly=false; "
            "expected queryOnly=true for chat-only briefs"
        )
    if mode in {"beautify", "reproduce"} and not imgs:
        errors.append(
            f"s01b.inputMode={mode!r} requires inputSources.images to be non-empty"
        )
    if mode == "generate" and imgs:
        errors.append(
            "s01b.inputMode='generate' but images are present; promote to 'expand' "
            "(image as one of several inputs) — see workflow-step1.md § 1b"
        )

    # 4. Image-style extraction parity
    if imgs:
        ext_path = session / "s01c-image-style-extraction.json"
        if not ext_path.exists():
            errors.append(
                "inputSources.images is non-empty but "
                "s01c-image-style-extraction.json is missing"
            )
        else:
            ext = load_json(ext_path)
            entries = ext if isinstance(ext, list) else ext.get("images", [ext])
            if len(entries) < len(imgs):
                warnings.append(
                    f"s01c-image-style-extraction.json has {len(entries)} entries "
                    f"but inputSources.images has {len(imgs)}"
                )

    # 5. inferences[] field whitelist — only `language` and `inputMode`
    for entry in (s01b.get("inferences") or []):
        if not isinstance(entry, dict):
            errors.append(
                f"s01b.inferences entry is not an object: {entry!r}"
            )
            continue
        field = entry.get("field", "")
        top = field.split(".", 1)[0] if isinstance(field, str) else ""
        if field not in INFERENCE_FIELD_WHITELIST and top not in INFERENCE_FIELD_WHITELIST:
            errors.append(
                f"s01b.inferences contains forbidden field {field!r}; "
                f"only {sorted(INFERENCE_FIELD_WHITELIST)} are allowed in "
                f"Step 1 (audience/purpose → Step 2; design fields → "
                f"Step 5b) — workflow-step1.md § 1b"
            )

    # 6. Language must be set somewhere on s01b
    explicit = s01b.get("explicitSignals") or {}
    explicit_lang = explicit.get("language")
    inferred_lang = any(
        isinstance(e, dict) and e.get("field") == "language" and e.get("value")
        for e in (s01b.get("inferences") or [])
    )
    if not explicit_lang and not inferred_lang:
        errors.append(
            "language is unset on s01b — populate either explicitSignals.language "
            "or an inferences[] entry with field='language' (drives Step 4 phrasing "
            "and Step 5f image-prompt language)"
        )

    # 7. s01d.source enum
    src = s01d.get("source")
    if src not in VALID_DESIGN_SOURCES:
        errors.append(
            f"s01d.source = {src!r}; must be one of {sorted(VALID_DESIGN_SOURCES)}"
        )

    # 8. s01d.dimensions presence + numeric + unit enum
    dims = s01d.get("dimensions") or {}
    for k in ("width", "height", "unit"):
        if k not in dims:
            errors.append(f"s01d.dimensions.{k} is missing")
    w, h, u = dims.get("width"), dims.get("height"), dims.get("unit")
    if isinstance(w, (int, float)) and w <= 0:
        errors.append(f"s01d.dimensions.width must be > 0 (got {w!r})")
    if isinstance(h, (int, float)) and h <= 0:
        errors.append(f"s01d.dimensions.height must be > 0 (got {h!r})")
    if u is not None and u not in VALID_DIMENSION_UNITS:
        errors.append(
            f"s01d.dimensions.unit = {u!r}; must be one of "
            f"{sorted(VALID_DIMENSION_UNITS)}"
        )

    # 9-10. sourceProvenance — mandatory + field-grain + enum + null-coupled
    #    Every leaf in dimensions/palette/typography/style MUST appear as a
    #    key with one of VALID_PROVENANCE_VALUES (regardless of whether the
    #    leaf is null). Null leaves MUST be declared deferred-step5b; non-
    #    null leaves MUST NOT be deferred-step5b. This forces honest
    #    attribution: the LLM cannot silently invent values, and cannot
    #    silently leave fields null without declaring deferral.
    typo = s01d.get("typography") or {}
    prov = s01d.get("sourceProvenance") or {}
    if not isinstance(prov, dict):
        errors.append("s01d.sourceProvenance must be an object")
        prov = {}

    palette = s01d.get("palette")
    style = s01d.get("style") or {}

    def _leaf_value(key: str):
        if key == "dimensions":
            return dims if dims else None
        if key == "palette":
            if isinstance(palette, dict) and any(v for v in palette.values()):
                return palette
            return None
        if key.startswith("typography."):
            return typo.get(key.split(".", 1)[1])
        if key.startswith("style."):
            if isinstance(style, dict):
                return style.get(key.split(".", 1)[1])
            return None
        return None

    for k in REQUIRED_PROVENANCE_KEYS:
        if k not in prov:
            errors.append(
                f"s01d.sourceProvenance missing required entry for {k!r}; "
                f"every leaf must declare its origin (one of "
                f"{sorted(VALID_PROVENANCE_VALUES)}) — workflow-step1.md § 1d"
            )
            continue
        pv = prov[k]
        if pv not in VALID_PROVENANCE_VALUES:
            errors.append(
                f"s01d.sourceProvenance[{k!r}] = {pv!r}; must be one of "
                f"{sorted(VALID_PROVENANCE_VALUES)} (note: 'content-inferred' "
                f"is no longer accepted — Step 1 does not infer design fields "
                f"from content; use 'deferred-step5b' instead)"
            )
            continue
        leaf = _leaf_value(k)
        if leaf is None and pv != "deferred-step5b":
            errors.append(
                f"s01d.sourceProvenance[{k!r}] = {pv!r} but the leaf value "
                f"is null/empty; null leaves must be declared 'deferred-step5b' "
                f"— workflow-step1.md § 1d"
            )
        if leaf is not None and pv == "deferred-step5b":
            errors.append(
                f"s01d.sourceProvenance[{k!r}] = 'deferred-step5b' but the "
                f"leaf value is non-null ({leaf!r}); deferred-step5b is only "
                f"valid when the value is null"
            )

    # 10. typography.monoFont (warn only — has a sane default)
    if not typo.get("monoFont"):
        warnings.append(
            "s01d.typography.monoFont is missing; "
            "default to 'JetBrains Mono' (required by code-explain-split / terminal-hero)"
        )

    # 11. secondaryFont must be present (even if null)
    if "secondaryFont" not in typo:
        errors.append(
            "s01d.typography.secondaryFont is absent; "
            "write the field explicitly (string or null) per workflow-step1.md § 1d"
        )

    # 12. slideCountConstraint shape (when present)
    scc = explicit.get("slideCountConstraint")
    if "slideCount" in explicit:
        errors.append(
            "s01b.explicitSignals.slideCount is forbidden; "
            "rename to `slideCountConstraint` and use the structured shape "
            "({type:exact,value} / {type:range,min,max} / {type:duration,minutes}) "
            "per workflow-step1.md § 1b"
        )
    scc_err = validate_slide_count_constraint(scc)
    if scc_err:
        errors.append(
            f"s01b.explicitSignals.slideCountConstraint: {scc_err}"
        )

    # Report
    for warn in warnings:
        print(f"  ! {warn}")
    for e in errors:
        print(f"  ✗ {e}")

    if errors:
        print(f"\nStep 1 validation FAILED ({len(errors)} error(s), "
              f"{len(warnings)} warning(s))")
        return 1

    print(f"\nStep 1 validation OK ({len(warnings)} warning(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
