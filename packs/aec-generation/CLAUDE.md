# AEC BREP Generation Engine

Parametric building geometry generation engine. Creates architectural elements (floors, columns, walls, curtain walls, stairs), runs code compliance checks (GB 50016, JGJ/T 67), exports to STEP/IFC — all orchestrated through coarse-grained MCP tools and a 5-layer Python stack.

## Skill Routing

Before starting any task below, **read the corresponding SKILL.md** for full workflow, commands, and constraints.

| Task                                                        | Read first                                         |
| ----------------------------------------------------------- | -------------------------------------------------- |
| Parametric building modeling, geometry, MCP tools, STEP/IFC | `.claude/skills/aec-building/SKILL.md`             |
| 建筑设计合规审查清单（防火/无障碍/人防/绿建）               | `.claude/skills/aec-compliance-checklist/SKILL.md` |
| AEC 项目通信文档（RFI/变更单/联系单/会议纪要/日报周报）     | `.claude/skills/aec-project-docs/SKILL.md`         |

## Variables

| Variable      | Value            |
| ------------- | ---------------- |
| `SKILLS_ROOT` | `.claude/skills` |

All skill paths below are relative to `SKILLS_ROOT`. Individual skills
derive their own path variables from it (e.g. `BREP_SKILL`).

## Key Commands

```bash
pip install -e ".[dev]"              # install with dev deps
pytest tests/ -v                     # run all 131 tests
pytest tests/ -k "not BREP"          # skip CadQuery-dependent tests
python -m aec_building.mcp.transport     # start MCP server on stdio
python examples/l_office_building.py # full MCP workflow demo
```

## Coding Conventions

- Source code under `src/aec_building/`
- Examples under `examples/`
- Model outputs exported to `output/`
- All tests in `tests/`, named `test_*.py`
- CadQuery-dependent tests use `BREP` in name (skippable with `-k "not BREP"`)
