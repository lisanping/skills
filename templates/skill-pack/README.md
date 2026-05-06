# <pack-name>

> 一句话描述这个 pack 的领域定位（建议 30 字内）。

## 包含的 SKILL

| SKILL       | 用途 | 触发场景 |
| ----------- | ---- | -------- |
| `<skill-1>` | TODO | TODO     |

## 环境搭建

```bash
conda env create -f environment.yml
conda activate <pack-name>
# 如果含 Python 包：
pip install -e ".[dev]"
```

## SKILL 路由

详见 [AGENTS.md](AGENTS.md)（或 [CLAUDE.md](CLAUDE.md)）。

## 测试

```bash
pytest tests/ -v
```

## 目录结构

```text
<pack-name>/
├── README.md
├── AGENTS.md                       # 给 agent 的内部路由
├── environment.yml                 # Conda 环境（name 必须与 pack 同名）
├── pyproject.toml                  # 可选
├── .claude/skills/
│   └── <skill-name>/
│       ├── SKILL.md
│       ├── references/
│       └── scripts/
├── src/                            # 可选：pack 内 Python 源码
├── tests/                          # 可选：单元测试 / prompt-eval
├── examples/                       # 可选
└── output/                         # git-ignored
```
