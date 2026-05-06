---
name: aec-building
description: 'AEC building modeling skill — parametric architectural geometry for Agent harness. USE when the task involves creating building geometry (floors, columns, walls, curtain walls, stairs), running code compliance checks (GB 50016, JGJ/T 67), exporting to STEP/IFC/GLB, or orchestrating multi-step building design workflows via MCP tools. Supports modern office, traditional heritage, and custom-shape buildings. DO NOT USE for MEP/structural calculation/rendering/site design.'
argument-hint: 'Describe the building you want to generate (e.g. 3-story L-shaped office with atrium, octagonal pagoda, Chinese palace courtyard)'
---

# aec-building SKILL

## What this skill does

Generates parametric BREP building geometry through a 5-layer stack:

```
orchestrator (planner → executor → reporter)
    ↓ calls
mcp/server (19 粗粒度 MCP tools + JSON-RPC transport)
    ↓ calls
aec/ (Building + elements + grid + staircase)
    ↓ calls
core/ (shapes + booleans + references)
    ↓ exports via
export/ (STEP + IFC)
```

## Architecture invariants

1. **Reference-driven** — all geometry positioned via GridRef/LevelRef, never absolute coordinates
2. **Coarse-grained tools** — one MCP tool call = one complete operation (e.g. "place all columns")
3. **Compliance = deterministic code** — GB 50016 / JGJ/T 67 rules are pure functions, not LLM memory
4. **Failure = signal** — error messages always include actionable suggestions + fix_action
5. **Building.summary()** returns < 2KB for Agent context compression

## Key entry points

| Entry point | When to use |
|---|---|
| `GeometryKernelMCP` ([server.py](../../src/aec_building/mcp/server.py)) | MCP tool calls from Agent |
| `python -m aec_building.mcp.transport` | Start MCP JSON-RPC server on stdio |
| `run_l_office_plan()` ([executor.py](../../src/aec_building/orchestrator/executor.py)) | Execute full 14-step L-office plan |
| `Building.generate_brep()` ([building.py](../../src/aec_building/aec/building.py)) | Generate all CadQuery BREP solids |
| `Building.snapshot()` / `Building.restore()` | State management for multi-Agent |

## MCP tools (27)

### 通用工具
`solve_constraints` · `validate_constraints` · `create_project` · `create_floors` · `create_opening` · `modify_element` · `check_compliance` · `visual_check` · `export_model` · `generate_report` · `get_summary` · `take_snapshot` · `rollback` · `state_diff`

### 矩形柱网工具 (现代建筑)
`place_columns` · `place_beams` · `create_walls` · `create_curtain_wall` · `create_staircase` · `auto_place_doors`

### 自由几何工具 (传统/异形建筑)
`place_columns_at` · `place_beams_at` · `place_windows`

### 外观与渲染
`set_appearance` — 批量设置构件颜色/透明度/材质预设

### LOD 300 高精度工具
`place_round_columns_at` — 圆形截面柱 (木柱/装饰柱/罗马柱)
`create_curved_roof` — 曲面屋顶 (hip/gable/half_hip/conical/flat)
`create_railing` — 栏杆/勾栏 (立柱 + 扶手 + 底部横杆)

---

## Step 0: 建筑分类 (Building Classification)

**在开始任何设计前，先判断建筑类型，选择对应的工作流路径。**

| 特征 | 路径 A: 现代标准建筑 | 路径 B: 传统/异形建筑 |
|---|---|---|
| 平面形状 | L / rectangle / courtyard | polygon / circular / custom / 复杂组合 |
| 柱网 | 矩形正交柱网 | 环形 / 自由散布 / 多圈柱网 |
| 典型建筑 | 办公楼、商业、住宅 | 宫殿、塔楼、寺庙、亭阁、异形展馆 |
| 约束求解 | `solve_constraints` 自动求解 | `solve_constraints` (polygon/circular/custom) 或手动设计 |
| 柱子放置 | `place_columns` (轴网交点) | `place_columns_at` (自定义坐标) |
| 梁放置 | `place_beams` (轴网自动) | `place_beams_at` (自定义位置) |
| 楼梯 | `create_staircase` (必需) | 可选 (单层建筑可能不需要) |

