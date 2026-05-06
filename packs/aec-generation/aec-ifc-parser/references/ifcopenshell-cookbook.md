# IfcOpenShell 操作速查 (Cookbook)

> 何时读取:写脚本前需要回忆 IfcOpenShell 的常见 API 时。

## 1. 打开文件

```python
import ifcopenshell
f = ifcopenshell.open("model.ifc")
print(f.schema)          # IFC2X3 / IFC4 / IFC4X3
print(len(list(f)))      # 实体总数
```

支持 `.ifc` (STEP), `.ifczip`, `.ifcxml`。

## 2. 按类型查询实体

```python
walls = f.by_type("IfcWall")             # 含子类 (IfcWallStandardCase 等)
walls_only = f.by_type("IfcWall", include_subtypes=False)
wall = f.by_guid("3vB2YO$MX4xv5uCqZZG05$")
wall = f.by_id(123)                       # STEP ID
```

## 3. 属性集 (Pset) 与数量集 (Qto)

**便捷方式 (推荐)**:

```python
import ifcopenshell.util.element as util
psets = util.get_psets(wall)              # {pset_name: {prop: value}}
# {'Pset_WallCommon': {'FireRating': '2.0h', 'IsExternal': True, ...},
#  'Qto_WallBaseQuantities': {'Length': 5000.0, 'NetVolume': 1.5, ...}}
```

**底层方式** (理解关系链):

```python
for rel in wall.IsDefinedBy:
    if rel.is_a("IfcRelDefinesByProperties"):
        pset = rel.RelatingPropertyDefinition
        if pset.is_a("IfcPropertySet"):
            for prop in pset.HasProperties:
                if prop.is_a("IfcPropertySingleValue"):
                    print(prop.Name, "=", prop.NominalValue.wrappedValue)
```

## 4. 空间结构遍历

```python
project = f.by_type("IfcProject")[0]

# IfcRelAggregates: Project → Site → Building → Storey
for rel in project.IsDecomposedBy:
    for site in rel.RelatedObjects:
        print("Site:", site.Name)

# IfcRelContainedInSpatialStructure: Storey → Element
for storey in f.by_type("IfcBuildingStorey"):
    for rel in storey.ContainsElements:
        for elem in rel.RelatedElements:
            print(f"  [{storey.Name}] {elem.is_a()}: {elem.Name}")
```

工具函数:

```python
import ifcopenshell.util.element as util
storey = util.get_container(wall)         # 取所属楼层
psets_inherited = util.get_type(wall)     # 取构件类型 (IfcWallType)
```

## 5. 几何 (慢,按需启用)

```python
import ifcopenshell.geom as geom
settings = geom.settings()
settings.set(settings.USE_WORLD_COORDS, True)

shape = geom.create_shape(settings, wall)
verts = shape.geometry.verts             # [x1,y1,z1, x2,y2,z2, ...]
faces = shape.geometry.faces             # 三角面索引
```

批量遍历用 `geom.iterator`:

```python
it = geom.iterator(settings, f, multiprocessing.cpu_count())
if it.initialize():
    while True:
        shape = it.get()
        # 处理 shape
        if not it.next():
            break
```

## 6. 单位

```python
import ifcopenshell.util.unit as uutil
unit_scale = uutil.calculate_unit_scale(f)   # 长度单位到米的换算系数
# 例如模型用毫米则返回 0.001
```

## 7. 类型对象 (IfcWallType / IfcDoorType)

构件实例和类型对象通过 `IfcRelDefinesByType` 关联:

```python
type_obj = util.get_type(wall)            # 取对应的 IfcWallType
type_psets = util.get_psets(type_obj)     # 类型上的 Pset
```

实例的 Pset 优先于类型;类型 Pset 用于"同类型构件共有属性"。

## 8. 材料

```python
material = ifcopenshell.util.element.get_material(wall)
if material.is_a("IfcMaterialLayerSet"):
    for layer in material.MaterialLayers:
        print(layer.Material.Name, layer.LayerThickness)
```

## 9. Schema 检查

```python
import ifcopenshell.validate
errors = list(ifcopenshell.validate.validate(f, json=True))
for err in errors:
    print(err)
```

## 10. 常见坑

| 坑                                          | 解法                                                                              |
| ------------------------------------------- | --------------------------------------------------------------------------------- |
| 大模型 (>500MB) 内存爆                      | 用 `ifcopenshell.open(path, should_stream=True)` 流式读取                         |
| `Pset_*Common` 缺失                         | 用 `util.get_psets()` 时属性默认值是 `None`,显式判空                              |
| 同名 Pset 多次出现                          | 取最后一个,或合并                                                                 |
| 空间结构不完整 (Storey 直接挂在 Project 下) | 检查 `IfcRelAggregates` 链路                                                      |
| 子类被遗漏                                  | `by_type()` 默认含子类,关闭时显式传 `include_subtypes=False`                      |
| GlobalId 不是顺序 ID                        | `by_id()` 用 STEP ID,`by_guid()` 用 IfcGloballyUniqueId                           |
| 几何转换很慢                                | 启用 `USE_WORLD_COORDS=False` 时只取局部坐标系,跳过变换                           |
| Schema 兼容性                               | IFC2x3 → IFC4 部分实体改名 (`IfcDoorStyle` → `IfcDoorType` 等),按 schema 分支处理 |
