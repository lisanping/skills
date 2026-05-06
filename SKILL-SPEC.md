# SKILL Authoring Specification

This document defines the format and quality rules that **every** SKILL in this repository must follow. The machine-checkable subset is enforced in CI via [scripts/lint_skill.py](scripts/lint_skill.py).

> The spec extends the Anthropic Agent Skills convention with a few repository-specific constraints.

---

## 1. File location

```text
packs/<pack-name>/.claude/skills/<skill-name>/
├── SKILL.md            # required
├── references/         # optional — long-form knowledge, loaded on demand
│   └── *.md / *.yaml / *.json
└── scripts/            # optional — executable scripts, invoked explicitly by SKILL.md
    └── *.py
```

- `<skill-name>` must be kebab-case and **equal to** the `name` field in the SKILL.md frontmatter.
- `references/` and `scripts/` are both optional; many document-oriented SKILLs only have `references/`.

> **Compatibility layout.** Existing packs are also allowed to place SKILLs at the pack root (`packs/<pack>/<skill>/SKILL.md`). New packs **should prefer** the `.claude/skills/` layout to align with the Claude Code default; the linter accepts both.

---

## 2. SKILL.md structure

### 2.1 YAML frontmatter (required)

```yaml
---
name: my-skill
description: |
  One-paragraph description.
  USE WHEN the user wants to <trigger 1> / <trigger 2>.
  DO NOT USE for <anti-trigger 1> / <anti-trigger 2>.
argument-hint: 'one-line description of expected user input'
---
```

| Field           | Required    | Rule                                                                                               |
| --------------- | ----------- | -------------------------------------------------------------------------------------------------- |
| `name`          | ✅           | `^[a-z0-9-]+$`, equal to the directory name                                                        |
| `description`   | ✅           | Must contain **USE WHEN** and **DO NOT USE**; aim for 2–5 sentences, under 200 characters of prose |
| `argument-hint` | recommended | One-line description of what the user should provide; wrap in single quotes                        |
| `version`       | optional    | semver, e.g. `1.0.0`                                                                               |

> ❗ `description` is the **only** signal an agent uses to route to a SKILL — the more specific it is, the lower the risk of false triggers.
>
> CI runs `python scripts/lint_skill.py --strict` by default: missing `USE WHEN` / `DO NOT USE` will fail the PR. Local quick checks can omit `--strict`, in which case those become warnings.

### 2.2 Body structure (recommended)

```markdown
# <skill-name> SKILL

## What this skill does
A short paragraph stating the inputs, outputs, and boundaries of this SKILL.

## When to use / When NOT to use
Restate the trigger conditions from the frontmatter; add 1–2 examples if helpful.

## Workflow
Step-by-step description of how the agent should execute:
1. Read references/<file>.md
2. Invoke scripts/<script>.py
3. Validate the artifact and report

## Key entry points
| Entry | When to use |
| ----- | ----------- |

## Constraints
Hard rules that must not be violated (e.g. "output must be UTF-8", "never overwrite the input file").

## References
- references/<file>.md — when to read it on demand
```

---

## 3. references/ authoring rules

- **Load on demand.** Put long-form material that is not always needed into `references/`. Link from `SKILL.md` with a relative link `[xxx](references/xxx.md)`; the agent will only fetch it when it sees the link.
- **One topic per file.** Avoid mixing spec text + templates + examples in a single reference.
- **Split threshold.** Consider splitting a reference once it exceeds roughly 500 lines.
- **State the version of any cited standard.** For example `GB 50016—2014 (2018 revision)`. At the top of the reference, declare "verify the currently effective version before use."

---

## 4. scripts/ authoring rules

- **Runnable standalone.** `python scripts/foo.py --help` must produce valid usage.
- **CLI parameterized.** Paths and parameters go through the command line; nothing hardcoded.
- **Diagnosable failures.** Exception messages include actionable suggestions (e.g. `fix_action: ...`).
- **No hidden side effects.** Do not modify input files unless the caller passes `--write`.
- **No network access** unless the SKILL explicitly states it and obtains user consent.

---

## 5. Description template (paste-ready)

```yaml
description: |
  <One sentence describing what this skill does>.
  USE WHEN the user wants to <action 1> / <action 2> / <action 3>.
  DO NOT USE for <out-of-scope 1> / <out-of-scope 2>.
```

**Good example** (from [aec-building](packs/aec-generation/aec-building/SKILL.md)):

> AEC building modeling skill — parametric architectural geometry for Agent harness.
> USE when the task involves creating building geometry (floors, columns, walls, curtain walls, stairs), running code compliance checks (GB 50016, JGJ/T 67), exporting to STEP/IFC/GLB, or orchestrating multi-step building design workflows via MCP tools.
> DO NOT USE for MEP / structural calculation / rendering / site design.

**Bad example**:

> "A skill for buildings." ← too generic; the agent has no basis for deciding when to trigger.

---

## 6. Modification workflow (recap)

See [CONTRIBUTING.md](CONTRIBUTING.md) "Modification workflow". Key points:

1. Run tests first; record the baseline.
2. One change at a time.
3. Re-run the full suite after each change — only merge when the pass rate does not drop.
4. Append new reports under `tests/results/`; never overwrite.

---

## 7. Validation commands

```bash
# Validate every SKILL
python scripts/lint_skill.py

# Validate a single SKILL
python scripts/lint_skill.py packs/aec-generation/aec-building

# Check naming
python scripts/check_naming.py
```

CI runs these two scripts automatically on every PR.