**分类规则**:
- 用户描述中包含"办公"、"住宅"、"商业"、规则平面 → 路径 A
- 用户描述中包含"传统"、"宫殿"、"塔"、"庙"、"异形"、多边形、圆形 → 路径 B
- 不确定时 → 询问用户，或默认路径 A

---

## Workflow A: 现代标准建筑 (NL → BREP → Export)

适用于: L 形 / 矩形 / 院落式等正交平面建筑。

### Step A1: 约束提取 (Agent 侧推理)

从用户 NL 输入提取结构化参数：

| 参数 | 说明 | 示例 |
|---|---|---|
| `floors` | 层数 | 3 |
| `area_per_floor` | 每层面积 (m²) | 800 |
| `shape` | 平面形状 | L / rectangle |
| `max_span` | 最大柱距 (m) | 9 |
| `floor_height` | 层高 (mm) | 3900 |
| `core_position` | 核心筒位置 | north / south / center |
| `has_atrium` | 是否有中庭 | true / false |
| `cutout_corner` | L 形切除角 | NE / NW / SE / SW |
| `entrance_direction` | 主入口朝向 | south / north / east / west |

隐含约束由 Agent 补充推断：
- 建筑高度 = floors × floor_height
- 建筑类别（< 24m 为多层）
- 防火分区（单层 < 2500m² 为单一分区）
- 疏散楼梯 ≥ 2 部（floors ≥ 2 时）

### Step A2: 几何求解

调用 `solve_constraints` 获得推荐几何参数：

```python
solve_constraints(
    floors=3,
    area_per_floor=800,
    shape="L",
    max_span=9.0,
    cutout_corner="NE",
    has_atrium=True,
    core_position="north",
    entrance_direction="south",
)
```

返回：
- `grid` — 轴网名称+位置（可直接传给 create_project）
- `levels` — 标高名称+高程
- `floor_boundary` — 楼板轮廓点（可直接传给 create_floors）
- `core_zone` / `atrium_zone` — 推荐轴网区间
- `column_skip_x` / `column_skip_y` — L 形切除区柱跳过轴线
- `entrance_wall` — 入口幕墙位置

### Step A3: create_project

将 `solve_constraints` 返回的 grid/levels 直接传入：

```python
create_project(
    name="...",
    x_grid_names=sol.grid.x_names,
    x_grid_positions=sol.grid.x_positions,
    y_grid_names=sol.grid.y_names,
    y_grid_positions=sol.grid.y_positions,
    level_names=sol.levels.names,
    level_elevations=sol.levels.elevations,
)
```

### Step A4: 主体结构

按顺序调用：
1. `create_floors` — L 形楼板（用 sol.floor_boundary）
2. `create_opening` — 中庭开洞（用 sol.atrium_zone 轴网参照，仅 F2+ 楼板）
3. `place_columns` — 批量放柱（sol.column_skip_x/skip_y 跳过切除区）
4. `place_beams` — 每层梁（逐层调用）

### Step A5: 围护结构

1. `create_walls` — 核心筒防火墙（用 sol.core_zone 轴网范围） + 外墙（一次批量）
2. `create_curtain_wall` — 主入口幕墙（用 sol.entrance_wall）

### Step A6: 竖向交通

```python
create_staircase(
    x_grid="A", y_grid="3",
    base_level="F1", top_level="F3",
    stair_type="u_turn"
)
```

**至少调用 2 次**确保 ≥ 2 部疏散楼梯。
如果失败 → 读 `error.suggestions` → 用 `modify_element` 扩大空间 → 重试。

### Step A7: 内装

`auto_place_doors` — 批量放门

