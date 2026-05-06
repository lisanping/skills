# AEC Generation Skills

基于 Agent Harness 架构的 AEC（建筑 / 工程 / 施工）SKILL 集合。当前包含三类领域 SKILL：

| SKILL                          | 用途                     | 触发场景                                                                                 |
| ------------------------------ | ------------------------ | ---------------------------------------------------------------------------------------- |
| **`aec-building`**             | 参数化建筑 BREP 几何生成 | 楼板 / 柱 / 墙 / 幕墙 / 楼梯建模、合规几何检查、STEP / IFC / GLB 导出、MCP 工作流        |
| **`aec-compliance-checklist`** | 建筑设计合规审查清单     | 防火（GB 50016）/ 无障碍（GB 50763）/ 人防（GB 50038）/ 绿建（GB/T 50378）自审与对照审查 |
| **`aec-project-docs`**         | AEC 项目通信文档         | RFI / 设计变更单 / 工程联系单 / 会议纪要 / 施工日报周报                                  |
| `docx`（基础设施）             | Word 文档生成            | 被 `aec-project-docs` 等委托使用，本身不直接面向用户                                     |

详细路由见 [CLAUDE.md](CLAUDE.md)。

---

## 项目结构

```text
aec-generation/
├── environment.yml                       # Conda 环境（name: aec-generation）
├── pyproject.toml                        # Python 项目配置
├── CLAUDE.md                             # SKILL 路由（顶层）
├── .claude/skills/
│   ├── aec-building/                     # BREP 几何 SKILL
│   ├── aec-compliance-checklist/         # 合规审查 SKILL（含 6 份 references）
│   ├── aec-project-docs/                 # 项目文档 SKILL（含 6 份 references）
│   └── docx/                             # Word 输出基础 SKILL
├── src/aec_building/                     # BREP 生成引擎源码
│   ├── core/                             # OCCT 内核封装
│   ├── aec/                              # 领域对象（墙 / 楼板 / 柱 / 楼梯）
│   ├── constraints/                      # 约束提取与求解
│   ├── compliance/                       # 几何层合规检查（GB 50016 / JGJ/T 67）
│   ├── export/                           # IFC / STEP / STL / GLB 导出
│   ├── mcp/                              # MCP 服务端
│   └── orchestrator/                     # 多步建筑工作流
├── tests/                                # 测试集 + 报告 + 基线
│   ├── BASELINE-v1.0.md                  # 当前测试基线清单
│   ├── test-design-rationale.md          # 测试集设计思路
│   ├── *.evals.json                      # 文档类 SKILL 评测集（3 份）
│   ├── results/                          # 各轮测试报告（6 份）
│   └── test_*.py                         # BREP 引擎 Python 单元测试
└── output/                               # 模型输出（STEP / DXF / viewer.html）
```

---

## `aec_building` Python 包

`src/aec_building/` 是 **`aec-building` SKILL 的运行时支撑包**。其余几个 SKILL（compliance-checklist / project-docs / spec-writer / dwg-dxf / ifc-parser）都是**纯文档 + 小脚本**，不依赖此包。

通过 `pip install -e ".[dev]"` 安装到 pack 的 conda 环境后即可 `import aec_building...`。

### 子模块一览

| 子包            | 角色                                                |
| --------------- | --------------------------------------------------- |
| `core/`         | OCCT 内核底层封装（primitives, booleans, shapes …） |
| `aec/`          | 领域对象：`Building` / 墙 / 楼板 / 柱 / 楼梯        |
| `constraints/`  | 参数约束的提取与求解                                |
| `compliance/`   | 几何层合规检查（GB 50016 / JGJ/T 67）               |
| `export/`       | IFC / STEP / STL / GLB 导出                         |
| `mcp/`          | `GeometryKernelMCP` —— 19 个粗粒度 MCP 工具         |
| `orchestrator/` | planner → executor → reporter 多步建筑工作流        |
| `utils/verify/` | 通用工具与拓扑/可视化验证                           |

### 两种使用方式

**1. 通过 MCP 服务端被 Agent 调用（推荐，也是 `aec-building` SKILL 的默认路径）**

