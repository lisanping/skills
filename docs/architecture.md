# Repository architecture

## Overall design

```text
+--------------------------------------------------+
|  Agent (Claude Code / Copilot / Cursor / ...)    |
+----------------------+---------------------------+
                       | 1. read AGENTS.md (top-level routing)
                       v
+--------------------------------------------------+
|  packs/<pack-name>/AGENTS.md  (pack-internal)    |
+----------------------+---------------------------+
                       | 2. read the matching SKILL.md
                       v
+--------------------------------------------------+
|  packs/<pack>/.claude/skills/<skill>/SKILL.md    |
|   |-- frontmatter (name + description)           |
|   |-- workflow                                   |
|   |-- references/   <- loaded on demand          |
|   +-- scripts/      <- invoked explicitly        |
+--------------------------------------------------+
```

## Three-layer routing

1. **Top-level [AGENTS.md](../AGENTS.md)** — pick a pack by *task domain*.
2. **Pack-internal AGENTS.md / CLAUDE.md** — pick a SKILL by *task type*.
3. **SKILL.md** — self-contained workflow.

> Routing files only **point**; they never duplicate the details that live inside a SKILL.

## Isolation boundaries

| Boundary                      | How it is enforced                                                              |
| ----------------------------- | ------------------------------------------------------------------------------- |
| Python deps between packs     | Each pack ships its own `environment.yml`; Conda envs are **not shared**.       |
| Data exchange between packs   | Pass via files on disk (IFC / JSON / docx); never assume in-memory sharing.     |
| Code references between packs | Cross-pack `import` is forbidden. To share logic, extract a third pack.         |
| Repo root vs packs            | The repo root contains **no** executable Python. All code belongs to some pack. |

## SKILL loading mechanism

- **Layout convention.** `.claude/skills/` inside each pack is the standard convention used by Claude Code / Anthropic Skills. Other agents (Copilot, etc.) reach the same files through the repository's `AGENTS.md`.
- **Trigger.** Agents decide whether to activate a SKILL purely from the `description` field in the SKILL.md frontmatter — hence `description` must contain explicit **USE WHEN / DO NOT USE** clauses.
- **Lazy loading.** `references/` and `scripts/` are *not* loaded when the SKILL activates. The agent fetches them only after seeing a relative link inside `SKILL.md` — the key mechanism for context compression.

## Tests and baselines

See [evaluation.md](evaluation.md). The essentials:

- Code-oriented SKILLs → `pytest`
- Document-oriented SKILLs → manual prompt-evals defined in `tests/*.evals.json`
- Versioned baselines: `tests/BASELINE-vX.Y.md` + a matching git tag

## Naming consistency

Every identifier exposed to agents (pack name, SKILL name, directory name, frontmatter `name`) must be kebab-case. Enforced in CI by [scripts/check_naming.py](../scripts/check_naming.py).
