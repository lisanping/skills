"""输出管理工具 — 文件夹创建、格式转换、带色彩 GLB 导出.

集中管理输出文件夹命名规则和格式转换逻辑。
支持带材质色彩的 GLB 导出 (用于 Three.js PBR 渲染)。
"""

from __future__ import annotations

import time
from pathlib import Path


def create_output_folder(project_name: str, base_dir: str = "output") -> Path:
    """创建带时间戳的独立输出文件夹.

    结构: output/{YYYYMMDD_HHMMSS}_{project_name}/
    内含: model.step, 3d.png, plan.png, summary.json

    Args:
        project_name: 项目名称。
        base_dir: 输出根目录。

    Returns:
        创建的文件夹路径。
    """
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in project_name)
    folder = Path(base_dir) / f"{timestamp}_{safe_name}"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def step_to_stl(step_path: str | Path, tolerance: float = 1.0) -> Path:
    """STEP → STL 转换.

    Args:
        step_path: STEP 文件路径。
        tolerance: 三角化精度 (mm)。

    Returns:
        STL 文件路径。
    """
    import cadquery as cq
    from cadquery import importers

    step_path = Path(step_path)
    stl_path = step_path.with_suffix(".stl")
    result = importers.importStep(str(step_path))
    cq.exporters.export(result, str(stl_path), "STL", tolerance=tolerance)
    return stl_path


def step_to_glb(step_path: str | Path, tolerance: float = 1.0) -> Path:
    """STEP → STL → GLB 转换（GLB 为浏览器原生 3D 格式）.

    转换结果会缓存：如果 GLB 比 STEP 新则直接返回。

    Args:
        step_path: STEP 文件路径。
        tolerance: 三角化精度 (mm)。

    Returns:
        GLB 文件路径。
    """
    step_path = Path(step_path)
    glb_path = step_path.with_suffix(".glb")

    if glb_path.exists() and glb_path.stat().st_mtime > step_path.stat().st_mtime:
        return glb_path

    stl_path = step_to_stl(step_path, tolerance=tolerance)

    import trimesh
    mesh = trimesh.load(str(stl_path))
    mesh.export(str(glb_path))
    return glb_path


