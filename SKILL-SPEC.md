# SKILL 写作规范

本文件定义本仓库**所有** SKILL 必须遵守的格式与质量规范。CI 通过 [scripts/lint_skill.py](scripts/lint_skill.py) 强制执行其中可机器校验的部分。

> 本规范参考 Anthropic Agent Skills 约定，并在其基础上加入仓库自有约束。

---

## 1. 文件位置

```text
packs/<pack-name>/.claude/skills/<skill-name>/
├── SKILL.md            # 必需
├── references/         # 可选——长篇知识，按需加载
│   └── *.md / *.yaml / *.json
└── scripts/            # 可选——可执行脚本，由 SKILL.md 显式调用
    └── *.py
```

- `<skill-name>` 必须 kebab-case，且**等于** `SKILL.md` frontmatter 的 `name`。
- `references/` 与 `scripts/` 都是可选的；很多文档类 SKILL 只有 `references/`。

> **兼容布局**：已有 pack 也允许把 SKILL 直接放在 pack 根目录（`packs/<pack>/<skill>/SKILL.md`）。新 pack **推荐** `.claude/skills/` 布局以便与 Claude Code 默认约定对齐；校验脚本对两者都接受。

---

## 2. SKILL.md 结构

### 2.1 YAML frontmatter（必需）

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

| 字段            | 必填 | 规则                                                                |
| --------------- | ---- | ------------------------------------------------------------------- |
| `name`          | ✅    | `^[a-z0-9-]+$`，且等于目录名                                        |
| `description`   | ✅    | 必须包含 **USE WHEN** 与 **DO NOT USE**；建议 2–5 句，不超过 200 字 |
| `argument-hint` | 推荐 | 一行说明用户该提供什么；用单引号包裹                                |
| `version`       | 可选 | semver，例如 `1.0.0`                                                |

> ❗ `description` 是 agent 路由的**唯一依据**——写得越具体，被错误触发的概率越低。
>
> 当前 lint 把 `USE WHEN` / `DO NOT USE` 缺失记为 **warning**（兼容旧 SKILL）；用 `python scripts/lint_skill.py --strict` 升级为 error。仓库稳定后 CI 会切到 `--strict`。

### 2.2 正文结构（推荐）

```markdown
# <skill-name> SKILL

## What this skill does
一段说明此 SKILL 的输入、输出与边界。

## When to use / When NOT to use
重申 frontmatter 的触发条件，可补例子。

## Workflow
分步骤说明 agent 应如何执行：
1. 先读 references/<file>.md
2. 调用 scripts/<script>.py
3. 验证产物并报告

## Key entry points
| Entry | When to use |
| ----- | ----------- |

## Constraints
不可违反的硬性约束（如"必须输出 UTF-8"、"必须保留原文件"）。

## References
- references/<file>.md —— 何时按需读取
```

---

## 3. references/ 写作原则

- **按需加载**：把不一定每次都用的长篇资料放进 `references/`，由 `SKILL.md` 用相对链接 `[xxx](references/xxx.md)` 引用，agent 读到链接才取。
- **单文件聚焦一个主题**：避免一个 reference 同时讲规范 + 模板 + 示例。
- **长文档拆分阈值**：超过约 500 行就考虑拆。
- **引用规范要写清版本**：例如 `GB 50016—2014（2018 年版）`；并在 reference 顶部声明"使用前核查现行有效版本"。

---

## 4. scripts/ 写作原则

- **可独立运行**：`python scripts/foo.py --help` 必须给出有效用法。
- **CLI 参数化**：路径、参数走命令行，不硬编码。
- **失败可诊断**：异常消息含可操作建议（"check_action: 改为 ..."）。
- **零隐藏副作用**：除非用户传入 `--write`，否则不修改输入文件。
- **禁止网络访问**，除非 SKILL 明确说明并征得用户同意。

---

## 5. 描述模板（粘贴即用）

```yaml
description: |
  <One sentence what this skill does>.
  USE WHEN the user wants to <action 1> / <action 2> / <action 3>.
  DO NOT USE for <out-of-scope 1> / <out-of-scope 2>.
```

**好例子**（来自 [aec-building](packs/aec-generation/.claude/skills/aec-building/SKILL.md)）：

> AEC building modeling skill — parametric architectural geometry for Agent harness.
> USE when the task involves creating building geometry (floors, columns, walls, curtain walls, stairs), running code compliance checks (GB 50016, JGJ/T 67), exporting to STEP/IFC/GLB, or orchestrating multi-step building design workflows via MCP tools.
> DO NOT USE for MEP/structural calculation/rendering/site design.

**坏例子**：

> "A skill for buildings."  ← 过于笼统，agent 无法判定何时触发。

---

## 6. 修改流程（重述）

详见 [CONTRIBUTING.md](CONTRIBUTING.md) "修改流程"。要点：

1. 改前先跑测试，记下基线
2. 一次只改一处
3. 改后整轮重跑，通过率不降才合入
4. `tests/results/` 追加新报告，不覆盖

---

## 7. 校验命令

```bash
# 校验所有 SKILL
python scripts/lint_skill.py

# 校验单个 SKILL
python scripts/lint_skill.py packs/aec-generation/.claude/skills/aec-building

# 检查命名
python scripts/check_naming.py
```

CI 会在每个 PR 自动跑这两个脚本。
