# 仓库架构

## 总体设计

```text
┌──────────────────────────────────────────────────┐
│  Agent (Claude Code / Copilot / Cursor / ...)    │
└─────────────────────┬────────────────────────────┘
                      │ 1. 读 AGENTS.md（顶层路由）
                      ▼
┌──────────────────────────────────────────────────┐
│  packs/<pack-name>/AGENTS.md  （pack 内路由）    │
└─────────────────────┬────────────────────────────┘
                      │ 2. 读对应 SKILL.md
                      ▼
┌──────────────────────────────────────────────────┐
│  packs/<pack>/.claude/skills/<skill>/SKILL.md    │
│   ├── frontmatter (name + description)           │
│   ├── workflow                                    │
│   ├── references/   ← 按需加载                   │
│   └── scripts/      ← 显式调用                   │
└──────────────────────────────────────────────────┘
```

## 三层路由

1. **顶层 [AGENTS.md](../AGENTS.md)** —— 按"任务领域"选 pack
2. **Pack 内 AGENTS.md / CLAUDE.md** —— 按"任务类型"选 SKILL
3. **SKILL.md** —— 自含完整工作流

> 路由文件自身只做"指路"，不重复 SKILL 内的细节。

## 隔离边界

| 边界                  | 实现方式                                            |
| --------------------- | --------------------------------------------------- |
| Pack 之间 Python 依赖 | 各自 `environment.yml`，**不共享** Conda 环境       |
| Pack 之间数据交换     | 用文件落盘（IFC / JSON / docx），不假设内存共享     |
| Pack 之间代码引用     | 禁止跨 pack `import`；如需共享逻辑，抽出第三个 pack |
| 仓库根 vs pack        | 根目录**不含**可执行 Python；所有代码归属某个 pack  |

## SKILL 加载机制

- **加载方式**：每个 pack 内 `.claude/skills/` 目录是 Claude Code / Anthropic Skills 的标准约定；其他 agent（Copilot 等）可通过本仓库 `AGENTS.md` 路由到同一文件。
- **触发**：agent 仅根据 `SKILL.md` frontmatter 的 `description` 字段决定是否激活某个 SKILL，因此 `description` 必须包含 **USE WHEN / DO NOT USE** 子句。
- **按需加载**：`references/` 与 `scripts/` 不在 SKILL 激活时立刻加载，agent 看到 `SKILL.md` 内的相对链接才取——这是上下文压缩的关键机制。

## 测试与基线

详见 [evaluation.md](evaluation.md)。要点：

- 代码类 SKILL → `pytest`
- 文档类 SKILL → `tests/*.evals.json` 人工 prompt-eval
- 基线版本化：`tests/BASELINE-vX.Y.md` + git tag

## 命名一致性

所有面向 agent 暴露的标识符（pack 名、SKILL 名、目录名、frontmatter `name`）必须 kebab-case。CI 通过 [scripts/check_naming.py](../scripts/check_naming.py) 强制。
