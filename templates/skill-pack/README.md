# <pack-name>

> One sentence describing the problem domain this pack covers (aim for under ~25 words).

## SKILLs in this pack

| SKILL       | Purpose | Trigger scenarios |
| ----------- | ------- | ----------------- |
| `<skill-1>` | TODO    | TODO              |

## Environment setup

```bash
conda env create -f environment.yml
conda activate <pack-name>
# If the pack ships a Python package:
pip install -e ".[dev]"
```

## SKILL routing

See [AGENTS.md](AGENTS.md) (or [CLAUDE.md](CLAUDE.md)).

## Tests

```bash
pytest tests/ -v
```

## Directory layout

```text
<pack-name>/
├── README.md
├── AGENTS.md                       # internal routing for agents
├── environment.yml                 # Conda env (name must match the pack)
├── pyproject.toml                  # optional
├── .claude/skills/
│   └── <skill-name>/
│       ├── SKILL.md
│       ├── references/
│       └── scripts/
├── src/                            # optional: pack-local Python source
├── tests/                          # optional: unit tests / prompt-eval
├── examples/                       # optional
└── output/                         # git-ignored
```
