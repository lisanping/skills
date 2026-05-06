#!/usr/bin/env python3
"""Step 5 checkpoint validator — slide-plan.json + style-policy.json + slide-content.json.

Run after Step 5c. Verifies structural and business-rule constraints
that the JSON Schemas alone cannot catch (cross-artifact consistency,
mode x strategy legality, layoutRef existence in the template profile).

Checks:
  1.  JSON Schema validation for slide-plan / style-policy (best-effort
      if `jsonschema` is installed; soft-skipped otherwise).
  2.  taskId uniqueness in slide-plan.
  3.  Exactly one `cover` (first slide) and one `closing` (last slide).
  4.  All `divider` slides share the same `cloneSource` (or, if none,
      the same `layoutRef`).
  5.  Mode x strategy legality:
        - strict: forbids `augmented-clone`; forbids `spec-composed`
          unless the only viable choice (warn, not error).
        - balanced: allows all four.
        - creative: allows all four.
  6.  slide-plan slide count matches content-outline.json
      (intent.slideCount + sum of section.slideCount, if available).
  7.  slide-content.json has an entry for every taskId in slide-plan.
  8.  Each slot.text length <= slot.charBudget (warning).
  9.  layoutRef and cloneSource (when provided) exist in the template
      profile (if --profile passed).
  10. style-policy.palette values are theme slot names, not hex.
  11. style-policy.mode equals slide-plan.mode.

Usage:
  python validate_plan.py <session_dir>
  python validate_plan.py <session_dir> --profile path/to/template-profile.json
  python validate_plan.py <session_dir> --strict          # treat warnings as errors
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

THEME_SLOTS = {
    "bg1", "bg2", "lt1", "lt2", "dk1", "dk2", "tx1", "tx2",
    "accent1", "accent2", "accent3", "accent4", "accent5", "accent6",
    "hlink", "folHlink",
}

STRATEGIES_BY_MODE = {
    "strict": {"clone-sample", "clone-layout"},
    "balanced": {"clone-sample", "clone-layout", "augmented-clone", "spec-composed"},
    "creative": {"clone-sample", "clone-layout", "augmented-clone", "spec-composed"},
}


def load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def schema_validate(instance: dict, schema_path: Path) -> list[str]:
    """Best-effort schema validation. Returns errors as strings."""
    try:
        import jsonschema  # type: ignore
    except ImportError:
        return []  # silently skip
    if not schema_path.exists():
        return []
    schema = json.load(open(schema_path, encoding="utf-8"))
    try:
        jsonschema.validate(instance, schema)
        return []
    except jsonschema.ValidationError as err:
        return [f"{schema_path.name}: {err.message} at {list(err.absolute_path)}"]


# ---------- individual checks ----------

def check_task_id_uniqueness(plan: dict) -> list[str]:
    seen, dupes = set(), []
    for s in plan.get("slides", []):
        tid = s.get("taskId")
        if tid in seen:
            dupes.append(tid)
        seen.add(tid)
    return [f"Duplicate taskId: {t}" for t in dupes]


def check_bookends(plan: dict) -> list[str]:
    errors = []
    slides = plan.get("slides", [])
    if not slides:
        return ["slide-plan has no slides"]
    if slides[0].get("semanticRole") != "cover":
        errors.append(f"First slide must be 'cover', got '{slides[0].get('semanticRole')}'")
    if slides[-1].get("semanticRole") != "closing":
        errors.append(f"Last slide must be 'closing', got '{slides[-1].get('semanticRole')}'")
    cover_count = sum(1 for s in slides if s.get("semanticRole") == "cover")
    closing_count = sum(1 for s in slides if s.get("semanticRole") == "closing")
    if cover_count != 1:
        errors.append(f"Expected exactly 1 cover, found {cover_count}")
    if closing_count != 1:
        errors.append(f"Expected exactly 1 closing, found {closing_count}")
    return errors


def check_divider_consistency(plan: dict) -> list[str]:
    dividers = [s for s in plan.get("slides", []) if s.get("semanticRole") == "divider"]
    if len(dividers) < 2:
        return []
    sources = {d.get("cloneSource") for d in dividers}
    if len(sources) > 1 and None not in sources:
        return [f"Dividers must share cloneSource; found {sorted(s for s in sources if s)}"]
    if None in sources:
        # All dividers without cloneSource must share layoutRef.
        no_source_layouts = {d.get("layoutRef") for d in dividers if d.get("cloneSource") is None}
        if len(no_source_layouts) > 1:
            return [f"Dividers without cloneSource must share layoutRef; found {sorted(no_source_layouts)}"]
    return []


def check_mode_strategy(plan: dict) -> tuple[list[str], list[str]]:
    errors, warnings = [], []
    mode = plan.get("mode")
    allowed = STRATEGIES_BY_MODE.get(mode)
    if allowed is None:
        return [f"Unknown mode: {mode}"], []
    for s in plan.get("slides", []):
        strat = s.get("strategy")
        if strat not in allowed:
            if mode == "strict" and strat == "spec-composed":
                warnings.append(
                    f"{s.get('taskId')}: spec-composed in strict mode — only allowed when no layout fits"
                )
            else:
                errors.append(f"{s.get('taskId')}: strategy '{strat}' forbidden in mode '{mode}'")
    return errors, warnings


def check_outline_coverage(plan: dict, outline: dict | None) -> list[str]:
    if not outline:
        return []
    target = outline.get("intent", {}).get("slideCount")
    actual = len(plan.get("slides", []))
    if target is not None and target != actual:
        return [f"slide-plan has {actual} slides; content-outline.intent.slideCount = {target}"]
    return []


def check_content_coverage(plan: dict, content: dict | None) -> tuple[list[str], list[str]]:
    if not content:
        return ["slide-content.json missing"], []
    plan_ids = {s.get("taskId") for s in plan.get("slides", [])}
    content_ids = {s.get("taskId") for s in content.get("slides", [])}
    missing = plan_ids - content_ids
    extra = content_ids - plan_ids
    errors = []
    if missing:
        errors.append(f"slide-content missing taskIds: {sorted(missing)}")
    warnings = []
    if extra:
        warnings.append(f"slide-content has unused taskIds: {sorted(extra)}")
    return errors, warnings


def check_char_budgets(content: dict | None) -> list[str]:
    if not content:
        return []
    warnings = []
    for s in content.get("slides", []):
        for slot in s.get("slots", []):
            text = slot.get("text") or ""
            budget = slot.get("charBudget")
            if budget is not None and len(text) > budget and text.strip().upper() != "TBD":
                warnings.append(
                    f"{s.get('taskId')}.{slot.get('placeholder')}: "
                    f"text length {len(text)} > charBudget {budget}"
                )
    return warnings


def check_layout_refs(plan: dict, profile: dict | None) -> list[str]:
    if not profile:
        return []
    layouts_in_profile = set()
    for layout in profile.get("layouts", []):
        name = layout.get("file") or layout.get("filename") or layout.get("name")
        if name:
            layouts_in_profile.add(name)
    if not layouts_in_profile:
        return []
    errors = []
    for s in plan.get("slides", []):
        ref = s.get("layoutRef")
        if ref and ref not in layouts_in_profile:
            errors.append(f"{s.get('taskId')}: layoutRef '{ref}' not in template profile")
    return errors


def check_palette_theme(policy: dict | None) -> list[str]:
    if not policy:
        return []
    errors = []
    palette = policy.get("palette", {})
    for role, val in palette.items():
        if isinstance(val, str) and val.startswith("#"):
            errors.append(f"palette.{role} = '{val}' is a hex color; must be a theme slot")
        elif isinstance(val, str) and val not in THEME_SLOTS:
            errors.append(f"palette.{role} = '{val}' is not a known theme slot")
    return errors


def check_mode_alignment(plan: dict, policy: dict | None) -> list[str]:
    if not policy:
        return []
    pm, sm = plan.get("mode"), policy.get("mode")
    if pm and sm and pm != sm:
        return [f"slide-plan.mode='{pm}' != style-policy.mode='{sm}'"]
    return []


# ---------- runner ----------

def report(name: str, errors: list[str], warnings: list[str] | None = None) -> None:
    warnings = warnings or []
    if errors:
        print(f"X {name}")
        for e in errors:
            print(f"  ERROR: {e}")
    elif warnings:
        print(f"! {name}")
        for w in warnings:
            print(f"  WARN: {w}")
    else:
        print(f"+ {name}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Step 5 checkpoint validator for branded-pptx-generator")
    parser.add_argument("session_dir", type=Path)
    parser.add_argument("--profile", type=Path, help="Path to template-profile.json from pptx-profiler")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as failures")
    args = parser.parse_args()

    session = args.session_dir.resolve()
    plan = load_json(session / "slide-plan.json")
    policy = load_json(session / "style-policy.json")
    content = load_json(session / "slide-content.json")
    outline = load_json(session / "content-outline.json")
    profile = load_json(args.profile) if args.profile else None

    if not plan:
        print(f"FAIL: slide-plan.json not found in {session}")
        return 1
    if not policy:
        print(f"FAIL: style-policy.json not found in {session}")
        return 1

    print(f"Validating Step 5 checkpoint in: {session.name}")
    print(f"  Slides in plan: {len(plan.get('slides', []))}")
    print(f"  Mode: {plan.get('mode')}")
    print(f"  Outline available: {outline is not None}")
    print(f"  Content available: {content is not None}")
    print(f"  Profile available: {profile is not None}")
    print()

    schema_dir = Path(__file__).resolve().parent.parent / "schemas"
    all_errors: list[str] = []
    all_warnings: list[str] = []

    # 1. Schema
    e = schema_validate(plan, schema_dir / "slide_plan_schema.json")
    e += schema_validate(policy, schema_dir / "style_policy_schema.json")
    if outline:
        e += schema_validate(outline, schema_dir / "content_outline_schema.json")
    report("JSON Schema", e); all_errors += e

    # 2. taskId uniqueness
    e = check_task_id_uniqueness(plan)
    report("taskId uniqueness", e); all_errors += e

    # 3. Bookends
    e = check_bookends(plan)
    report("Bookends (cover/closing)", e); all_errors += e

    # 4. Divider consistency
    e = check_divider_consistency(plan)
    report("Divider consistency", e); all_errors += e

    # 5. Mode x strategy
    e, w = check_mode_strategy(plan)
    report("Mode x strategy", e, w); all_errors += e; all_warnings += w

    # 6. Outline coverage
    e = check_outline_coverage(plan, outline)
    report("Outline coverage", e); all_errors += e

    # 7. Content coverage
    e, w = check_content_coverage(plan, content)
    report("Content coverage", e, w); all_errors += e; all_warnings += w

    # 8. charBudget
    w = check_char_budgets(content)
    report("Slot charBudget", [], w); all_warnings += w

    # 9. layoutRef in profile
    e = check_layout_refs(plan, profile)
    report("layoutRef existence", e); all_errors += e

    # 10. Palette theme slots
    e = check_palette_theme(policy)
    report("Palette theme slots", e); all_errors += e

    # 11. Mode alignment
    e = check_mode_alignment(plan, policy)
    report("Mode alignment (plan vs policy)", e); all_errors += e

    print()
    fail = len(all_errors) + (len(all_warnings) if args.strict else 0)
    if fail == 0:
        print(f"=== PASS — {len(all_warnings)} warnings ===")
        return 0
    print(f"=== FAIL — {len(all_errors)} errors, {len(all_warnings)} warnings ===")
    return 1


if __name__ == "__main__":
    sys.exit(main())
