# Repository-level scripts

Repository-wide tooling that does **not** belong to any pack. These scripts are read-only — they validate and lint, never generate.

| Script                             | Purpose                                                                                                 |
| ---------------------------------- | ------------------------------------------------------------------------------------------------------- |
| [lint_skill.py](lint_skill.py)     | Validate every `SKILL.md` frontmatter (`name` / `description` / kebab-case / `USE WHEN` / `DO NOT USE`) |
| [check_naming.py](check_naming.py) | Check naming of pack / SKILL / `references/` / `scripts/` directories and files                         |

## Running locally

Only `pyyaml` is required. Any pack's conda env will already have it; otherwise install it standalone:

```bash
pip install pyyaml
python scripts/lint_skill.py            # lint all SKILL.md
python scripts/lint_skill.py --strict   # treat warnings as errors (matches CI)
python scripts/check_naming.py
```

## In CI

See [.github/workflows/lint.yml](../.github/workflows/lint.yml). CI runs `lint_skill.py --strict` and `check_naming.py` on every push and pull request to `main`.

> CI does **not** run pytest or prompt-evals — those live inside individual packs (`packs/<pack>/tests/`) and are owned by each pack's maintainer.
