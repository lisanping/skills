# Skills Monorepo

A cross-domain repository of **agent SKILL packs**. Each domain is an independent *skill pack* under [packs/](packs/), with its own Conda environment, SKILL collection, and test baseline.

> The repository itself is **not a Python package** and is not published to PyPI — it is purely a collection of documentation, SKILL files, and scaffolding.

---

## Skill packs

| Pack                                           | Domain                                                                                                                                                        | Status |
| ---------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------ |
| [packs/aec-generation/](packs/aec-generation/) | AEC (Architecture / Engineering / Construction) — BREP modeling, IFC/DWG parsing, code-compliance checklists, specifications, project communication documents | active |

To add a new pack, see [CONTRIBUTING.md](CONTRIBUTING.md).

---

## Quick navigation

| Goal                                             | Where to look                                                                       |
| ------------------------------------------------ | ----------------------------------------------------------------------------------- |
| Help an AI agent locate the right SKILL          | [AGENTS.md](AGENTS.md)                                                              |
| Author a new SKILL                               | [SKILL-SPEC.md](SKILL-SPEC.md) + [templates/skill/](templates/skill/)               |
| Create a new domain pack                         | [CONTRIBUTING.md](CONTRIBUTING.md) + [templates/skill-pack/](templates/skill-pack/) |
| Understand the overall architecture              | [docs/architecture.md](docs/architecture.md)                                        |
| Understand the evaluation / baseline methodology | [docs/evaluation.md](docs/evaluation.md)                                            |

---

## Repository layout

```text
skills/
├── README.md                       # this file
├── AGENTS.md                       # top-level agent routing
├── CONTRIBUTING.md                 # how to add a pack / SKILL
├── SKILL-SPEC.md                   # SKILL authoring spec (frontmatter, naming)
├── LICENSE                         # MIT
├── .editorconfig
├── .gitignore
│
├── packs/                          # all skill packs
│   └── <pack-name>/
│       ├── README.md
│       ├── AGENTS.md (or CLAUDE.md)
│       ├── environment.yml         # each pack owns its Conda env
│       ├── pyproject.toml          # optional: pack-local Python project
│       └── .claude/skills/
│           └── <skill-name>/
│               ├── SKILL.md
│               ├── references/
│               └── scripts/
│
├── templates/                      # copy to bootstrap a new pack/SKILL
│   ├── skill-pack/                 # minimal scaffold for a whole pack
│   └── skill/                      # single-SKILL.md template
│
├── docs/                           # framework-level long-form docs
│   ├── architecture.md             # multi-pack collaboration / SKILL loading
│   ├── writing-skills.md           # triggers, references split rules
│   └── evaluation.md               # prompt-eval and pytest dual track
│
├── scripts/                        # repo-level tooling
│   ├── lint_skill.py               # validate every SKILL.md frontmatter
│   └── check_naming.py             # enforce kebab-case for packs/SKILLs
│
└── .github/
    ├── workflows/                  # CI: lint + naming check
    ├── ISSUE_TEMPLATE/
    └── PULL_REQUEST_TEMPLATE.md
```

---

## Design conventions

1. **Monorepo.** All packs live in a single repository for easier cross-referencing and unified CI.
2. **One environment per pack.** Each pack ships its own `environment.yml` so heavy dependencies (e.g. OCCT in the AEC pack) never bleed into unrelated packs.
3. **SKILL load path.** Inside each pack, SKILLs are organized under `.claude/skills/<skill-name>/SKILL.md`, matching the Claude Code / Anthropic Skills convention. (Legacy packs may keep SKILLs at the pack root — the linter accepts both.)
4. **kebab-case naming.** Pack names, SKILL names, and folder names are lowercase + hyphens. No `.`, no underscores, no CamelCase.

---

## License

[MIT](LICENSE)