### Step A8: 合规检查

```python
check_compliance(
    standards=["GB_50016_2014", "JGJ_T_67_2019"],
    scope=["fire_escape", "fire_compartment", "accessibility"],
    extra_info={"shape": "L"}
)
```

**关键**：检查返回的 violations，如果有 `fix_action` → 直接调用对应 tool → 重新 check。

### Step A9: 自我验证

`visual_check` — 截图审查几何正确性

### Step A10: 导出 + 报告

```python
export_model(output_path, formats=["step", "ifc", "summary"])
generate_report(compliance_result, exported_files, open_issues)
```

### Step A11: 约束验证 (可选)

在交付前用 `validate_constraints` 逐条对照原始约束：

```python
validate_constraints(
    floors=3, area_per_floor=800, shape="L",
    structure="steel_frame", max_span=9.0,
    has_atrium=True, core_position="north",
)
```

返回每条约束的 passed/failed/pending 状态。

---

## Workflow B: 传统/异形建筑 (NL → Custom Geometry → Export)

适用于: 传统宫殿、塔楼、寺庙、亭阁、异形展馆、圆形建筑等非正交平面建筑。

### Step B1: 约束提取 + 建筑风格分析

从用户 NL 输入提取结构化参数（与 A1 类似），并额外识别:

| 参数 | 说明 | 示例 |
|---|---|---|
| `shape` | 平面形状 | polygon / circular / custom |
| `polygon_sides` | 多边形边数 | 8 (八角形) |
| `building_style` | 风格标签 | "pagoda" / "palace" / "pavilion" |
| `center_x/y` | 建筑中心 (mm) | 如八角塔的中心点 |
| `custom_boundary` | 自定义边界点 | [(x1,y1), (x2,y2), ...] |

传统建筑隐含约束:
- 面阔×进深 → 开间数决定柱网
- 台基层数 (1~3 层须弥座)
- 屋顶类型 (庑殿/歇山/攒尖) → 决定屋檐出挑
- 柱网类型 (方形/环形/多圈)
- 木结构特有: 斗拱层、收分系数

### Step B2: 几何求解 (两种方式)

**方式 1: 使用 `solve_constraints`** — 适合能映射到标准形状的建筑

```python
solve_constraints(
    floors=5,
    area_per_floor=700,
    shape="polygon",         # 正多边形
    polygon_sides=8,         # 八角形
    center_x=16000, center_y=16000,
    max_span=6.0,
    floor_height=7000.0,
    building_style="pagoda",
)
```

返回 `column_positions` (环形柱位) 替代 `column_skip_x/y`。

**方式 2: Agent 手动设计** — 适合复杂组合建筑 (如宫殿群)

Agent 自行计算轴网、标高、柱位，直接跳到 Step B3。
参考 `examples/yingxian_pagoda.py` 和 `examples/imperial_palace.py` 的模式。

### Step B3: create_project

与路径 A 相同，但轴网仅作**外包矩形参考**，实际几何不受轴网约束:

```python
create_project(
    name="Octagonal_Pagoda",
    x_grid_names=["A", "B", "C", "D", "E"],
    x_grid_positions=[0, 8000, 16000, 24000, 32000],  # 外包矩形
    y_grid_names=["1", "2", "3", "4", "5"],
    y_grid_positions=[0, 8000, 16000, 24000, 32000],
    level_names=["Base", "F1", "F2", "Roof"],
    level_elevations=[0, 4000, 11000, 18000],
)
```

### Step B4: 台基/基座

传统建筑常有台基。用 `create_floors` + `create_walls` 组合:

```python
# 台基楼板
create_floors(boundary_points=台基轮廓, levels=["Base"], thickness=600.0)
# 台基围边墙
create_walls(walls=[...台基围墙...])
```

可叠加多层台基 (每层标高不同、面积递缩)。

### Step B5: 主体结构 (使用自由几何工具)

