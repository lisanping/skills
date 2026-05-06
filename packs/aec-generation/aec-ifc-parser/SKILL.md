---
name: aec-ifc-parser
description: "Use this skill whenever the user needs to read, query, validate, or summarize IFC (Industry Foundation Classes) files for AEC / BIM projects — including 构件提取 (entity extraction by type), 属性集查询 (Pset / Qto query), 空间结构遍历 (project → site → building → storey → space), 工程量统计 (quantity takeoff from IFC), 模型质量检查 (LOD / 命名规则 / 参数完整性 / IFC schema validation), and 跨模型对比 (model diff). Trigger on phrases like '解析这个 IFC 文件', '从 IFC 里提取所有墙的属性', '统计 IFC 模型的构件数量', 'list all spaces in this IFC', 'check IFC LOD compliance', 'extract Pset_WallCommon from this model'. Also trigger when user uploads .ifc / .ifczip files. Built on top of IfcOpenShell. Do NOT use this skill for DWG / DXF parsing (use aec-dwg-dxf), for generating new IFC geometry (use aec-building's IFC export), or for IFC file editing / authoring (read-only focus)."
---

# AEC IFC 文件解析

## 目的

IFC (ISO 16739) 是 AEC / BIM 行业的开放交换格式。痛点:

1. **Schema 复杂** —— IFC4 / IFC2x3 几百个实体类型,人工查询易遗漏
2. **属性集 (Pset)** 散落在 `IsDefinedBy` 关系链上,需多步遍历才能取到
3. **空间结构** (Project → Site → Building → Storey → Space) 用 `IfcRelAggregates` / `IfcRelContainedInSpatialStructure` 关联,遍历模式固定
4. **工程量 (Qto)** 与几何分别存储,需要分别取
5. **模型质量** (LOD、命名、参数完整性) 各家约定不一,缺少标准检查脚本

本 SKILL 沉淀**怎么用对 IfcOpenShell**的工程经验,把上述高频查询固化为可复用脚本。

## 技术栈

