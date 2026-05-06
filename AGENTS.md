# AGENTS.md

> Top-level agent routing file. AI agents (Claude Code / GitHub Copilot / Cursor / etc.) should read this file before doing anything else, locate the correct *skill pack*, then read that pack's internal `AGENTS.md` or `CLAUDE.md` for second-level routing.

---

## Repository purpose

**A multi-domain SKILL sharing repository.** The repo itself contains no executable code — all domain knowledge and scripts are encapsulated inside the individual packs under [packs/](packs/).

---

## Routing table (level 1)

Pick a pack by **task domain**. After reading the pack's `README.md` + `AGENTS.md`, follow its internal routing to a specific SKILL.

| Task domain                                                                                                                                       | Enter pack                                       | Internal routing file             |
| ------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------ | --------------------------------- |
| Building BREP modeling / IFC / DWG / compliance checklists / specifications / project documents                                                   | [packs/aec-generation/](packs/aec-generation/)   | `packs/aec-generation/AGENTS.md`  |
| PowerPoint generation: template profiling / brand-compliant decks / narrative composition / batch image generation / low-level `.pptx` operations | [packs/pptx-generation/](packs/pptx-generation/) | `packs/pptx-generation/AGENTS.md` |

> If the task does not fit any of the above, **do not guess**. Tell the user the repository does not yet cover that domain, and suggest creating a new pack via [CONTRIBUTING.md](CONTRIBUTING.md).

---

## Cross-pack tasks

When a task spans multiple domains (e.g. "read an IFC → generate a compliance report → emit it as a docx"), proceed as follows:

1. **Decompose.** Split the task into single-pack subtasks.
2. **Run sequentially.** Enter each pack independently and follow its `AGENTS.md`.
3. **Exchange data via files.** Pass IFC / JSON / docx through disk between packs; do not assume in-memory sharing.
4. **Switch environments.** Each pack has its own Conda env — `conda activate` the right one when switching.

---

## When adding a new pack

A new pack must:

1. Live under `packs/<pack-name>/` with `<pack-name>` in kebab-case.
2. Contain `README.md` + `AGENTS.md` (or `CLAUDE.md`) + `environment.yml`.
3. Place SKILLs under `packs/<pack-name>/.claude/skills/<skill-name>/SKILL.md`.
4. Append a row to the **routing table (level 1)** in this file.
5. Pass the CI checks from [scripts/lint_skill.py](scripts/lint_skill.py) and [scripts/check_naming.py](scripts/check_naming.py).

See [CONTRIBUTING.md](CONTRIBUTING.md) and [SKILL-SPEC.md](SKILL-SPEC.md) for details.

---

## Hard constraints for agents

- **Always read SKILL.md first** before invoking its `scripts/`. Never generate commands from memory.
- **Do not modify files across packs** unless the task explicitly requires it.
- **Do not add executable code at the repo root.** All code belongs to some pack.
- **Naming is always kebab-case**: `my-skill` ✓, `my_skill` ✗, `my.skill` ✗, `MySkill` ✗.
