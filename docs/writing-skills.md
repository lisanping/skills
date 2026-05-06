# Practical guide to writing a SKILL

> This file is the **how-to** companion to [SKILL-SPEC.md](../SKILL-SPEC.md). The spec says "what is required"; this file explains "why and how to do it well".

---

## 1. Getting started: copy a template

```bash
cp -r templates/skill packs/<pack>/.claude/skills/<new-skill>
```

Then do four things:

1. Set the SKILL.md frontmatter `name` (must equal the directory name).
2. Write the `description` (the single most important field — it controls when the agent triggers).
3. Write the workflow steps.
4. Remove the TODO placeholders left by the template.

---

## 2. How to write a good description

`description` is the **only** clue the agent uses for routing — it does not read your workflow to decide whether to activate.

### Formula

```
<verb phrase describing the capability>.
USE WHEN <user intent 1> / <user intent 2> / <user intent 3>.
DO NOT USE for <anti-trigger 1> / <anti-trigger 2>.
```

### Checklist

- [ ] First sentence **starts with a verb** stating the capability. Avoid "This is a skill that…".
- [ ] **USE WHEN** lists at least 2 concrete scenarios. Avoid "general purpose".
- [ ] **DO NOT USE** lists adjacent domains commonly confused with this one (prevents false triggers).
- [ ] Whole field stays under ~200 characters.
- [ ] Keywords match the wording the user is likely to use (e.g. if users say "fire safety", write "fire safety" — not "fire protection engineering").

---

## 3. When to split content into references/

Decide whether something belongs in `SKILL.md` or in `references/`:

| Situation                                                           | Where it goes                                                                             |
| ------------------------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| Needed on every invocation                                          | `SKILL.md`                                                                                |
| Needed only for a specific sub-task (e.g. one clause of a standard) | `references/<topic>.md`                                                                   |
| Long templates / tables / YAML configs                              | `references/`                                                                             |
| Volatile version numbers, regulatory clauses                        | `references/` (with a top-line note: "verify the currently effective version before use") |

### Thresholds

- Keep `SKILL.md` under ~200 lines.
- Keep a single reference under ~500 lines; split when it grows beyond that.

---

## 4. How to write scripts/

### Principles

- **CLI-parameterized.** Paths and parameters via `argparse` / `click`; nothing hardcoded.
- **Help-able.** `--help` always works and explains every parameter.
- **Idempotent.** Same input twice produces the same result.
- **No hidden side effects.** Read-only unless `--write` is passed.
- **Diagnosable failures.** Exceptions include actionable hints, e.g. `fix_action: ...`.

### Bad vs good

```python
# ❌ hardcoded path
def main():
    df = pd.read_csv("/Users/me/data.csv")
```

```python
# ✅ CLI
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    args = parser.parse_args()
    df = pd.read_csv(args.input)
```

---

## 5. Mis-trigger self-test

After writing a SKILL, construct 5–10 sample user prompts and verify routing:

| Prompt                                       | Expected                                         | Actual |
| -------------------------------------------- | ------------------------------------------------ | ------ |
| "Help me sketch an L-shaped office building" | aec-building triggers                            | ?      |
| "How do I write an RFI?"                     | aec-project-docs triggers; aec-building does not | ?      |
| "How do I use Photoshop?"                    | nothing triggers                                 | ?      |

If you see false triggers or missed triggers, tune the `USE WHEN` / `DO NOT USE` clauses in `description`.

---

## 6. Document-oriented vs code-oriented SKILLs

| Dimension        | Document-oriented (e.g. compliance review)                        | Code-oriented (e.g. BREP engine)                           |
| ---------------- | ----------------------------------------------------------------- | ---------------------------------------------------------- |
| Main asset       | Templates and checklists in `references/`                         | `scripts/` and `src/`                                      |
| Test method      | Prompt-eval (manual run + JSON binary judgement)                  | `pytest` unit tests                                        |
| Trigger keywords | User business language ("draft an RFI", "fire-safety self-check") | User technical language ("export IFC", "draw a staircase") |

---

## 7. Five-step check before you ship

```bash
# 1. Frontmatter validation
python scripts/lint_skill.py packs/<pack>/.claude/skills/<skill>

# 2. Naming validation
python scripts/check_naming.py

# 3. SKILL.md line count (aim for ≤ 200)
wc -l packs/<pack>/.claude/skills/<skill>/SKILL.md

# 4. Manual mis-trigger self-test

# 5. Register the SKILL in the pack's README.md / AGENTS.md routing table
```
