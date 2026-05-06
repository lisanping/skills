# 常用 Pset / Qto 速查

> 何时读取:需要查询特定 IFC 实体类型的属性集时。

## Common Property Sets (Pset_*Common)

构件通用属性。所有标准化项目应至少填写以下属性。

### IfcWall — `Pset_WallCommon`
| 属性                 | 类型                           | 说明                   |
| -------------------- | ------------------------------ | ---------------------- |
| Reference            | IfcIdentifier                  | 墙体类型编号           |
| Status               | IfcLabel                       | 新建 / 既有 / 拆除     |
| AcousticRating       | IfcLabel                       | 隔声等级 (例如 STC-50) |
| FireRating           | IfcLabel                       | 耐火极限 (例如 2.00h)  |
| Combustible          | IfcBoolean                     | 是否可燃               |
| SurfaceSpreadOfFlame | IfcLabel                       | 火焰传播等级           |
| ThermalTransmittance | IfcThermalTransmittanceMeasure | 传热系数 W/(m²·K)      |
| IsExternal           | IfcBoolean                     | 是否外墙               |
| LoadBearing          | IfcBoolean                     | 是否承重               |
| ExtendToStructure    | IfcBoolean                     | 是否延伸到结构层       |
| Compartmentation     | IfcBoolean                     | 是否防火分区分隔墙     |

### IfcDoor — `Pset_DoorCommon`
| 属性                 | 类型                           | 说明                  |
| -------------------- | ------------------------------ | --------------------- |
| Reference            | IfcIdentifier                  | 门类型编号            |
| FireRating           | IfcLabel                       | 耐火极限 (甲/乙/丙级) |
| AcousticRating       | IfcLabel                       |                       |
| SecurityRating       | IfcLabel                       |                       |
| IsExternal           | IfcBoolean                     | 是否外门              |
| Infiltration         | IfcVolumetricFlowRateMeasure   | 渗风量                |
| ThermalTransmittance | IfcThermalTransmittanceMeasure |                       |
| GlazingAreaFraction  | IfcPositiveRatioMeasure        | 玻璃面积比            |
| HandicapAccessible   | IfcBoolean                     | 无障碍                |
| FireExit             | IfcBoolean                     | 是否疏散门            |
| SelfClosing          | IfcBoolean                     | 是否自闭              |
| SmokeStop            | IfcBoolean                     | 是否防烟              |

### IfcWindow — `Pset_WindowCommon`
| 属性                 | 类型                           | 说明 |
| -------------------- | ------------------------------ | ---- |
| FireRating           | IfcLabel                       |      |
| AcousticRating       | IfcLabel                       |      |
| SecurityRating       | IfcLabel                       |      |
| IsExternal           | IfcBoolean                     |      |
| Infiltration         | IfcVolumetricFlowRateMeasure   |      |
| ThermalTransmittance | IfcThermalTransmittanceMeasure |      |
| GlazingAreaFraction  | IfcPositiveRatioMeasure        |      |
| SmokeStop            | IfcBoolean                     |      |
| FireExit             | IfcBoolean                     |      |
| HasSillExternal      | IfcBoolean                     |      |
| HasDrive             | IfcBoolean                     |      |

### IfcSlab — `Pset_SlabCommon`
FireRating, AcousticRating, ThermalTransmittance, LoadBearing, IsExternal, Combustible, SurfaceSpreadOfFlame, Compartmentation, PitchAngle

### IfcColumn — `Pset_ColumnCommon`
Reference, Status, Slope, FireRating, LoadBearing

### IfcBeam — `Pset_BeamCommon`
Reference, Status, Span, Slope, IsExternal, FireRating, LoadBearing

### IfcSpace — `Pset_SpaceCommon`
Reference, IsExternal, GrossPlannedArea, NetPlannedArea, PubliclyAccessible, HandicapAccessible, Category, CeilingCovering, FloorCovering, WallCovering

### IfcBuildingStorey — `Pset_BuildingStoreyCommon`
EntranceLevel, AboveGround, SprinklerProtection, GrossAreaPlanned, NetAreaPlanned

### IfcBuilding — `Pset_BuildingCommon`
BuildingID, IsPermanentID, OccupancyType, GrossPlannedArea, NetPlannedArea, NumberOfStoreys, YearOfConstruction, IsLandmarked

## Quantity Sets (Qto_*BaseQuantities)

数量集,用于工程量统计。值由 BIM 软件根据几何自动计算。

### IfcWall — `Qto_WallBaseQuantities`
Length, Width, Height, GrossFootprintArea, NetFootprintArea, GrossSideArea, NetSideArea, GrossVolume, NetVolume, GrossWeight, NetWeight

### IfcSlab — `Qto_SlabBaseQuantities`
Width, Perimeter, GrossArea, NetArea, GrossVolume, NetVolume, GrossWeight, NetWeight

### IfcColumn — `Qto_ColumnBaseQuantities`
Length, CrossSectionArea, OuterSurfaceArea, GrossSurfaceArea, NetSurfaceArea, GrossVolume, NetVolume, GrossWeight, NetWeight

### IfcBeam — `Qto_BeamBaseQuantities`
Length, CrossSectionArea, OuterSurfaceArea, GrossSurfaceArea, NetSurfaceArea, GrossVolume, NetVolume, GrossWeight, NetWeight

### IfcDoor — `Qto_DoorBaseQuantities`
Width, Height, Perimeter, Area

### IfcWindow — `Qto_WindowBaseQuantities`
Width, Height, Perimeter, Area

### IfcSpace — `Qto_SpaceBaseQuantities`
Height, FinishCeilingHeight, FinishFloorHeight, GrossPerimeter, NetPerimeter, GrossFloorArea, NetFloorArea, GrossWallArea, NetWallArea, GrossCeilingArea, NetCeilingArea, GrossVolume, NetVolume

## 取值代码示例

```python
import ifcopenshell.util.element as util
psets = util.get_psets(wall_entity)        # {pset_name: {prop: value}}
fire_rating = psets.get("Pset_WallCommon", {}).get("FireRating")
volume = psets.get("Qto_WallBaseQuantities", {}).get("NetVolume")
```

## 项目级 Pset

业主 / 设计单位常自定义 `Pset_<公司名>_*`,处理时:
1. 先取标准 Pset
2. 再取项目自定义 Pset (按 `references/qa-checklist.yaml` 配置)
3. 缺失时报警,但不视为致命错误
