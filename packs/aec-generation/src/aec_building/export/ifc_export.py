"""IFC4 文件导出.

将 Building 数据模型导出为 IFC4 格式，包含材质和颜色信息。
需要 IfcOpenShell 库（conda install -c ifcopenshell ifcopenshell）。
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aec_building.aec.building import Building


def _assign_material_and_color(
    ifc, ifc_entity, material_name: str,
    color_rgb: tuple[int, int, int] | None = None,
):
    """为 IFC 实体分配材质和表面颜色."""
    import ifcopenshell.api

    mat = ifcopenshell.api.run("material.add_material", ifc, name=material_name)
    ifcopenshell.api.run("material.assign_material", ifc, products=[ifc_entity], material=mat)

    if color_rgb:
        try:
            style = ifcopenshell.api.run("style.add_style", ifc, name=f"Style_{material_name}")
            ifcopenshell.api.run(
                "style.add_surface_style", ifc,
                style=style,
                ifc_class="IfcSurfaceStyleShading",
                attributes={
                    "SurfaceColour": {
                        "Name": material_name,
                        "Red": color_rgb[0] / 255.0,
                        "Green": color_rgb[1] / 255.0,
                        "Blue": color_rgb[2] / 255.0,
                    }
                },
            )
        except Exception:
            pass  # style API may not be available in all ifcopenshell versions


def export_to_ifc(building: Building, filepath: str | Path) -> str:
    """将 Building 导出为 IFC4 文件.

    Args:
        building: 建筑数据模型。
        filepath: 输出路径。

    Returns:
        写入的文件路径。
    """
    import ifcopenshell
    import ifcopenshell.api

    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    ifc = ifcopenshell.api.run("project.create_file", version="IFC4")

    # 项目
    project = ifcopenshell.api.run("root.create_entity", ifc, ifc_class="IfcProject", name=building.name)
    ifcopenshell.api.run("unit.assign_unit", ifc, length={"is_metric": True, "raw": "MILLIMETERS"})

    # 场地 → 建筑 → 楼层
    site = ifcopenshell.api.run("root.create_entity", ifc, ifc_class="IfcSite", name="Site")
    ifcopenshell.api.run("aggregate.assign_object", ifc, products=[site], relating_object=project)

    ifc_building = ifcopenshell.api.run("root.create_entity", ifc, ifc_class="IfcBuilding", name=building.name)
    ifcopenshell.api.run("aggregate.assign_object", ifc, products=[ifc_building], relating_object=site)

    # 为每个标高创建楼层
    storey_map = {}
    for level_name, elevation in building.grid.levels.items():
        storey = ifcopenshell.api.run(
            "root.create_entity", ifc,
            ifc_class="IfcBuildingStorey",
            name=level_name,
        )
        storey.Elevation = elevation
        ifcopenshell.api.run("aggregate.assign_object", ifc, products=[storey], relating_object=ifc_building)
        storey_map[level_name] = storey

    # 楼板
    for be in building.slabs:
        slab = be.element
        storey = storey_map.get(slab.level)
        if storey:
            ifc_slab = ifcopenshell.api.run(
                "root.create_entity", ifc,
                ifc_class="IfcSlab",
                name=be.id,
            )
            ifcopenshell.api.run(
                "spatial.assign_container", ifc,
                products=[ifc_slab], relating_structure=storey,
            )
            app = slab.resolved_appearance()
            _assign_material_and_color(ifc, ifc_slab, "Concrete_Slab", app.color_rgb)

    # 柱子
    from aec_building.aec.elements import Column
    for be in building.columns:
        col = be.element
        storey = storey_map.get(col.base_level)
        if storey:
            ifc_col = ifcopenshell.api.run(
                "root.create_entity", ifc,
                ifc_class="IfcColumn",
                name=be.id,
            )
            ifcopenshell.api.run(
                "spatial.assign_container", ifc,
                products=[ifc_col], relating_structure=storey,
            )
            app = col.resolved_appearance()
            _assign_material_and_color(ifc, ifc_col, col.material.value.title(), app.color_rgb)

    # 墙体
    from aec_building.aec.elements import Wall
    for be in building.walls:
        wall = be.element
        storey = storey_map.get(wall.base_level)
        if storey:
            ifc_wall = ifcopenshell.api.run(
                "root.create_entity", ifc,
                ifc_class="IfcWall",
                name=be.id,
            )
            ifcopenshell.api.run(
                "spatial.assign_container", ifc,
                products=[ifc_wall], relating_structure=storey,
            )
            app = wall.resolved_appearance()
            _assign_material_and_color(
                ifc, ifc_wall,
                f"{wall.wall_type.value.title()}_Wall",
                app.color_rgb,
            )

    ifc.write(str(filepath))
    return str(filepath)