def find_latest_step(base_dir: str = "output") -> Path | None:
    """找到 output/ 下最新的 model.step.

    优先查找 output/*/model.step，回退到 output/*.step。
    """
    import os
    output = Path(base_dir)
    candidates = sorted(
        output.glob("*/model.step"),
        key=lambda p: p.parent.name,
        reverse=True,
    )
    if candidates:
        return candidates[0]
    candidates = sorted(
        output.glob("*.step"),
        key=os.path.getmtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


def building_to_colored_glb(building: object, filepath: str | Path) -> Path:
    """将 Building 导出为带材质色彩的 GLB 文件.

    每个构件根据其 resolved_appearance() 着色，
    生成的 GLB 在 Three.js 中可直接渲染出真实外观。

    不依赖 CadQuery/STEP，直接从构件几何参数生成三角网格。

    Args:
        building: Building 对象。
        filepath: 输出 GLB 路径。

    Returns:
        写入的文件路径。
    """
    import numpy as np
    import trimesh

    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    meshes = []

    def _make_box_mesh(pts, z_base, height, color_rgb, opacity=1.0):
        """从平面多边形顶点拉伸为三角网格盒体."""
        from trimesh.creation import extrude_polygon
        from shapely.geometry import Polygon as ShapelyPolygon

        try:
            poly = ShapelyPolygon(pts)
            if not poly.is_valid:
                poly = poly.buffer(0)
            mesh = extrude_polygon(poly, height)
            mesh.apply_translation([0, 0, z_base])
            r, g, b = color_rgb or (200, 200, 200)
            a = int(opacity * 255)
            mesh.visual = trimesh.visual.ColorVisuals(
                mesh=mesh,
                face_colors=np.tile([r, g, b, a], (len(mesh.faces), 1)),
            )
            return mesh
        except Exception:
            return None

    def _make_wall_mesh(start, end, thickness, z_base, height, color_rgb, opacity=1.0):
        """从墙中心线生成墙体网格."""
        import math
        sx, sy = start
        ex, ey = end
        dx, dy = ex - sx, ey - sy
        length = math.sqrt(dx * dx + dy * dy)
        if length < 1:
            return None
        nx, ny = -dy / length * thickness / 2, dx / length * thickness / 2
        pts = [
            (sx + nx, sy + ny), (ex + nx, ey + ny),
            (ex - nx, ey - ny), (sx - nx, sy - ny),
        ]
        return _make_box_mesh(pts, z_base, height, color_rgb, opacity)

    grid = building.grid

    # ── 楼板 ──
    for be in building.slabs:
        slab = be.element
        elev = grid.level_elevation(slab.level)
        app = slab.resolved_appearance()
        m = _make_box_mesh(slab.boundary_points, elev, slab.thickness,
                           app.color_rgb, app.opacity)
        if m:
            meshes.append(m)

    # ── 柱子 ──
    for be in building.columns:
        col = be.element
        base_z = grid.level_elevation(col.base_level)
        top_z = grid.level_elevation(col.top_level)
        h = top_z - base_z
        hw, hd = col.section_width / 2, col.section_depth / 2
        pts = [
            (col.x - hw, col.y - hd), (col.x + hw, col.y - hd),
            (col.x + hw, col.y + hd), (col.x - hw, col.y + hd),
        ]
        app = col.resolved_appearance()
        m = _make_box_mesh(pts, base_z, h, app.color_rgb, app.opacity)
        if m:
            meshes.append(m)

    # ── 墙体 ──
    for be in building.walls:
        wall = be.element
        base_z = grid.level_elevation(wall.base_level)
        top_z = grid.level_elevation(wall.top_level)
        h = top_z - base_z
        app = wall.resolved_appearance()
        m = _make_wall_mesh(wall.start, wall.end, wall.thickness,
                            base_z, h, app.color_rgb, app.opacity)
        if m:
            meshes.append(m)

    # ── 梁 ──
    for be in building.beams:
        beam = be.element
        import math
        sx, sy = beam.start
        ex, ey = beam.end
        dx, dy = ex - sx, ey - sy
        length = math.sqrt(dx * dx + dy * dy)
        if length < 1:
            continue
        elev = grid.level_elevation(beam.level) - beam.height
        app = beam.resolved_appearance()
        m = _make_wall_mesh(beam.start, beam.end, beam.width,
                            elev, beam.height, app.color_rgb, app.opacity)
        if m:
            meshes.append(m)

    # ── 幕墙 (玻璃面板) ──
    for be in building.curtain_walls:
        cw = be.element
        base_z = grid.level_elevation(cw.base_level)
        top_z = grid.level_elevation(cw.top_level)
        h = top_z - base_z
        app = cw.resolved_appearance()
        m = _make_wall_mesh(cw.start, cw.end, cw.glass_thickness,
                            base_z, h, app.color_rgb, app.opacity)
        if m:
            meshes.append(m)

    # ── 门 (薄板模拟) ──
    from aec_building.aec.elements import Door
    for be in building.get_elements_by_type(Door):
        door = be.element
        host = building.get_element(door.host_wall_id)
        if not host:
            continue
        wall = host.element
        base_z = grid.level_elevation(wall.base_level)
        import math as _math
        sx, sy = wall.start
        ex, ey = wall.end
        dx, dy = ex - sx, ey - sy
        wlen = _math.sqrt(dx * dx + dy * dy)
        if wlen < 1:
            continue
        cx = sx + dx * door.position
        cy = sy + dy * door.position
        ux, uy = dx / wlen, dy / wlen
        hw = door.width / 2
        ds = (cx - ux * hw, cy - uy * hw)
        de = (cx + ux * hw, cy + uy * hw)
        app = door.resolved_appearance()
        m = _make_wall_mesh(ds, de, 60.0, base_z, door.height,
                            app.color_rgb, app.opacity)
        if m:
            meshes.append(m)

    # ── 窗 (薄玻璃板) ──
    from aec_building.aec.elements import Window
    for be in building.get_elements_by_type(Window):
        win = be.element
        host = building.get_element(win.host_wall_id)
        if not host:
            continue
        wall = host.element
        base_z = grid.level_elevation(wall.base_level) + win.sill_height
        import math as _math
        sx, sy = wall.start
        ex, ey = wall.end
        dx, dy = ex - sx, ey - sy
        wlen = _math.sqrt(dx * dx + dy * dy)
        if wlen < 1:
            continue
        cx = sx + dx * win.position
        cy = sy + dy * win.position
        ux, uy = dx / wlen, dy / wlen
        hw = win.width / 2
        ws = (cx - ux * hw, cy - uy * hw)
        we = (cx + ux * hw, cy + uy * hw)
        app = win.resolved_appearance()
        m = _make_wall_mesh(ws, we, 30.0, base_z, win.height,
                            app.color_rgb, app.opacity)
        if m:
            meshes.append(m)

    if not meshes:
        # 空模型 — 写一个占位立方体
        meshes.append(trimesh.creation.box(extents=[1000, 1000, 1000]))

    combined = trimesh.util.concatenate(meshes)

    # 强制计算法线 — trimesh 默认 GLB 导出可能不包含 NORMAL 属性
    # 没有法线的 GLB 在 Three.js 中会渲染为全黑
    _ = combined.vertex_normals  # 触发法线计算

    # 导出时使用 include_normals 确保法线写入 GLB
    combined.export(str(filepath), file_type='glb', include_normals=True)
    return filepath


def building_to_colored_mesh(building: object) -> object:
    """将 Building 转为带色彩的 trimesh 对象 (内部复用).

    供 GLB/OBJ/STL/DAE 等多种格式导出共享。
    """
    import trimesh

    # 直接调用 building_to_colored_glb 的前半段逻辑
    # 先导出到临时 GLB 再读回来太浪费, 改为提取公共逻辑
    # 这里直接返回 combined mesh
    import tempfile, os
    tmp = tempfile.mktemp(suffix='.glb')
    try:
        building_to_colored_glb(building, tmp)
        scene = trimesh.load(tmp)
        if hasattr(scene, 'geometry') and scene.geometry:
            meshes = list(scene.geometry.values())
            combined = trimesh.util.concatenate(meshes)
        else:
            combined = scene
        return combined
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def building_to_obj(building: object, filepath: str | Path) -> Path:
    """导出为 OBJ 格式 (通用三角网格, Blender/3ds Max/Maya 可导入)."""
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)
    mesh = building_to_colored_mesh(building)
    mesh.export(str(filepath), file_type='obj')
    # trimesh 会同时生成 .mtl 文件
    return filepath


