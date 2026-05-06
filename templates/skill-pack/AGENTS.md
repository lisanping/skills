# AGENTS.md (pack-level)

> Second-level routing for tasks scoped to this pack. Agents should read this file before opening any SKILL.md inside the pack.

## Pack purpose

One sentence describing the problem domain, inputs, and outputs of this pack.

## SKILL routing

| Task                    | Read first                             |
| ----------------------- | -------------------------------------- |
| TODO describe task type | `.claude/skills/<skill-name>/SKILL.md` |

## Variables

| Variable      | Value            |
| ------------- | ---------------- |
| `SKILLS_ROOT` | `.claude/skills` |

All SKILL paths are relative to `SKILLS_ROOT`.

## Key commands

```bash
conda activate <pack-name>
pytest tests/ -v
```

## Conventions

- Source code: `src/<package>/`
- Examples: `examples/`
- Output: `output/` (git-ignored)
- Tests: `tests/test_*.py`