1. **楼板**: `create_floors` — 接受任意多边形 (已支持八角形、圆形等)
2. **柱子**: `place_columns_at` (方柱) 或 `place_round_columns_at` (圆柱) — 传入环形/自由柱位坐标

```python
# 方柱 (LOD 200)
place_columns_at(
    positions=sol.column_positions,
    base_level="F1", top_level="F2",
    section_width=500.0, section_depth=500.0,
    material="wood",
)

# 圆柱 (LOD 300) — 传统建筑首选
place_round_columns_at(
    positions=sol.column_positions,
    base_level="F1", top_level="F2",
    diameter=500.0,
    material="wood",
)
```

3. **梁**: `place_beams_at` — 传入环向梁、径向梁、斗拱短梁等

```python
place_beams_at(beams=[
    {"start": [x1, y1], "end": [x2, y2], "level": "F2",
     "width": 250, "height": 400, "material": "wood"},
    ...
])
```

### Step B6: 围护结构

`create_walls` — 任意起止点的墙体，适用于多边形外墙、火墙等。

### Step B7: 屋顶 / 屋檐

**LOD 300 (推荐)**: 使用 `create_curved_roof` 生成参数化曲面屋顶:

```python
# 庑殿顶 (四坡) — 适用于宫殿正殿
create_curved_roof(
    base_level="Roof",
    boundary_points=hall_boundary,
    ridge_height=3000.0,
    roof_type="hip",
    overhang=2500.0,         # 大出檐
    eave_rise=500.0,         # 翘角
)

# 攒尖顶 (锥形) — 适用于亭阁、塔
create_curved_roof(
    base_level="Roof",
    boundary_points=octagon_points(cx, cy, radius),
    ridge_height=5000.0,
    roof_type="conical",
    overhang=2000.0,
    eave_rise=300.0,
)

# 歇山顶 — 适用于配殿
create_curved_roof(
    base_level="Roof",
    boundary_points=hall_boundary,
    ridge_height=2500.0,
    roof_type="half_hip",
    overhang=2000.0,
)
```

**LOD 200 (兼容)**: 传统方式用**大出檐楼板**模拟:
- 屋檐: 比墙体外扩的薄楼板 (`create_floors` + 更大边界)
- 重檐: 两层不同大小的出檐楼板
- 屋脊: 窄长楼板置于最高标高

### Step B8: 装饰细节

- 斗拱层: `place_beams_at` 生成密排短梁阵列
- 窗户: `place_windows` 在外墙上放置
- 台阶/御道: `create_floors` 用阶梯状楼板模拟
- 华表/装饰柱: `place_round_columns_at` 放置圆形装饰柱 (LOD 300)
- **栏杆/勾栏** (LOD 300): `create_railing` 沿路径自动生成立柱 + 扶手

```python
# 台基围栏 — 沿八角形路径
create_railing(
    path_points=octagon_points(cx, cy, platform_radius),
    level="Base",
    height=1100.0,
    post_spacing=1200.0,
    material="marble",  # 石质栏杆用 wood/concrete
)

# 阳台栏杆 — 直线路径
create_railing(
    path_points=[[0, 0], [16000, 0]],
    level="F2",
    height=1100.0,
    material="steel",
)
```

### Step B9: 合规检查 + 导出

与路径 A 的 Step A8~A10 相同:

```python
check_compliance(standards=["GB_50016_2014"], scope=["fire_escape", "fire_compartment"])
visual_check()
export_model(output_path, formats=["step", "summary"])
```

**注意**: 传统建筑的合规检查通常会产生违规 (如缺少疏散楼梯)，这是预期的——传统建筑不需要满足现代规范。Agent 应在报告中说明原因。

---

## 几何辅助工具 (geometry utilities)

在 Step B 的手动设计场景中，可直接使用 `aec_building.utils.geometry`:

