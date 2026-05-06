"""Check kebab-case naming for packs, SKILLs, and reference files.

Rules
-----
1. Each directory under ``packs/`` must match ``^[a-z0-9][a-z0-9-]*$``.
2. Each SKILL directory under ``packs/<pack>/.claude/skills/`` must match the same.
3. Files under ``references/`` should be lowercase with hyphens (``my-doc.md``),
   not snake_case or camelCase.
4. Python files under ``scripts/`` should be snake_case (``my_script.py``).

Usage
-----
    python scripts/check_naming.py             # check whole repo
    python scripts/check_naming.py --fix       # (not implemented; print suggestions only)
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PACKS_DIR = REPO_ROOT / "packs"
TEMPLATES_DIR = REPO_ROOT / "templates"

KEBAB_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
SNAKE_RE = re.compile(r"^[a-z0-9_]+\.py$")
KEBAB_FILE_RE = re.compile(r"^[a-z0-9][a-z0-9-]*\.[a-z0-9.]+$")

# Files allowed to keep their canonical mixed casing even though they live next
# to kebab-case content.
ALLOWED_FILES = {
    "README.md",
    "AGENTS.md",
    "CLAUDE.md",
    "SKILL.md",
    "LICENSE",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "SKILL-SPEC.md",
    "BASELINE.md",
    "Makefile",
}


def check_dir_kebab(p: Path, kind: str, errors: list[str]) -> None:
    if not KEBAB_RE.match(p.name):
        errors.append(f"{kind} '{p.relative_to(REPO_ROOT)}' is not kebab-case")


def check_packs(errors: list[str]) -> None:
    if not PACKS_DIR.exists():
        return
    for pack in sorted(PACKS_DIR.iterdir()):
        if not pack.is_dir():
            continue
        check_dir_kebab(pack, "pack", errors)

        # Two supported layouts:
        #   1) packs/<pack>/.claude/skills/<skill>/SKILL.md  (recommended)
        #   2) packs/<pack>/<skill>/SKILL.md                 (pack-root, legacy)
        skill_dirs: list[Path] = []
        skills_root = pack / ".claude" / "skills"
        if skills_root.exists():
            skill_dirs.extend(d for d in skills_root.iterdir() if d.is_dir())
        # Also discover any pack-root SKILL.md (legacy layout)
        for child in pack.iterdir():
            if child.is_dir() and (child / "SKILL.md").is_file():
                skill_dirs.append(child)

        for skill in sorted(set(skill_dirs)):
            check_dir_kebab(skill, "skill", errors)

            refs = skill / "references"
            if refs.exists():
                for ref in sorted(refs.iterdir()):
                    if not ref.is_file():
                        continue
                    if ref.name in ALLOWED_FILES:
                        continue
                    if not KEBAB_FILE_RE.match(ref.name):
                        errors.append(
                            f"reference '{ref.relative_to(REPO_ROOT)}' should be "
                            "kebab-case + extension"
                        )

            scripts = skill / "scripts"
            if scripts.exists():
                for s in sorted(scripts.iterdir()):
                    if not s.is_file() or s.suffix != ".py":
                        continue
                    if s.name in ALLOWED_FILES:
                        continue
                    if not SNAKE_RE.match(s.name):
                        errors.append(
                            f"script '{s.relative_to(REPO_ROOT)}' should be snake_case .py"
                        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--fix",
        action="store_true",
        help="(reserved) print suggestions only; never renames automatically",
    )
    args = parser.parse_args()

    errors: list[str] = []
    check_packs(errors)

    if args.fix:
        print("Note: --fix is suggestions-only; no files will be renamed.")

    if errors:
        print(f"FAIL: {len(errors)} naming issue(s):")
        for e in errors:
            print(f"  - {e}")
        return 1

    print("OK: all pack / skill / reference / script names are conformant.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