- **核心库**:[`ifcopenshell`](https://docs.ifcopenshell.org/) ≥ 0.8
- **几何处理**(可选):`ifcopenshell.geom` + OpenCascade
- **Schema 支持**:IFC2x3, IFC4, IFC4x3
- **只读为主**:不做 IFC 编辑 / 编写 (避免破坏模型完整性)

## 工作流

### 第 1 步:确认输入

| 输入 | 处理 |
|------|------|
| `.ifc` (STEP 物理文件) | 直接 `ifcopenshell.open()` |
| `.ifczip` | 解压后处理,或直接 `open()` (新版支持) |
| `.ifcxml` | `open()` 自动识别 |
| 多文件(联合模型) | 逐个加载,或合并后再查 |

加载即输出基础概要:Schema 版本、实体总数、空间结构层级、主要构件类型分布。

### 第 2 步:识别任务类型

| 任务 | 脚本 | 说明 |
|------|------|------|
| 模型概要 | `scripts/summarize.py` | 实体计数、Schema 版本、空间结构、坐标范围 |
| 按类型提取构件 | `scripts/extract_by_type.py` | `IfcWall`, `IfcDoor`, `IfcColumn` 等 |
| 属性集查询 | `scripts/query_pset.py` | 取构件的 `Pset_*` / `Qto_*` |
| 空间结构遍历 | `scripts/spatial_tree.py` | 输出 Project/Site/Building/Storey/Space 树形 |
| 工程量统计 | `scripts/quantity_takeoff.py` | 按类型 / 楼层聚合面积、体积、长度 |
| 模型质量检查 | `scripts/qa_check.py` | LOD、命名、必填属性、孤立构件 |
| 模型对比 | `scripts/model_diff.py` | 两个 IFC 的实体级 diff |

### 第 3 步:输出

- **报告**:Markdown / JSON,默认写到 `output/ifc/<job_id>/`
- **大模型** (>500MB) :增量输出,避免内存爆掉
- **几何相关查询** 默认关闭 (慢且重),用户明确要求几何统计时才启用 `ifcopenshell.geom`

### 第 4 步:跨 SKILL 联动

- `aec-building` 导出的 `.ifc` → 可直接走"模型概要 / 质量检查"
- 提取的 `Pset_WallCommon.FireRating` / `IsExternal` → 可作为 `aec-compliance-checklist` 防火检查的输入
- 工程量统计结果 → 可对接未来的"BoQ 整理 SKILL"

## 关键脚本骨架

### `scripts/summarize.py`

```python
"""IFC 文件概要:Schema、构件计数、空间结构层级、坐标范围。"""
import ifcopenshell
from collections import Counter
import json
import sys


def summarize(path: str) -> dict:
    f = ifcopenshell.open(path)
    by_type = Counter(e.is_a() for e in f)

    project = f.by_type("IfcProject")
    sites = f.by_type("IfcSite")
    buildings = f.by_type("IfcBuilding")
    storeys = f.by_type("IfcBuildingStorey")
    spaces = f.by_type("IfcSpace")

    return {
        "schema": f.schema,
        "total_entities": len(list(f)),
        "project": project[0].Name if project else None,
        "site_count": len(sites),
        "building_count": len(buildings),
        "storey_count": len(storeys),
        "space_count": len(spaces),
        "top_entity_types": by_type.most_common(20),
    }


if __name__ == "__main__":
    print(json.dumps(summarize(sys.argv[1]), ensure_ascii=False, indent=2))
```

### `scripts/query_pset.py` (核心)

```python
"""提取构件的属性集 (Pset) 和数量集 (Qto)。

IFC 属性通过 IfcRelDefinesByProperties 关系链访问。
IfcOpenShell 提供了便捷封装 ifcopenshell.util.element.get_psets()。
"""
import ifcopenshell
import ifcopenshell.util.element as util
import json
import sys


def query(path: str, ifc_type: str, pset_name: str | None = None):
    f = ifcopenshell.open(path)
    results = []
    for ent in f.by_type(ifc_type):
        psets = util.get_psets(ent)            # {pset_name: {prop: value}}
        if pset_name:
            psets = {k: v for k, v in psets.items() if k == pset_name}
        results.append({
            "id": ent.GlobalId,
            "name": ent.Name,
            "type": ent.is_a(),
            "psets": psets,
        })
    return results


if __name__ == "__main__":
    path, ifc_type = sys.argv[1], sys.argv[2]
    pset = sys.argv[3] if len(sys.argv) > 3 else None
    print(json.dumps(query(path, ifc_type, pset), ensure_ascii=False, indent=2))
```

### `scripts/spatial_tree.py`

```python
"""输出 IFC 的空间结构树 (Project → Site → Building → Storey → Space → Element)。"""
import ifcopenshell


def walk(node, depth=0):
    print("  " * depth + f"{node.is_a()}: {node.Name or '(unnamed)'} [{node.GlobalId}]")
    for rel in getattr(node, "IsDecomposedBy", []) or []:
        for child in rel.RelatedObjects:
            walk(child, depth + 1)
    for rel in getattr(node, "ContainsElements", []) or []:
        for child in rel.RelatedElements:
            walk(child, depth + 1)


if __name__ == "__main__":
    import sys
    f = ifcopenshell.open(sys.argv[1])
    for project in f.by_type("IfcProject"):
        walk(project)
```

### `scripts/qa_check.py` 检查项 (示例)

参考 `references/qa-checklist.yaml`:
- ✅ 所有 `IfcWall` 必填 `Pset_WallCommon.FireRating`
- ✅ 所有 `IfcDoor` 必填 `Pset_DoorCommon.FireRating` 与 `IsExternal`
- ✅ 所有 `IfcSpace` 必填 `Pset_SpaceCommon.GrossPlannedArea`
- ✅ 命名规则:`<类型代号>-<楼层>-<流水号>`
- ✅ 无孤立构件 (未关联到 `IfcBuildingStorey`)
- ✅ Schema 版本应为 IFC4 或 IFC4x3 (项目级配置可放宽)

## 常见 Pset 速查 (摘录)

| Pset | 适用类型 | 关键属性 |
|------|---------|---------|
| `Pset_WallCommon` | IfcWall | FireRating, IsExternal, LoadBearing, ThermalTransmittance |
| `Pset_DoorCommon` | IfcDoor | FireRating, AcousticRating, IsExternal, SecurityRating |
| `Pset_WindowCommon` | IfcWindow | FireRating, ThermalTransmittance, IsExternal, GlazingAreaFraction |
| `Pset_SlabCommon` | IfcSlab | FireRating, LoadBearing, IsExternal, ThermalTransmittance |
| `Pset_ColumnCommon` | IfcColumn | LoadBearing, FireRating |
| `Pset_SpaceCommon` | IfcSpace | IsExternal, PubliclyAccessible, HandicapAccessible |
| `Qto_WallBaseQuantities` | IfcWall | Length, Width, Height, GrossSideArea, NetVolume |
| `Qto_SpaceBaseQuantities` | IfcSpace | Height, GrossFloorArea, NetFloorArea, GrossVolume |

完整清单见 `references/common-psets.md`。

## 边界

- ❌ 不做 IFC 编辑 / 写入 (read-only)
- ❌ 不做 IFC 渲染 / 三维可视化 (使用 IfcConvert + viewer)
- ❌ 不做 BIM 协同冲突检查 (clash detection 属于另一 SKILL)
- ❌ 不做 IFC 转其他格式 (STEP / glTF / OBJ)
- ✅ 只做 **结构化读取 + 查询 + 校验**

## 依赖检查

```bash
python -c "import ifcopenshell; print(ifcopenshell.version)"   # 需要 ≥ 0.8
```

如未安装:
```bash
pip install ifcopenshell
# 或 conda install -c ifcopenshell -c conda-forge ifcopenshell
```

## 参考文件

- `references/common-psets.md` —— 常用 Pset / Qto 完整清单
- `references/qa-checklist.yaml` —— 模型质量检查规则 (可项目级覆写)
- `references/ifcopenshell-cookbook.md` —— IfcOpenShell 常见操作速查

## 免责声明

本 SKILL 输出为**自动化读取与校验结果**。模型最终交付的合规性 (LOD 是否达标、是否满足业主 BIM 实施手册要求) 需由 BIM 经理 / 业主代表复核。
