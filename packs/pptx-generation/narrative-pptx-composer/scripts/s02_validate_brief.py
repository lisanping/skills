"""Step 2 checkpoint validator — s02-communication-brief.json.

Verifies:
  1. s02-communication-brief.json exists.
  2. presentationPurpose is one of {inform, persuade, report, propose, inspire}.
  3. purposeStatement is a non-empty string.
  4. audience.who is a non-empty string. audience.decisionPower is
     required when presentationPurpose ∈ {persuade, propose, report}.
  5. communicationObjectives has concrete entries for think/feel/do.
  6. keyMessages has >= 1 entry; each has a message + valid evidence source.
  7. constraints.{language, formalityLevel} are present.
  8. Every entry in `inferences[]`, if present, has the required
     {field, value, basis, confidence} shape.

Out of scope (handled elsewhere):
  - `slideCountConstraint` — extracted in s01b, arbitrated in Step 3c.
  - `imageryDemand` — derived in Step 5b; written to
    s05b-style-policy.json → visualTone.imageryDemand.

Usage:
  python s02_validate_brief.py <session_dir>
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

VALID_EVIDENCE = {"document", "generated", "hybrid"}
VALID_PURPOSE = {"inform", "persuade", "report", "propose", "inspire"}
VALID_CONFIDENCE = {"low", "medium", "high"}
DECISION_PURPOSES = {"persuade", "propose", "report"}


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

    s02_path = session / "s02-communication-brief.json"
    if not s02_path.exists():
        print(f"  ✗ missing artifact: {s02_path.name}")
        return 1

    s02 = load_json(s02_path)

    # 1. presentationPurpose enum (accept string or {primary: <enum>, ...})
    purpose = s02.get("presentationPurpose")
    purpose_value = purpose.get("primary") if isinstance(purpose, dict) else purpose
    if purpose_value not in VALID_PURPOSE:
        errors.append(
            f"s02.presentationPurpose = {purpose!r}; "
            f"must be (or contain `primary`) one of {sorted(VALID_PURPOSE)}"
        )

    # 2. purposeStatement non-empty
    statement = s02.get("purposeStatement")
    if not isinstance(statement, str) or not statement.strip():
        errors.append(
            "s02.purposeStatement is empty; must be a one-sentence "
            "statement naming the audience and the desired change"
        )

    # 3. audience.who minimal; decisionPower conditional
    audience = s02.get("audience") or {}
    who = audience.get("who")
    if not isinstance(who, str) or not who.strip():
        errors.append(
            "s02.audience.who is empty; thin briefs still need a "
            "concrete (possibly inferred) audience description"
        )
    if purpose_value in DECISION_PURPOSES:
        dp = audience.get("decisionPower")
        if not isinstance(dp, str) or not dp.strip():
            errors.append(
                f"s02.audience.decisionPower is required when "
                f"presentationPurpose='{purpose_value}'"
            )

    # 4. communicationObjectives think/feel/do
    objectives = s02.get("communicationObjectives") or {}
    for dim in ("think", "feel", "do"):
        val = objectives.get(dim)
        if not val or not isinstance(val, str) or not val.strip():
            errors.append(
                f"s02.communicationObjectives.{dim} is empty; "
                f"thin briefs still need a concrete value"
            )

    # 5. keyMessages >= 1, each has message + evidence
    key_messages = s02.get("keyMessages") or []
    if not key_messages:
        errors.append("s02.keyMessages is empty; need >= 1 message")
    elif len(key_messages) > 5:
        warnings.append(
            f"s02.keyMessages has {len(key_messages)} entries; "
            f"recommended max is 5"
        )
    for i, km in enumerate(key_messages):
        if not isinstance(km, dict):
            errors.append(f"s02.keyMessages[{i}] is not an object")
            continue
        if not km.get("message"):
            errors.append(f"s02.keyMessages[{i}].message is missing")
        ev = km.get("evidence")
        if ev not in VALID_EVIDENCE:
            errors.append(
                f"s02.keyMessages[{i}].evidence = {ev!r}; "
                f"must be one of {sorted(VALID_EVIDENCE)}"
            )

    # 6. constraints minimal fields
    constraints = s02.get("constraints") or {}
    for f in ("language", "formalityLevel"):
        v = constraints.get(f)
        if not isinstance(v, str) or not v.strip():
            errors.append(f"s02.constraints.{f} is empty; required")

    # 6a. Forbidden field — slideCountConstraint lives on s01b
    if "slideCountConstraint" in constraints:
        errors.append(
            "s02.constraints.slideCountConstraint is forbidden; "
            "the user-given quantity constraint lives on "
            "s01b-query-intent.json → explicitSignals.slideCountConstraint "
            "and is consumed directly by Step 3c. Remove from s02."
        )

    # 6b. Forbidden field — imageryDemand lives on s05d (Step 5b)
    if "imageryDemand" in s02:
        errors.append(
            "s02.imageryDemand is forbidden; the resolved imagery demand "
            "is derived in Step 5b and written to "
            "s05b-style-policy.json → visualTone.imageryDemand. "
            "Remove from s02."
        )

    # 7. inferences[] shape (if present)
    inferences = s02.get("inferences") or []
    if not isinstance(inferences, list):
        errors.append("s02.inferences must be a list when present")
        inferences = []
    for i, inf in enumerate(inferences):
        if not isinstance(inf, dict):
            errors.append(f"s02.inferences[{i}] is not an object")
            continue
        for k in ("field", "value", "basis", "confidence"):
            if k not in inf:
                errors.append(f"s02.inferences[{i}].{k} is missing")
        conf = inf.get("confidence")
        if conf is not None and conf not in VALID_CONFIDENCE:
            errors.append(
                f"s02.inferences[{i}].confidence = {conf!r}; "
                f"must be one of {sorted(VALID_CONFIDENCE)}"
            )

    # Report
    for w in warnings:
        print(f"  ! {w}")
    for e in errors:
        print(f"  ✗ {e}")

    if errors:
        print(f"\nStep 2 validation FAILED ({len(errors)} error(s), "
              f"{len(warnings)} warning(s))")
        return 1

    print(f"\nStep 2 validation OK ({len(warnings)} warning(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
