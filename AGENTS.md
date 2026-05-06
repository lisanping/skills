# AGENTS.md

> 顶层 agent 路由文件。AI agent（Claude Code / GitHub Copilot / Cursor 等）应在执行任何任务前先读本文件，定位到正确的 *skill pack*，再读该 pack 内部的 `AGENTS.md` 或 `CLAUDE.md` 做二级路由。

---

## 仓库定位

**多领域 SKILL 分享仓库**。仓库本身不含可执行代码——所有领域知识与脚本都封装在 [packs/](packs/) 子目录下的独立 pack 中。

---

## 路由表（一级）

按**任务领域**选择 pack。读完对应 pack 的 `README.md` + `AGENTS.md` 之后，再按其内部路由进入具体 SKILL。

| 任务领域                                                  | 进入 pack                                      | 内部路由文件                     |
| --------------------------------------------------------- | ---------------------------------------------- | -------------------------------- |
| 建筑 BREP 建模 / IFC / DWG / 合规审查 / 规格书 / 项目文档 | [packs/aec-generation/](packs/aec-generation/) | `packs/aec-generation/CLAUDE.md` |

> 如果任务不属于以上任何领域，**不要猜**——告诉用户当前仓库尚未覆盖该领域，并建议参考 [CONTRIBUTING.md](CONTRIBUTING.md) 新建 pack。

---

## 跨 pack 任务

当任务跨越多个领域（例如"读 IFC → 生成合规审查报告 → 写成 docx"），按以下顺序处理：

1. **拆解**：把任务拆成单 pack 子任务。
2. **顺序执行**：每个子任务独立进入对应 pack，按其 `AGENTS.md` 路由。
3. **数据交换**：跨 pack 数据用文件（IFC / JSON / docx）落盘传递，不要假设内存共享。
4. **环境切换**：每个 pack 有独立 Conda 环境，切换 pack 时切换 `conda activate`。

---

## 新增 pack 时

新 pack 必须：

1. 放在 `packs/<pack-name>/` 下，`<pack-name>` 用 kebab-case。
2. 包含 `README.md` + `AGENTS.md`（或 `CLAUDE.md`）+ `environment.yml`。
3. SKILL 集合放在 `packs/<pack-name>/.claude/skills/<skill-name>/SKILL.md`。
4. 在本文件**路由表（一级）**中追加一行。
5. 通过 [scripts/lint_skill.py](scripts/lint_skill.py) 与 [scripts/check_naming.py](scripts/check_naming.py) 的 CI 检查。

详见 [CONTRIBUTING.md](CONTRIBUTING.md) 与 [SKILL-SPEC.md](SKILL-SPEC.md)。

---

## 给 agent 的硬性约束

- **永远先读 SKILL.md**，再调用其 `scripts/`；不要凭记忆生成命令。
- **不要跨 pack 修改文件**，除非任务明确要求。
- **不要在仓库根新增可执行代码**——所有代码归属某个 pack。
- **命名一律 kebab-case**：`my-skill` ✓，`my_skill` ✗，`my.skill` ✗，`MySkill` ✗。
