"""Validate SKILL.md files across the repository.

Checks performed
----------------
- File exists and is non-empty
- Has YAML frontmatter delimited by `---` lines
- Frontmatter is valid YAML
- Required fields present: ``name``, ``description``
- ``name`` matches ``^[a-z0-9-]+$`` and equals the parent directory name
- ``description`` contains both "USE WHEN" and "DO NOT USE" (case-insensitive)
- ``description`` length within reasonable bounds (<= 1500 chars)

Usage
-----
    python scripts/lint_skill.py                           # all SKILL.md under packs/ and templates/
    python scripts/lint_skill.py path/to/SKILL.md          # single file
    python scripts/lint_skill.py path/to/skill-dir         # single SKILL directory

Exit code is non-zero if any check fails.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.stderr.write(
        "ERROR: PyYAML is required. Install with `pip install pyyaml` "
        "or activate a pack's conda env.\n"
    )
    sys.exit(2)


REPO_ROOT = Path(__file__).resolve().parent.parent
NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


@dataclass
class Result:
    path: Path
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def find_skill_files(target: Path) -> list[Path]:
    """Resolve a CLI argument to a concrete list of SKILL.md files."""
    if target.is_file() and target.name == "SKILL.md":
        return [target]
    if target.is_dir():
        candidate = target / "SKILL.md"
        if candidate.is_file():
            return [candidate]
        return sorted(target.rglob("SKILL.md"))
    return []


def parse_frontmatter(text: str) -> tuple[dict | None, str | None]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return None, "missing or malformed YAML frontmatter (must start with `---`)"
    try:
        data = yaml.safe_load(match.group(1))
    except yaml.YAMLError as exc:
        return None, f"YAML parse error: {exc}"
    if not isinstance(data, dict):
        return None, "frontmatter must be a YAML mapping"
    return data, None


def lint_one(path: Path) -> Result:
    result = Result(path=path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        result.errors.append(f"cannot read file: {exc}")
        return result

    if not text.strip():
        result.errors.append("file is empty")
        return result

    data, err = parse_frontmatter(text)
    if err:
        result.errors.append(err)
        return result

    # Required fields
    name = data.get("name")
    description = data.get("description")

    if not name:
        result.errors.append("frontmatter missing required field: name")
    elif not isinstance(name, str) or not NAME_PATTERN.match(name):
        result.errors.append(
            f"name '{name}' must match ^[a-z0-9-]+$ (kebab-case, no underscores or dots)"
        )
    else:
        # Templates use placeholder names; the parent-dir match only applies
        # once the SKILL has been copied into packs/.
        is_template = "templates" in path.parts
        if not is_template:
            parent = path.parent.name
            if parent != name:
                result.errors.append(
                    f"name '{name}' must equal parent directory name '{parent}'"
                )

    if not description:
        result.errors.append("frontmatter missing required field: description")
    elif not isinstance(description, str):
        result.errors.append("description must be a string")
    else:
        desc_lower = description.lower()
        # These two are SPEC requirements but downgraded to warnings for backwards
        # compatibility with pre-spec SKILLs. Use --strict in CI to enforce.
        if "use when" not in desc_lower:
            result.warnings.append(
                "description should contain 'USE WHEN' clause (see SKILL-SPEC.md)"
            )
        if "do not use" not in desc_lower:
            result.warnings.append(
                "description should contain 'DO NOT USE' clause (see SKILL-SPEC.md)"
            )
        if len(description) > 1500:
            result.warnings.append(
                f"description is long ({len(description)} chars); aim for < 1500"
            )

    # Optional sanity
    arg_hint = data.get("argument-hint")
    if arg_hint is not None and not isinstance(arg_hint, str):
        result.errors.append("argument-hint must be a string when present")

    # Body sanity (after frontmatter)
    body = FRONTMATTER_RE.sub("", text, count=1).strip()
    if not body:
        result.warnings.append("SKILL.md has no body after frontmatter")

    return result


def format_result(result: Result) -> str:
    rel = result.path.relative_to(REPO_ROOT) if REPO_ROOT in result.path.parents else result.path
    lines = []
    if result.errors:
        lines.append(f"FAIL  {rel}")
        for err in result.errors:
            lines.append(f"  - error:   {err}")
    else:
        lines.append(f"OK    {rel}")
    for warn in result.warnings:
        lines.append(f"  - warning: {warn}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "targets",
        nargs="*",
        help="SKILL.md files or directories. Default: packs/ and templates/",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as errors",
    )
    args = parser.parse_args()

    if args.targets:
        targets = [Path(t).resolve() for t in args.targets]
    else:
        targets = [REPO_ROOT / "packs", REPO_ROOT / "templates"]

    files: list[Path] = []
    for t in targets:
        if not t.exists():
            print(f"WARN: target does not exist: {t}", file=sys.stderr)
            continue
        files.extend(find_skill_files(t))

    files = sorted(set(files))
    if not files:
        print("No SKILL.md files found.", file=sys.stderr)
        return 0

    failed = 0
    warned = 0
    for f in files:
        result = lint_one(f)
        print(format_result(result))
        if not result.ok:
            failed += 1
        if result.warnings:
            warned += 1

    print()
    print(f"Checked {len(files)} file(s); {failed} failed, {warned} with warnings.")

    if failed:
        return 1
    if args.strict and warned:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