```bash
python -m aec_building.mcp.transport     # 启动 JSON-RPC over stdio
```

Agent 端连上后调用粗粒度工具（`place_columns`、`add_curtain_wall` 等），由 [`GeometryKernelMCP`](src/aec_building/mcp/server.py) 路由到下层模块。完整工作流见 [aec-building/SKILL.md](aec-building/SKILL.md)。

**2. 作为普通 Python 包直接调用（脚本 / Notebook）**

```python
from aec_building.aec.building import Building
from aec_building.aec.grid import GridSystem
from aec_building.export.step_export import export_step

building = Building(grid=GridSystem.from_spans(x=[8, 8, 8], y=[6, 6]))
building.add_floor_slab(level="L1", thickness=0.15)
building.add_columns(grid_range="A1:C2", section=(0.6, 0.6))

solids = building.generate_brep()
export_step(solids, "output/demo.stp")
print(building.summary())              # < 2KB，便于 Agent 上下文压缩
```

### 关键入口

| 入口                                                               | 何时使用                            |
| ------------------------------------------------------------------ | ----------------------------------- |
| [`GeometryKernelMCP`](src/aec_building/mcp/server.py)              | 通过 MCP 协议被 Agent 调用          |
| `python -m aec_building.mcp.transport`                             | 在 stdio 上启动 MCP 服务端          |
| [`Building.generate_brep()`](src/aec_building/aec/building.py)     | 一次性生成所有 CadQuery BREP solids |
| [`run_l_office_plan()`](src/aec_building/orchestrator/executor.py) | 跑完整 14 步 L 形办公楼示范流程     |

> 上述代码示例只是最小骨架，端到端的工作流（含合规检查、IFC 导出、MCP 工具粒度等）请以 [aec-building/SKILL.md](aec-building/SKILL.md) 为准。

---

## 环境搭建

### 前置条件

