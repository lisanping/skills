"""STEP 文件导出."""

from __future__ import annotations

import math
from pathlib import Path


def export_to_step(cq_shape: object, filepath: str | Path) -> Path:
    """将 CadQuery 对象导出为 STEP 文件.

    Args:
        cq_shape: CadQuery Workplane 对象。
        filepath: 输出路径。

    Returns:
        写入的文件路径。
    """
    import cadquery as cq

    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)
    cq.exporters.export(cq_shape, str(filepath), cq.exporters.ExportTypes.STEP)
    return filepath


def export_to_stl(cq_shape: object, filepath: str | Path, tolerance: float = 0.1) -> Path:
    """将 CadQuery 对象导出为 STL 文件.

    Args:
        cq_shape: CadQuery Workplane 对象。
        filepath: 输出路径。
        tolerance: 三角化精度 (mm)。

    Returns:
        写入的文件路径。
    """
    import cadquery as cq

    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)
    cq.exporters.export(cq_shape, str(filepath), cq.exporters.ExportTypes.STL, tolerance=tolerance)
    return filepath


def export_colored_step(building: object, filepath: str | Path) -> Path:
    """导出带逐构件颜色的 STEP 文件 (AP214 + styled_item).

    使用 OCP (OpenCascade Python) 的 XDE 文档模型，绕过 CadQuery 的颜色限制。
    每个构件根据 resolved_appearance() 的 RGB 颜色着色。

    在 FreeCAD / SolidWorks / CATIA 中打开可看到正确颜色。

    Args:
        building: Building 对象。
        filepath: 输出路径。

    Returns:
        写入的文件路径。
    """
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.gp import gp_Pnt, gp_Vec, gp_Trsf, gp_Dir, gp_Ax2
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform, BRepBuilderAPI_MakeWire, BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakeEdge
    from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
    from OCP.TopoDS import TopoDS_Shape
    from OCP.XCAFDoc import XCAFDoc_ColorSurf, XCAFDoc_DocumentTool
    from OCP.STEPCAFControl import STEPCAFControl_Writer
    from OCP.TDocStd import TDocStd_Document
    from OCP.TCollection import TCollection_ExtendedString
    from OCP.Quantity import Quantity_Color, Quantity_TOC_RGB

    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    doc = TDocStd_Document(TCollection_ExtendedString("XDE"))
    shape_tool = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    color_tool = XCAFDoc_DocumentTool.ColorTool_s(doc.Main())

    grid = building.grid

    def _make_prism(pts, z_base, height):
        """从平面多边形+拉伸高度创建 TopoDS_Shape."""
        if len(pts) < 3 or height < 1:
            return None
        try:
            wire_builder = BRepBuilderAPI_MakeWire()
            n = len(pts)
            for i in range(n):
                p1 = gp_Pnt(float(pts[i][0]), float(pts[i][1]), float(z_base))
                p2 = gp_Pnt(float(pts[(i + 1) % n][0]), float(pts[(i + 1) % n][1]), float(z_base))
                edge = BRepBuilderAPI_MakeEdge(p1, p2).Edge()
                wire_builder.Add(edge)
            wire = wire_builder.Wire()
            face = BRepBuilderAPI_MakeFace(wire).Face()
            prism = BRepPrimAPI_MakePrism(face, gp_Vec(0, 0, float(height))).Shape()
            return prism
        except Exception:
            return None

    def _wall_pts(start, end, thickness):
        """从墙中心线算出四角点."""
        sx, sy = float(start[0]), float(start[1])
        ex, ey = float(end[0]), float(end[1])
        dx, dy = ex - sx, ey - sy
        length = math.sqrt(dx * dx + dy * dy)
        if length < 1:
            return None
        nx = -dy / length * thickness / 2
        ny = dx / length * thickness / 2
        return [
            (sx + nx, sy + ny), (ex + nx, ey + ny),
            (ex - nx, ey - ny), (sx - nx, sy - ny),
        ]

    def _add_shape(shape, color_rgb):
        """添加形状到 XDE 文档并设置颜色."""
        if shape is None:
            return
        label = shape_tool.AddShape(shape)
        r, g, b = color_rgb
        occ_color = Quantity_Color(r / 255.0, g / 255.0, b / 255.0, Quantity_TOC_RGB)
        color_tool.SetColor(label, occ_color, XCAFDoc_ColorSurf)

    from aec_building.aec.elements import Door, Window

    # ── 楼板 ──
    for be in building.slabs:
        slab = be.element
        elev = grid.level_elevation(slab.level)
        app = slab.resolved_appearance()
        shape = _make_prism(slab.boundary_points, elev, slab.thickness)
        _add_shape(shape, app.color_rgb)

    # ── 柱子 ──
    for be in building.columns:
        col = be.element
        base_z = grid.level_elevation(col.base_level)
        top_z = grid.level_elevation(col.top_level)
        hw, hd = col.section_width / 2, col.section_depth / 2
        pts = [
            (col.x - hw, col.y - hd), (col.x + hw, col.y - hd),
            (col.x + hw, col.y + hd), (col.x - hw, col.y + hd),
        ]
        app = col.resolved_appearance()
        shape = _make_prism(pts, base_z, top_z - base_z)
        _add_shape(shape, app.color_rgb)

    # ── 墙体 ──
    for be in building.walls:
        wall = be.element
        base_z = grid.level_elevation(wall.base_level)
        top_z = grid.level_elevation(wall.top_level)
        pts = _wall_pts(wall.start, wall.end, wall.thickness)
        if pts:
            app = wall.resolved_appearance()
            shape = _make_prism(pts, base_z, top_z - base_z)
            _add_shape(shape, app.color_rgb)

    # ── 梁 ──
    for be in building.beams:
        beam = be.element
        sx, sy = beam.start
        ex, ey = beam.end
        dx, dy = float(ex - sx), float(ey - sy)
        length = math.sqrt(dx * dx + dy * dy)
        if length < 1:
            continue
        elev = grid.level_elevation(beam.level) - beam.height
        pts = _wall_pts(beam.start, beam.end, beam.width)
        if pts:
            app = beam.resolved_appearance()
            shape = _make_prism(pts, elev, beam.height)
            _add_shape(shape, app.color_rgb)

    # ── 幕墙 ──
    for be in building.curtain_walls:
        cw = be.element
        base_z = grid.level_elevation(cw.base_level)
        top_z = grid.level_elevation(cw.top_level)
        pts = _wall_pts(cw.start, cw.end, cw.glass_thickness)
        if pts:
            app = cw.resolved_appearance()
            shape = _make_prism(pts, base_z, top_z - base_z)
            _add_shape(shape, app.color_rgb)

    # ── 门 ──
    for be in building.get_elements_by_type(Door):
        door = be.element
        try:
            host = building.get_element(door.host_wall_id)
        except KeyError:
            continue
        wall = host.element
        base_z = grid.level_elevation(wall.base_level)
        sx, sy = float(wall.start[0]), float(wall.start[1])
        ex, ey = float(wall.end[0]), float(wall.end[1])
        dx, dy = ex - sx, ey - sy
        wlen = math.sqrt(dx * dx + dy * dy)
        if wlen < 1:
            continue
        cx = sx + dx * door.position
        cy = sy + dy * door.position
        ux, uy = dx / wlen, dy / wlen
        hw = door.width / 2
        ds = (cx - ux * hw, cy - uy * hw)
        de = (cx + ux * hw, cy + uy * hw)
        pts = _wall_pts(ds, de, 60.0)
        if pts:
            app = door.resolved_appearance()
            shape = _make_prism(pts, base_z, door.height)
            _add_shape(shape, app.color_rgb)

    # ── 窗 ──
    for be in building.get_elements_by_type(Window):
        win = be.element
        try:
            host = building.get_element(win.host_wall_id)
        except KeyError:
            continue
        wall = host.element
        base_z = grid.level_elevation(wall.base_level) + win.sill_height
        sx, sy = float(wall.start[0]), float(wall.start[1])
        ex, ey = float(wall.end[0]), float(wall.end[1])
        dx, dy = ex - sx, ey - sy
        wlen = math.sqrt(dx * dx + dy * dy)
        if wlen < 1:
            continue
        cx = sx + dx * win.position
        cy = sy + dy * win.position
        ux, uy = dx / wlen, dy / wlen
        hw = win.width / 2
        ws = (cx - ux * hw, cy - uy * hw)
        we = (cx + ux * hw, cy + uy * hw)
        pts = _wall_pts(ws, we, 30.0)
        if pts:
            app = win.resolved_appearance()
            shape = _make_prism(pts, base_z, win.height)
            _add_shape(shape, app.color_rgb)

    # 写入
    writer = STEPCAFControl_Writer()
    writer.Transfer(doc)
    writer.Write(str(filepath))
    return filepath