```python
from aec_building.utils.geometry import (
    regular_polygon_points,  # 正 n 边形顶点
    octagon_points,          # 八角形快捷方式
    ring_positions,          # 环形等分点 (柱位/灯位)
    polygon_area,            # Shoelace 面积计算
)
```

---

## 外观与渲染 (Appearance & Rendering)

### 外观系统

每个构件都有 `appearance` 属性 (可选)，不设置时使用基于材料/类型的默认色彩。

**默认色彩映射**:

| 材料/类型 | 颜色 | 效果 | 用途 |
|---|---|---|---|
| `steel` | 银灰 (192,192,200) | 金属 | 钢柱/钢梁 |
| `concrete` | 灰色 (180,180,175) | 哑光 | 混凝土构件 |
| `wood` | 木色 (180,140,100) | 缎面 | 木柱/木梁/门 |
| `exterior` | 米白 (235,225,210) | 哑光 | 外墙 |
| `glass` | 浅蓝 (180,220,240) | 玻璃/30%透 | 幕墙/窗户 |
| `red_wall` | 朱红 (180,50,45) | 哑光 | 传统红墙 |
| `marble` | 白玉 (240,235,225) | 高光 | 汉白玉台基 |
| `glazed_tile` | 琉璃黄 (200,170,40) | 高光 | 琉璃瓦屋顶 |
| `bronze` | 铜色 (140,120,80) | 金属 | 铜器/鼎 |

### 使用 `set_appearance` 工具

```python
# 方式 1: 使用预设
set_appearance(element_ids=wall_ids, preset="red_wall")

# 方式 2: 自定义 RGB
set_appearance(element_ids=col_ids, color_rgb=[160, 100, 60], opacity=1.0)

# 方式 3: 半透明 (玻璃)
set_appearance(element_ids=curtain_ids, preset="glass")
```

### 构件创建时直接指定外观

```python
from aec_building.aec.elements import Appearance, SurfaceFinish

Wall(start=..., end=..., base_level="F1", top_level="F2",
     wall_type=WallType.EXTERIOR,
     appearance=Appearance(color_rgb=(180, 50, 45), finish=SurfaceFinish.MATTE))
```

### 导出带色彩的模型

```python
export_model(output_path="output/my_building", formats=["glb", "obj", "ifc", "dxf", "summary"])
```

**支持的全部格式**:

| 格式 | formats 值 | 输出文件 | 依赖 | 色彩 | 用途 |
|---|---|---|---|---|---|
| **STEP** | `"step"` | `model.step` | CadQuery (conda) | 无 | CAD 内核精确几何 |
| **彩色 STEP** | `"colored_step"` | `model_colored.step` | OCP/XDE (pip) | **有 RGB** | FreeCAD/SolidWorks 显色 |
| **IFC4** | `"ifc"` | `model.ifc` | IfcOpenShell (conda) | 有 | BIM 行业标准 → Revit/ArchiCAD |
| **GLB** | `"glb"` | `model.glb` | trimesh (pip) | 有 | Web 3D / Three.js 渲染 |
| **OBJ** | `"obj"` | `model.obj` + `.mtl` | trimesh (pip) | 有 | Blender / 3ds Max / Maya |
| **STL** | `"stl"` | `model.stl` | trimesh (pip) | 无 | 3D 打印 / FEM 分析 |
| **DAE** | `"dae"` | `model.dae` | trimesh (pip) | 有 | SketchUp / 游戏引擎 |
| **DXF** | `"dxf"` | `model.dxf` | ezdxf (pip) | 无 | AutoCAD / 中望 CAD |
| **PNG 3D** | `"png_3d"` | `3d.png` | PyVista | — | 3D 等轴截图 |
| **PNG 平面** | `"png_plan"` | `plan.png` | matplotlib | — | 平面图 |
| **JSON** | `"summary"` | `summary.json` | 无 | — | 构件清单/参数 |

**Revit (.rvt) 导入路径**: `export_model(formats=["ifc"])` → Revit 中 `File > Open > IFC` 可得到可编辑模型

