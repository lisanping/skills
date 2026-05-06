# AGENTS.md (pack-level)

> Second-level routing for tasks scoped to **aec-generation**. Read this file before opening any `SKILL.md` inside the pack.

## Pack purpose

AEC（建筑 / 工程 / 施工）领域的全栈 SKILL 集合 —— 覆盖**参数化 BREP 建模 → CAD/BIM 文件解析 → 设计合规审查 → 项目文档撰写**的端到端工作流。

| SKILL                          | 用途                                             | 触发关键词                                                                                                    |
| ------------------------------ | ------------------------------------------------ | ------------------------------------------------------------------------------------------------------------- |
| **`aec-building`**             | 参数化 BREP 建筑几何生成（楼板/柱/墙/楼梯/幕墙） | "生成 L 形办公楼"、"画一座八角塔"、"导出 STEP/IFC"、需要 BREP 几何或 MCP 工作流                               |
| **`aec-compliance-checklist`** | 建筑设计合规审查清单                             | 防火（GB 50016）/ 无障碍（GB 50763）/ 人防（GB 50038）/ 绿建（GB/T 50378）—— "合规审查 / 规范审查 / 设计审查" |
| **`aec-dwg-dxf`**              | DWG / DXF CAD 文件读写与批处理（基于 ezdxf）     | 图层规范检查、图签信息提取、图纸目录生成、批量重命名、块属性查询                                              |
| **`aec-ifc-parser`**           | IFC / BIM 文件只读解析（基于 IfcOpenShell）      | 构件提取、Pset / Qto 查询、空间结构遍历、模型质量检查、跨模型对比                                             |
| **`aec-project-docs`**         | AEC 项目通信文档                                 | RFI、设计变更单、工程联系单、设计 / 工地例会纪要、施工日报 / 周报 / 监理日志                                  |
| **`aec-spec-writer`**          | 施工说明书 / 技术规格书                          | 建筑 / 结构施工图设计说明、装修做法说明、CSI MasterFormat 三段式技术规格书                                    |

## SKILL routing

按"任务出现的关键证据"二选一进入对应 SKILL，不要平行加载多个 SKILL.md。

| 任务类型                                                          | Read first                                                             |
| ----------------------------------------------------------------- | ---------------------------------------------------------------------- |
| 生成 / 修改 / 校验**建筑几何**（BREP / STEP / IFC）               | [aec-building/SKILL.md](aec-building/SKILL.md)                         |
| 生成 / 套用 / 评审**设计合规清单**（防火 / 无障碍 / 人防 / 绿建） | [aec-compliance-checklist/SKILL.md](aec-compliance-checklist/SKILL.md) |
| 处理 / 批改 / 提取 **DWG / DXF 文件**                             | [aec-dwg-dxf/SKILL.md](aec-dwg-dxf/SKILL.md)                           |
| 解析 / 查询 / 校验 **IFC 文件**（只读）                           | [aec-ifc-parser/SKILL.md](aec-ifc-parser/SKILL.md)                     |
| 撰写 / 评审**项目通信文档**（RFI / 变更 / 联系单 / 纪要 / 日报）  | [aec-project-docs/SKILL.md](aec-project-docs/SKILL.md)                 |
| 撰写 / 评审**技术规格书 / 设计说明 / 做法表**                     | [aec-spec-writer/SKILL.md](aec-spec-writer/SKILL.md)                   |

### 易混淆任务的边界

- **"出一份合规清单"** → `aec-compliance-checklist`；**"写一份设计说明"** → `aec-spec-writer`
- **DWG / DXF** → `aec-dwg-dxf`；**IFC** → `aec-ifc-parser`；**新建 IFC 几何** → `aec-building`（其 export 子模块）
- **施工日报 / 会议纪要** → `aec-project-docs`；**装修做法表** → `aec-spec-writer`
- **设计是否合规**（条款核对）→ `aec-compliance-checklist`；**几何层强约束**（疏散距离、构件耐火极限的几何参数）→ `aec-building` 内置的 `compliance/` 模块

## Variables

| Variable           | Resolved path (relative to pack root) | Notes                                                   |
| ------------------ | ------------------------------------- | ------------------------------------------------------- |
| `SKILLS_ROOT`      | `.`                                   | 本 pack 采用平铺布局，每个 SKILL 直接位于 pack 根下     |
| `BREP_SKILL`       | `aec-building`                        | 同时也是 `src/aec_building/` Python 包对应的 SKILL      |
| `COMPLIANCE_SKILL` | `aec-compliance-checklist`            | 纯文档 + references，不依赖 Python 包                   |
| `DWG_SKILL`        | `aec-dwg-dxf`                         | 依赖 `ezdxf`；附带 `scripts/sample.dxf` 测试样本        |
| `IFC_SKILL`        | `aec-ifc-parser`                      | 依赖 `ifcopenshell`；附带 `scripts/sample.ifc` 测试样本 |
| `DOCS_SKILL`       | `aec-project-docs`                    | 纯文档 + references                                     |
| `SPEC_SKILL`       | `aec-spec-writer`                     | 文档为主，可选 `openpyxl` 用于做法表 Excel 输出         |