def building_to_stl(building: object, filepath: str | Path) -> Path:
    """导出为 STL 格式 (3D 打印/FEM 分析, 无色彩)."""
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)
    mesh = building_to_colored_mesh(building)
    mesh.export(str(filepath), file_type='stl')
    return filepath


def building_to_dae(building: object, filepath: str | Path) -> Path:
    """导出为 Collada DAE 格式 (SketchUp/游戏引擎通用交换)."""
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)
    mesh = building_to_colored_mesh(building)
    mesh.export(str(filepath), file_type='dae')
    return filepath


def building_to_dxf(building: object, filepath: str | Path) -> Path:
    """导出为 DXF 格式 (AutoCAD 3D 线框 + 3DFACE).

    将构件边界导出为 3D FACE 实体, 可在 AutoCAD/中望/浩辰 CAD 中打开。
    需要 ezdxf 库: pip install ezdxf
    """
    import ezdxf

    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    doc = ezdxf.new('R2010')
    msp = doc.modelspace()

    grid = building.grid

    def _add_slab_faces(pts, z_base, thickness):
        """添加楼板的上下表面为 3DFACE."""
        n = len(pts)
        for z in [z_base, z_base + thickness]:
            for i in range(1, n - 1):
                msp.add_3dface([
                    (pts[0][0], pts[0][1], z),
                    (pts[i][0], pts[i][1], z),
                    (pts[i + 1][0], pts[i + 1][1], z),
                    (pts[i + 1][0], pts[i + 1][1], z),  # 三角形重复最后点
                ])
        # 侧面
        for i in range(n):
            j = (i + 1) % n
            msp.add_3dface([
                (pts[i][0], pts[i][1], z_base),
                (pts[j][0], pts[j][1], z_base),
                (pts[j][0], pts[j][1], z_base + thickness),
                (pts[i][0], pts[i][1], z_base + thickness),
            ])

    def _add_box(cx, cy, hw, hd, z_base, height):
        """添加矩形柱/梁为六面体 3DFACE."""
        pts = [
            (cx - hw, cy - hd), (cx + hw, cy - hd),
            (cx + hw, cy + hd), (cx - hw, cy + hd),
        ]
        _add_slab_faces(pts, z_base, height)

    import math

    # 楼板
    for be in building.slabs:
        slab = be.element
        elev = grid.level_elevation(slab.level)
        _add_slab_faces(slab.boundary_points, elev, slab.thickness)

    # 柱子
    for be in building.columns:
        col = be.element
        base_z = grid.level_elevation(col.base_level)
        top_z = grid.level_elevation(col.top_level)
        _add_box(col.x, col.y, col.section_width / 2, col.section_depth / 2,
                 base_z, top_z - base_z)

    # 墙体
    for be in building.walls:
        wall = be.element
        base_z = grid.level_elevation(wall.base_level)
        top_z = grid.level_elevation(wall.top_level)
        sx, sy = wall.start
        ex, ey = wall.end
        dx, dy = ex - sx, ey - sy
        length = math.sqrt(dx * dx + dy * dy)
        if length < 1:
            continue
        nx, ny = -dy / length * wall.thickness / 2, dx / length * wall.thickness / 2
        pts = [
            (sx + nx, sy + ny), (ex + nx, ey + ny),
            (ex - nx, ey - ny), (sx - nx, sy - ny),
        ]
        _add_slab_faces(pts, base_z, top_z - base_z)

    # 梁
    for be in building.beams:
        beam = be.element
        sx, sy = beam.start
        ex, ey = beam.end
        dx, dy = ex - sx, ey - sy
        length = math.sqrt(dx * dx + dy * dy)
        if length < 1:
            continue
        elev = grid.level_elevation(beam.level) - beam.height
        nx, ny = -dy / length * beam.width / 2, dx / length * beam.width / 2
        pts = [
            (sx + nx, sy + ny), (ex + nx, ey + ny),
            (ex - nx, ey - ny), (sx - nx, sy - ny),
        ]
        _add_slab_faces(pts, elev, beam.height)

    doc.saveas(str(filepath))
    return filepath