### 渲染流水线

```
Building (Appearance) → building_to_colored_glb() → model.glb
                                                        ↓
                        viewer_3d.py → Three.js PBR (阴影 + 色调映射 + 顶点色)
```

---

## Recovery Patterns (路径 A/B 通用)

### 楼梯空间不足
- **触发**: `create_staircase` → `STAIR_GEOMETRY_INVALID`
- **修复**: 读 `suggestions` → `modify_element` 扩大核心筒墙 → 重试 `create_staircase`
- **联动**: `modify_element` 修改墙端点时，相交墙自动延长（`cascaded_updates` 列表）

### 疏散楼梯数量不足
- **触发**: `check_compliance` → `§5.5.17` violation with `fix_action`
- **修复**: 读 `fix_action.tool` → 调用 `create_staircase` 在建筑另一端

### 防火间距不足
- **触发**: `check_compliance` → `§6.2.2` violation
- **修复**: `modify_element` 调整 L 形折角处窗位

### 参数化联动机制
`modify_element` 修改墙的 `start` 或 `end` 时，会自动查找端点相交的其他墙并同步更新。
返回的 `cascaded_updates` 列出所有被联动修改的墙及其新坐标。Agent 无需手动逐个修改相交墙。

---

## Tool Call Granularity Rules

### 批量操作（一次 tool call）
- `place_columns`: 全部柱子一次放完，用 skip_x/skip_y 排除 (路径 A)
- `place_columns_at`: 全部柱子坐标一次传入 (路径 B)
- `create_floors`: 多层楼板一次创建
- `auto_place_doors`: 全部门一次放完
- `place_beams`: 每层所有梁一次放完（逐层调用, 路径 A）
- `place_beams_at`: 一类梁一次传入 (路径 B, 如"所有环向梁"一批)
- `place_windows`: 同类窗户一次传入

### 逐个操作
- `create_staircase`: 每部楼梯单独调用（不同位置 + 独立验证）
- `create_curtain_wall`: 每个立面单独调用

### 绝不逐个
- 不要一根柱子一个 tool call
- 不要一面墙一个 tool call（除非类型不同需分批）

---

## Context Management

- 每次 tool call 后只记住：element_id（后续引用）、warnings（可能需处理）、error（需恢复）
- 调用 `get_summary` 获取 <2KB 状态快照
- 每 5-8 步调用一次 `visual_check`
- 用 `take_snapshot` 在关键节点保存状态，出错用 `rollback` 回退

---

## Adding new element types

1. Add dataclass to `aec/elements.py`
2. Add `*_to_brep()` factory in `aec/element_factory.py`
3. Add `Building.add_*()` method in `aec/building.py`
4. Add MCP tool in `mcp/server.py` + `mcp/transport.py` TOOL_DEFINITIONS + executor method map
5. Add tests

## Adding new compliance rules

1. Add check function in `compliance/rules/gb50016.py` or `jgj_t67.py`
2. Wire into `check_gb50016()` dispatcher with scope key
3. Every violation should include `fix_action` with tool + params when an automated fix is possible
4. Add test in `tests/test_compliance.py`

## Build & test

```bash
pip install -e ".[dev]"
pytest tests/ -v                    # all tests
pytest tests/ -k "not BREP"         # skip CadQuery-dependent tests
python examples/l_office_building.py           # 路径 A: 现代办公 MCP workflow
python examples/small_office_with_atrium.py    # 路径 A: full workflow with atrium
python examples/yingxian_pagoda.py             # 路径 B: 传统建筑 (八角木塔)
python examples/imperial_palace.py             # 路径 B: 传统建筑 (宫殿群)
```

## Reference documents

- [PRD & Architecture](docs/PRD_Architecture.md)
- [Agent Harness Case Study (20 tool calls)](docs/Agent_Harness_BREP_Generation_Case_Study.md)
