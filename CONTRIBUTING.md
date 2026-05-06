# Contributing

Welcome to contribute a new *skill pack* or add a SKILL inside an existing pack. This document describes the standard workflow for both.

---

## Three contribution types

| Type                                             | Scope of change                            | Required reading                                        |
| ------------------------------------------------ | ------------------------------------------ | ------------------------------------------------------- |
| Add a **single SKILL** (inside an existing pack) | `packs/<pack>/.claude/skills/<new-skill>/` | [SKILL-SPEC.md](SKILL-SPEC.md)                          |
| Add an **entire pack** (new domain)              | All of `packs/<new-pack>/`                 | §2 of this file                                         |
| Fix / improve an existing SKILL                  | A single SKILL.md or reference             | [SKILL-SPEC.md](SKILL-SPEC.md) §"Modification workflow" |

---

## 1. Add a SKILL inside an existing pack

```bash
# 1. Copy the single-SKILL template
cp -r templates/skill packs/<pack-name>/.claude/skills/<new-skill-name>

# 2. Edit the SKILL.md frontmatter and body
#    - name: must equal the directory name
#    - description: must contain USE WHEN... / DO NOT USE...
#    - see SKILL-SPEC.md for details

# 3. Validate
python scripts/lint_skill.py packs/<pack-name>/.claude/skills/<new-skill-name>
python scripts/check_naming.py

# 4. Append a row to the routing table in the pack's README.md / AGENTS.md
```

---

## 2. Add a new pack

```bash
# 1. Copy the pack template
cp -r templates/skill-pack packs/<new-pack-name>

# 2. Edit the following files
#    - README.md       : domain purpose, SKILL list, install commands
#    - AGENTS.md       : internal agent routing
#    - environment.yml : set name to <new-pack-name>
#    - pyproject.toml  : optional, only if the pack ships a Python package

# 3. Create at least one SKILL (see §1)

# 4. Append a row to the routing table in the repo-root README.md / AGENTS.md

# 5. Validate
python scripts/lint_skill.py
python scripts/check_naming.py
```

### Required files for a pack

- [ ] `README.md` — the human-facing front page
- [ ] `AGENTS.md` or `CLAUDE.md` — internal routing for agents
- [ ] `environment.yml` — Conda environment definition; `name` must equal the pack name
- [ ] `.claude/skills/<skill>/SKILL.md` — at least one SKILL
- [ ] `.gitignore` — if the pack produces large outputs, ignore them locally

### Optional files

- `pyproject.toml` — if the pack contains Python source code
- `tests/` — unit tests or prompt-eval test suites
- `examples/` — example scripts
- `output/` (git-ignored) — model / document output

---

## Naming rules (enforced)

| Object          | Rule                                   | Example                                      |
| --------------- | -------------------------------------- | -------------------------------------------- |
| Pack directory  | kebab-case                             | `aec-generation` ✓ &nbsp; `aec.generation` ✗ |
| SKILL directory | kebab-case, equal to SKILL.md `name`   | `aec-building` ✓                             |
| Reference file  | kebab-case + `.md` / `.yaml` / `.json` | `code-versions.md` ✓                         |
| Python file     | snake_case + `.py`                     | `lint_skill.py` ✓                            |

Enforced in CI by [scripts/check_naming.py](scripts/check_naming.py).

---

## Required SKILL.md frontmatter fields

```yaml
---
name: my-skill                    # must equal the directory name
description: |                    # must contain USE WHEN... and DO NOT USE...
  USE WHEN the user wants to ...
  DO NOT USE for ...
argument-hint: 'one-line input hint'   # optional
---
```

Field semantics: see [SKILL-SPEC.md](SKILL-SPEC.md).

---

## Modification workflow (existing SKILL)

1. **Run tests before changing anything.** Execute `pytest` or the manual eval against the pack's current baseline; record the pass rate.
2. **One change at a time.** Touch only one of `SKILL.md` / `references/` / `scripts/` / `evals.json` per iteration.
3. **Re-run the full suite.** Pass rate must be ≥ the baseline before merging.
4. **If the pass rate drops**, decide whether the SKILL regressed or the test cases need updating.
5. **Append, don't overwrite.** Add a new report under `tests/results/`; never edit the old ones.
6. **Bump the baseline.** When the pass rate improves or the test set grows, update `tests/BASELINE-vX.Y.md` and tag the commit in git.

---

## Pull request checklist

- [ ] Naming follows kebab-case
- [ ] `python scripts/lint_skill.py` passes
- [ ] `python scripts/check_naming.py` passes
- [ ] Pass rate of affected SKILL tests ≥ the previous baseline
- [ ] Updated the relevant README.md / AGENTS.md routing table
- [ ] No large binary files committed (CAD / IFC / docx / etc. — add to `.gitignore`)