> 当前各 SKILL.md 文件**没有引用** `$SKILLS_ROOT` 等变量（与 `pptx-generation` pack 不同）。上表用于跨 SKILL 协作时手工指代路径，不是 SKILL.md 中的实际占位符。

## Python 包：`aec_building`

只有 `aec-building` 这一个 SKILL 依赖 pack 内的 Python 包 [src/aec_building/](src/aec_building/)，其余 5 个 SKILL 都是**纯文档 + 独立 CLI 脚本**，不需要 import 任何 pack 内代码。

```text
src/aec_building/
├── core/         # OCCT 内核封装（primitives, booleans, shapes）
├── aec/          # 领域对象：Building / 楼板 / 柱 / 墙 / 楼梯
├── constraints/  # 参数约束的提取与求解
├── compliance/   # 几何层合规检查（GB 50016 / JGJ/T 67）
├── export/       # IFC / STEP / STL / GLB 导出
├── mcp/          # GeometryKernelMCP（19 个粗粒度 MCP 工具）+ JSON-RPC transport
├── orchestrator/ # planner → executor → reporter 多步建筑工作流
├── tools/
├── utils/
└── verify/       # 拓扑 / 可视化验证
```

完整工作流以 [aec-building/SKILL.md](aec-building/SKILL.md) 为准。

## Key commands

```bash
# 1. 激活环境
conda activate aec-generation

# 2. 安装 aec_building Python 包（仅 aec-building SKILL 需要）
pip install -e ".[dev]"

# 3. 启动 MCP 服务端（aec-building SKILL 默认入口）
python -m aec_building.mcp.transport

# 4. 用 spec-writer 的 Excel 输出（可选 extra）
pip install -e ".[dev,spec-writer]"

# --- 其余 5 个 SKILL 的 scripts 直接调用，无需安装 Python 包 ---

# DWG / DXF 工具
python aec-dwg-dxf/scripts/check_layers.py <file>.dxf
python aec-dwg-dxf/scripts/extract_titleblock.py <file>.dxf
python aec-dwg-dxf/scripts/generate_index.py <dir>/

# IFC 工具
python aec-ifc-parser/scripts/summarize.py <file>.ifc
python aec-ifc-parser/scripts/spatial_tree.py <file>.ifc
python aec-ifc-parser/scripts/quantity_takeoff.py <file>.ifc
python aec-ifc-parser/scripts/qa_check.py <file>.ifc
python aec-ifc-parser/scripts/model_diff.py <a>.ifc <b>.ifc
```

## Cross-skill data exchange

跨 SKILL 协作时一律通过**磁盘上的文件**交换数据（IFC / DXF / docx / JSON），不假设内存共享：

| 来源                                 | 产物                        | 下游消费者                                            |
| ------------------------------------ | --------------------------- | ----------------------------------------------------- |
| `aec-building` (`export/`)           | `*.ifc` / `*.step`          | `aec-ifc-parser`（解析）/ `aec-dwg-dxf`（DXF 后处理） |
| `aec-ifc-parser` (`summarize`)       | 模型摘要 JSON               | `aec-compliance-checklist`（条目化合规判断输入）      |
| `aec-dwg-dxf` (`extract_titleblock`) | 图签元数据 JSON             | `aec-project-docs`（自动填充 RFI / 联系单表头）       |
| `aec-compliance-checklist`           | 合规清单（Markdown / docx） | `aec-project-docs`（作为附件分发）                    |

## Conventions

- SKILL 平铺位于 `packs/aec-generation/<skill>/SKILL.md`（与 `pptx-generation` 一致；linter 接受平铺与 `.claude/skills/` 两种布局）
- `references/`：kebab-case `*.md` / `*.yaml` —— 按需加载，不在 SKILL.md 中复述
- `scripts/`：snake_case `*.py`，可作为独立 CLI 调用（`python scripts/<name>.py --help`）
- `src/aec_building/` 是**唯一**的 pack 内 Python 包；其余 SKILL 不要 import 它
- 模型输出（STEP / IFC / GLB / DXF）写入 `output/`，不入版本控制；分享样例走 Git LFS
- 规范引用必须显式标注版本（如 `GB 50016—2014 (2018 修订)`），并在 reference 顶部声明"使用前核查现行有效版本"

## Hard constraints

- **永远先读 SKILL.md**，再调用其 `scripts/`；不要凭记忆生成命令
- **不要跨 pack 修改文件**，除非任务明确要求
- 规范条款**不允许凭模型记忆补全编号**，未确认时主动询问用户使用的版本
- IFC 解析为**只读**：模型编辑 / 写出新 IFC 应交给 `aec-building` 的 export 模块完成

---

## 已知文档漂移（待清理，不影响 routing）

- pack 根 [README.md](README.md) 仍引用 `tests/`、`tests/BASELINE-v1.0.md`、`tests/results/`、`examples/l_office_building.py`，但当前磁盘上**没有这些目录 / 文件**。修改任何 SKILL 之前，需要按 [docs/evaluation.md](../../docs/evaluation.md) 重建测试集与基线。