- [Miniforge](https://github.com/conda-forge/miniforge) 或 Mambaforge（推荐，比 Anaconda 更轻量）
- Git + Git LFS（用于版本控制大型 CAD 文件）

### 快速开始

```bash
# 1. 创建 Conda 环境（环境名 aec-generation，定义见 environment.yml）
conda env create -f environment.yml

# 2. 激活环境
conda activate aec-generation

# 3. 安装项目（可编辑模式）
pip install -e ".[dev]"

# 4. 验证安装
python -c "from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox; print('OCCT OK')"
python -c "import cadquery as cq; print('CadQuery OK')"
python -c "import ifcopenshell; print('IfcOpenShell OK')"

# 5. 运行 BREP 引擎测试
pytest tests/ -v                     # 全部测试
pytest tests/ -k "not BREP"          # 跳过 CadQuery 依赖项

# 6. 启动 MCP 服务端
python -m aec_building.mcp.transport
```

上手代码示例见上文「[`aec_building` Python 包](#aec_building-python-%E5%8C%85)」一节。

---

## 测试与基线

文档类 SKILL（compliance-checklist / project-docs / cross-skill 协同）使用 **prompt-based eval 测试集**——以 JSON 描述用例 + expectations，由开发者按 SKILL 工作流真实演练后逐条二元判定。BREP 引擎仍用 pytest 单元测试。

### 当前基线

**aec-skills-baseline v1.0**（2026-04-29，git tag `aec-skills-baseline-v1.0`）

| 测试集                                                                                 | 用例   | expectations | 通过率   |
| -------------------------------------------------------------------------------------- | ------ | ------------ | -------- |
| [tests/aec-compliance-checklist.evals.json](tests/aec-compliance-checklist.evals.json) | 15     | 87           | 100%     |
| [tests/aec-project-docs.evals.json](tests/aec-project-docs.evals.json)                 | 12     | 76           | 100%     |
| [tests/cross-skill.evals.json](tests/cross-skill.evals.json)                           | 5      | 51           | 100%     |
| **合计**                                                                               | **32** | **214**      | **100%** |

详见：

- [tests/BASELINE-v1.0.md](tests/BASELINE-v1.0.md) — 基线清单与变更控制规则
- [tests/test-design-rationale.md](tests/test-design-rationale.md) — 测试集设计思路
- `tests/results/*.md` — 6 份测试运行报告

### 修改 SKILL 时的最小流程

1. 改前在当前基线下复跑对应测试集
2. 仅改一处（SKILL.md / references / evals 三选一）
3. 整轮重跑 → 100% 才合入
4. 通过率下降时，先评估是 SKILL 退化还是测试用例需更新
5. 任何变更在 `tests/results/` 下追加新报告（不覆盖原报告）

---

## BREP 技术栈

| 层次     | 技术                 | 用途                |
| -------- | -------------------- | ------------------- |
| 几何内核 | Open CASCADE (OCCT)  | BREP 拓扑与几何运算 |
| CAD 脚本 | CadQuery / build123d | 参数化建模 API      |
| BIM 数据 | IfcOpenShell         | IFC 读写与几何转换  |
| 2D 几何  | Shapely              | 平面布局运算        |
| 可视化   | PyVista / matplotlib | 3D / 2D 渲染与验证  |

---

## 文档资源

### BREP 理论

- [Open CASCADE 技术概览](https://dev.opencascade.org/doc/overview/html/)
- [OCCT API 参考](https://dev.opencascade.org/doc/refman/html/)
- Christoph Hoffmann, *Geometric and Solid Modeling*（Purdue 免费）

### BIM / IFC

- [IFC4 规范](https://standards.buildingsmart.org/IFC/RELEASE/IFC4/ADD2_TC1/HTML/)
- [IFC4x3 规范](https://ifc43-docs.standards.buildingsmart.org/)
- [IfcOpenShell 文档](https://ifcopenshell.org/docs)

### CadQuery / build123d

- [CadQuery 文档](https://cadquery.readthedocs.io)
- [build123d 文档](https://build123d.readthedocs.io)
- [pythonocc 示例](https://github.com/tpaviot/pythonocc-core/tree/master/examples)

### 文档类 SKILL 参考规范

- GB 50016《建筑设计防火规范》（含 2018 修订）+ GB 55037-2022《建筑防火通用规范》
- GB 50763《无障碍设计规范》+ 《无障碍环境建设条例》（2023 施行）
- GB 50038《人民防空地下室设计规范》
- GB/T 50378《绿色建筑评价标准》（2019 版）

> ⚠️ SKILL 中所有规范引用均要求"使用前核查现行有效版本"，详见 [.claude/skills/aec-compliance-checklist/references/code-versions.md](.claude/skills/aec-compliance-checklist/references/code-versions.md)。

---

## 开发指南

### 浏览 BREP 文件

| 格式         | 免费查看器                                            |
| ------------ | ----------------------------------------------------- |
| `.ifc`       | [BIM Vision](https://bimvision.eu/), Bonsai (Blender) |
| `.stp/.step` | FreeCAD, CAD Assistant (OCCT 官方)                    |
| `.stl/.obj`  | 3D Viewer (Windows 内置), MeshLab                     |
| 代码内 3D    | PyVista, jupyter-cadquery, cq-editor                  |

### 代码内快速预览 BREP

```python
import cadquery as cq

# 生成一个 L 形楼板
result = (
    cq.Workplane("XY")
    .rect(32, 20)
    .extrude(0.15)
    .cut(
        cq.Workplane("XY")
        .center(8, 3.5)
        .rect(16, 7)
        .extrude(0.15)
    )
)

# 导出为 STEP
cq.exporters.export(result, "l_floor.step")
```

用 cq-editor 打开脚本可实时预览；或在 Jupyter 中使用 `jupyter-cadquery` 交互查看。

---

## 编码约定

- BREP 引擎源代码在 `src/aec_building/`（详见上文「[`aec_building` Python 包](#aec_building-python-%E5%8C%85)」）
- 模型输出导出到 `output/`
- Python 单元测试在 `tests/`，命名 `test_*.py`；CadQuery 依赖项以 `BREP` 命名（可用 `-k "not BREP"` 跳过）
- 文档类 SKILL 测试在 `tests/*.evals.json`（手工跑），结果在 `tests/results/`
