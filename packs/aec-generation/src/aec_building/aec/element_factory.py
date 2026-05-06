"""元素 → BREP 工厂 — 将 AEC 数据类转换为 CadQuery 实体.

这是连接 aec/elements.py（纯数据）与 core/shapes.py（几何内核）的桥梁。
对应案例 Tool Call 4/7/8 中的 BREP 生成行为。

设计原则：
- 所有定位基于 GridSystem 参照解析（案例 4.2）
- 批量操作在工厂内循环，而非 Agent 决策环（案例 4.1）
- 延迟导入 CadQuery，纯 Python 环境下可进行几何计算但不生成 BREP
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aec_building.aec.elements import Beam, Column, CurtainWall, CurvedRoof, Door, FloorSlab, Railing, RoundColumn, Wall
    from aec_building.aec.grid import GridSystem


@dataclass
class BrepResult:
    """BREP 生成结果，包含几何对象和验证信息.

    对应案例中每次 tool call 返回的结构化响应。
    """

    shape: object  # CadQuery Workplane
    element_id: str
    area: float = 0.0
    volume: float = 0.0
    geometry_valid: bool = True
    warnings: list[str] | None = None
    color_rgb: tuple[int, int, int] | None = None  # (R, G, B) 0~255
    opacity: float = 1.0

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []


def slab_to_brep(
    slab: FloorSlab,
    grid: GridSystem,
) -> BrepResult:
    """楼板 → BREP 实体.

    对应案例 Tool Call 4：从边界点列表拉伸生成楼板实体。
    楼板底面位于其所属标高处。

    Args:
        slab: 楼板数据对象。
        grid: 轴网系统（用于解析标高）。

    Returns:
        包含 CadQuery 实体的 BrepResult。
    """
    import cadquery as cq

    elevation = grid.level_elevation(slab.level)
    pts = slab.boundary_points

    shape = (
        cq.Workplane("XY")
        .workplane(offset=elevation)
        .polyline(pts)
        .close()
        .extrude(slab.thickness)
    )

    # 计算面积（Shoelace 公式）
    area = _polygon_area(pts)

    return BrepResult(
        shape=shape,
        element_id=f"slab_{slab.level}",
        area=area,
        volume=area * slab.thickness,
        geometry_valid=True,
        color_rgb=slab.resolved_appearance().color_rgb,
        opacity=slab.resolved_appearance().opacity,
    )


def column_to_brep(
    column: Column,
    grid: GridSystem,
) -> BrepResult:
    """结构柱 → BREP 实体.

    对应案例 Tool Call 7 中的单根柱子生成。
    生成方管型钢柱（HSS），从 base_level 拉伸到 top_level。

    Args:
        column: 柱数据对象。
        grid: 轴网系统。

    Returns:
        包含 CadQuery 实体的 BrepResult。
    """
    import cadquery as cq

    base_z = grid.level_elevation(column.base_level)
    top_z = grid.level_elevation(column.top_level)
    height = top_z - base_z

    w = column.section_width
    d = column.section_depth
    t = column.section_thickness

    # 方管截面：外矩形减内矩形
    shape = (
        cq.Workplane("XY")
        .workplane(offset=base_z)
        .center(column.x, column.y)
        .rect(w, d)
        .extrude(height)
    )
    # 掏空内部形成方管
    inner = (
        cq.Workplane("XY")
        .workplane(offset=base_z)
        .center(column.x, column.y)
        .rect(w - 2 * t, d - 2 * t)
        .extrude(height)
    )
    shape = shape.cut(inner)

    return BrepResult(
        shape=shape,
        element_id=f"col_{column.x:.0f}_{column.y:.0f}",
        volume=((w * d) - (w - 2 * t) * (d - 2 * t)) * height,
        geometry_valid=True,
        color_rgb=column.resolved_appearance().color_rgb,
        opacity=column.resolved_appearance().opacity,
    )


def wall_to_brep(
    wall: Wall,
    grid: GridSystem,
    top_offset: float = 0.0,
) -> BrepResult:
    """墙体 → BREP 实体.

    对应案例 Tool Call 8：从墙中心线两侧各偏移半个厚度，拉伸到指定高度。

    Args:
        wall: 墙数据对象。
        grid: 轴网系统。
        top_offset: 顶部额外偏移 (mm)，用于出屋面核心筒（案例 TC9）。

    Returns:
        包含 CadQuery 实体的 BrepResult。
    """
    import cadquery as cq

    base_z = grid.level_elevation(wall.base_level)
    top_z = grid.level_elevation(wall.top_level) + top_offset
    height = top_z - base_z

    sx, sy = wall.start
    ex, ey = wall.end
    half_t = wall.thickness / 2.0

    # 墙中心线方向向量
    dx = ex - sx
    dy = ey - sy
    length = math.sqrt(dx * dx + dy * dy)
    if length < 1e-6:
        return BrepResult(
            shape=None,
            element_id="wall_invalid",
            geometry_valid=False,
            warnings=["Wall length is zero"],
        )

    # 法线方向（逆时针旋转 90°）
    nx = -dy / length * half_t
    ny = dx / length * half_t

    # 矩形四角
    pts = [
        (sx + nx, sy + ny),
        (ex + nx, ey + ny),
        (ex - nx, ey - ny),
        (sx - nx, sy - ny),
    ]

    shape = (
        cq.Workplane("XY")
        .workplane(offset=base_z)
        .polyline(pts)
        .close()
        .extrude(height)
    )

    wall_area = length * height

    return BrepResult(
        shape=shape,
        element_id=f"wall_{sx:.0f}_{sy:.0f}_{ex:.0f}_{ey:.0f}",
        area=wall_area,
        volume=length * wall.thickness * height,
        geometry_valid=True,
        color_rgb=wall.resolved_appearance().color_rgb,
        opacity=wall.resolved_appearance().opacity,
    )


def batch_columns_to_brep(
    columns: list[Column],
    grid: GridSystem,
) -> list[BrepResult]:
    """批量柱子 → BREP.

    对应案例 Tool Call 7 的设计原则（案例 4.1）：
    粗粒度优于细粒度，把循环放到脚本里而非 Agent 决策环。

    Args:
        columns: 柱列表。
        grid: 轴网系统。

    Returns:
        BrepResult 列表。
    """
    results = []
    for col in columns:
        results.append(column_to_brep(col, grid))
    return results


def batch_walls_to_brep(
    walls: list[Wall],
    grid: GridSystem,
    top_offset: float = 0.0,
) -> list[BrepResult]:
    """批量墙体 → BREP."""
    results = []
    for wall in walls:
        results.append(wall_to_brep(wall, grid, top_offset))
    return results


def beam_to_brep(
    beam: Beam,
    grid: GridSystem,
) -> BrepResult:
    """梁 → BREP 实体.

    梁沿 start→end 中心线拉伸矩形截面。
    梁底标高 = 所属层标高 - 梁高（挂在楼板下方）。

    Args:
        beam: 梁数据对象。
        grid: 轴网系统。

    Returns:
        BrepResult。
    """
    import cadquery as cq

    sx, sy = beam.start
    ex, ey = beam.end
    dx = ex - sx
    dy = ey - sy
    length = math.sqrt(dx * dx + dy * dy)

    if length < 1e-6:
        return BrepResult(
            shape=None, element_id="beam_invalid",
            geometry_valid=False, warnings=["Beam length is zero"],
        )

    elev = grid.level_elevation(beam.level)
    z_bottom = elev - beam.height  # 梁底挂在楼板下

    # 计算中心线方向角
    angle = math.degrees(math.atan2(dy, dx))
    cx = (sx + ex) / 2
    cy = (sy + ey) / 2

    shape = (
        cq.Workplane("XY")
        .workplane(offset=z_bottom)
        .center(cx, cy)
        .rect(length, beam.width)
        .extrude(beam.height)
    )
    # 旋转到正确方向
    if abs(angle) > 0.01:
        shape = shape.rotate((cx, cy, z_bottom), (cx, cy, z_bottom + 1), angle)

    return BrepResult(
        shape=shape,
        element_id=f"beam_{sx:.0f}_{sy:.0f}_{ex:.0f}_{ey:.0f}",
        area=length * beam.width * 2 + length * beam.height * 2,
        volume=length * beam.width * beam.height,
        geometry_valid=True,
        color_rgb=beam.resolved_appearance().color_rgb,
        opacity=beam.resolved_appearance().opacity,
    )


def batch_beams_to_brep(
    beams: list[Beam],
    grid: GridSystem,
) -> list[BrepResult]:
    """批量梁 → BREP."""
    return [beam_to_brep(b, grid) for b in beams]


def _polygon_area(pts: list[tuple[float, float]]) -> float:
    """Shoelace 公式计算多边形面积 (mm² → m²)."""
    n = len(pts)
    if n < 3:
        return 0.0
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += pts[i][0] * pts[j][1]
        area -= pts[j][0] * pts[i][1]
    return abs(area) / 2.0 / 1e6  # mm² → m²


def curtain_wall_to_brep(
    cw: CurtainWall,
    grid: GridSystem,
) -> BrepResult:
    """幕墙 → BREP 实体.

    对应案例 TC 13：生成竖梃框架 + 玻璃面板。
    简化模型：竖梃为沿墙面法线拉伸的矩形截面。

    Args:
        cw: 幕墙数据对象。
        grid: 轴网系统。

    Returns:
        BrepResult。
    """
    import cadquery as cq

    base_z = grid.level_elevation(cw.base_level)
    top_z = grid.level_elevation(cw.top_level)
    height = top_z - base_z

    sx, sy = cw.start
    ex, ey = cw.end
    dx = ex - sx
    dy = ey - sy
    wall_length = math.sqrt(dx * dx + dy * dy)

    if wall_length < 1e-6:
        return BrepResult(
            shape=None, element_id="curtain_invalid",
            geometry_valid=False, warnings=["Curtain wall length is zero"],
        )

    # 计算面板数量
    panel_count = max(1, int(wall_length / cw.panel_width))
    actual_panel_w = wall_length / panel_count

    # 法线方向
    nx = -dy / wall_length
    ny = dx / wall_length

    # 生成竖梃（垂直杆件）
    shapes = []
    for i in range(panel_count + 1):
        frac = i / panel_count
        mx = sx + dx * frac
        my = sy + dy * frac
        mullion = (
            cq.Workplane("XY")
            .workplane(offset=base_z)
            .center(mx + nx * cw.mullion_depth / 2, my + ny * cw.mullion_depth / 2)
            .rect(cw.mullion_width, cw.mullion_depth)
            .extrude(height)
        )
        shapes.append(mullion)

    # 合并所有竖梃
    result_shape = shapes[0]
    for s in shapes[1:]:
        result_shape = result_shape.union(s)

    return BrepResult(
        shape=result_shape,
        element_id=f"curtain_{sx:.0f}_{sy:.0f}_{ex:.0f}_{ey:.0f}",
        area=wall_length * height,
        volume=0.0,  # 幕墙体积不直接有意义
        geometry_valid=True,
    )


def door_to_brep(
    door: Door,
    wall: Wall,
    grid: GridSystem,
) -> BrepResult:
    """门 → 开洞工具体 + 门扇 BREP.

    返回门扇实体（用于可视化），调用方需用
    开洞工具体对墙执行 boolean_cut。

    Args:
        door: 门数据对象。
        wall: 所属墙体。
        grid: 轴网系统。

    Returns:
        BrepResult（门扇实体）。
    """
    import cadquery as cq

    base_z = grid.level_elevation(wall.base_level)

    sx, sy = wall.start
    ex, ey = wall.end
    dx = ex - sx
    dy = ey - sy
    wall_length = math.sqrt(dx * dx + dy * dy)

    # 门在墙中心线上的位置
    pos = door.position
    cx = sx + dx * pos
    cy = sy + dy * pos

    # 法线方向
    nx = -dy / wall_length
    ny = dx / wall_length

    # 门扇简化为薄板
    door_thickness = 45.0  # mm
    shape = (
        cq.Workplane("XY")
        .workplane(offset=base_z)
        .center(cx, cy)
        .rect(door.width, door_thickness)
        .extrude(door.height)
    )

    return BrepResult(
        shape=shape,
        element_id=f"door_{cx:.0f}_{cy:.0f}",
        area=door.width * door.height,
        geometry_valid=True,
    )


# ── LOD 300: 圆柱、曲面屋顶、栏杆 ──


def round_column_to_brep(
    column: "RoundColumn",
    grid: GridSystem,
) -> BrepResult:
    """圆柱 → BREP 实体.

    生成圆柱体（实心），从 base_level 拉伸到 top_level。

    Args:
        column: 圆柱数据对象。
        grid: 轴网系统。

    Returns:
        BrepResult。
    """
    import cadquery as cq

    base_z = grid.level_elevation(column.base_level)
    top_z = grid.level_elevation(column.top_level)
    height = top_z - base_z
    r = column.diameter / 2.0

    shape = (
        cq.Workplane("XY")
        .workplane(offset=base_z)
        .center(column.x, column.y)
        .circle(r)
        .extrude(height)
    )

    area = math.pi * r * r
    return BrepResult(
        shape=shape,
        element_id=f"rcol_{column.x:.0f}_{column.y:.0f}",
        area=area / 1e6,
        volume=area * height,
        geometry_valid=True,
        color_rgb=column.resolved_appearance().color_rgb,
        opacity=column.resolved_appearance().opacity,
    )


def batch_round_columns_to_brep(
    columns: list["RoundColumn"],
    grid: GridSystem,
) -> list[BrepResult]:
    """批量圆柱 → BREP."""
    return [round_column_to_brep(c, grid) for c in columns]


def _compute_polygon_centroid(pts: list[tuple[float, float]]) -> tuple[float, float]:
    """计算多边形质心."""
    n = len(pts)
    cx = sum(p[0] for p in pts) / n
    cy = sum(p[1] for p in pts) / n
    return cx, cy


def _offset_polygon(
    pts: list[tuple[float, float]], offset: float,
) -> list[tuple[float, float]]:
    """向外扩展多边形 (正值外扩, 负值内缩), 基于质心方向."""
    cx, cy = _compute_polygon_centroid(pts)
    result = []
    for px, py in pts:
        dx = px - cx
        dy = py - cy
        dist = math.sqrt(dx * dx + dy * dy)
        if dist < 1e-6:
            result.append((px, py))
        else:
            factor = (dist + offset) / dist
            result.append((cx + dx * factor, cy + dy * factor))
    return result


def curved_roof_to_brep(
    roof: "CurvedRoof",
    grid: GridSystem,
) -> BrepResult:
    """曲面屋顶 → BREP 实体.

    根据 roof_type 生成不同屋顶几何:
    - HIP/HALF_HIP: 四坡顶, 由底边多边形 loft 到脊线
    - GABLE: 两坡顶, 由底边 loft 到脊线
    - CONICAL: 锥形顶, 由底边多边形 loft 到尖点
    - FLAT: 平屋顶 (带出挑)

    檐口翘起 (eave_rise > 0) 通过在出挑端点抬高实现。

    Args:
        roof: 屋顶数据对象。
        grid: 轴网系统。

    Returns:
        BrepResult。
    """
    import cadquery as cq
    from aec_building.aec.elements import RoofType

    base_z = grid.level_elevation(roof.base_level)
    pts = roof.boundary_points
    n = len(pts)

    if n < 3:
        return BrepResult(
            shape=None, element_id="roof_invalid",
            geometry_valid=False, warnings=["Roof needs at least 3 boundary points"],
        )

    cx, cy = _compute_polygon_centroid(pts)

    # 出挑后的檐口轮廓
    eave_pts = _offset_polygon(pts, roof.overhang) if roof.overhang > 0 else list(pts)

    if roof.roof_type == RoofType.FLAT:
        # 平屋顶: 带出挑的厚板
        shape = (
            cq.Workplane("XY")
            .workplane(offset=base_z)
            .polyline(eave_pts)
            .close()
            .extrude(roof.thickness)
        )
        area = _polygon_area(eave_pts) * 1e6  # m² → mm²
        return BrepResult(
            shape=shape,
            element_id=f"roof_flat_{base_z:.0f}",
            area=_polygon_area(eave_pts),
            volume=area * roof.thickness,
            geometry_valid=True,
            color_rgb=roof.resolved_appearance().color_rgb,
            opacity=roof.resolved_appearance().opacity,
        )

    if roof.roof_type == RoofType.CONICAL:
        # 攒尖顶: 底边多边形 → 顶部尖点, 使用 CQ loft
        ridge_z = base_z + roof.ridge_height

        # 底面 wire
        base_wire = (
            cq.Workplane("XY")
            .workplane(offset=base_z + roof.eave_rise)
            .polyline(eave_pts)
            .close()
        )

        # 顶部用微小多边形近似尖点
        tip_radius = 50.0  # mm, 近似点
        tip_pts = []
        for i in range(n):
            angle = math.radians(i * 360 / n)
            tip_pts.append((
                cx + tip_radius * math.cos(angle),
                cy + tip_radius * math.sin(angle),
            ))
        top_wire = (
            cq.Workplane("XY")
            .workplane(offset=ridge_z)
            .polyline(tip_pts)
            .close()
        )

        shape = cq.Workplane("XY").add(base_wire).add(top_wire).loft(ruled=True)

        return BrepResult(
            shape=shape,
            element_id=f"roof_conical_{base_z:.0f}",
            area=_polygon_area(eave_pts),
            geometry_valid=True,
            color_rgb=roof.resolved_appearance().color_rgb,
            opacity=roof.resolved_appearance().opacity,
        )

    # HIP / HALF_HIP / GABLE: 需要矩形底边 (取外包矩形)
    xs = [p[0] for p in eave_pts]
    ys = [p[1] for p in eave_pts]
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)
    length_x = x_max - x_min
    length_y = y_max - y_min

    ridge_z = base_z + roof.ridge_height
    eave_z = base_z + roof.eave_rise  # 檐口翘起

    # 确定脊线方向 (沿较长方向)
    if length_x >= length_y:
        # 脊线沿 X, 坡面沿 Y
        ridge_inset = length_x * 0.15 if roof.roof_type != RoofType.GABLE else 0
        ridge_pts_base = [
            (x_min + ridge_inset, cy),
            (x_max - ridge_inset, cy),
        ]
    else:
        # 脊线沿 Y, 坡面沿 X
        ridge_inset = length_y * 0.15 if roof.roof_type != RoofType.GABLE else 0
        ridge_pts_base = [
            (cx, y_min + ridge_inset),
            (cx, y_max - ridge_inset),
        ]

    # 构建屋顶多面体: 底边 + 脊线点
    # 使用 polyhedron 方法: 定义顶点和面
    eave_3d = [(p[0], p[1], eave_z) for p in eave_pts]
    ridge_3d = [(p[0], p[1], ridge_z) for p in ridge_pts_base]

    if roof.roof_type == RoofType.GABLE:
        # 两坡顶: 只有两端三角形山花
        # 底面4点 + 脊线2点 = 6点
        # 简化: 用 loft
        base_wire = (
            cq.Workplane("XY")
            .workplane(offset=eave_z)
            .polyline(eave_pts)
            .close()
        )
        # 脊线: 沿主方向的窄矩形
        ridge_half_w = roof.thickness / 2
        if length_x >= length_y:
            ridge_rect = [
                (x_min, cy - ridge_half_w),
                (x_max, cy - ridge_half_w),
                (x_max, cy + ridge_half_w),
                (x_min, cy + ridge_half_w),
            ]
        else:
            ridge_rect = [
                (cx - ridge_half_w, y_min),
                (cx + ridge_half_w, y_min),
                (cx + ridge_half_w, y_max),
                (cx - ridge_half_w, y_max),
            ]
        top_wire = (
            cq.Workplane("XY")
            .workplane(offset=ridge_z)
            .polyline(ridge_rect)
            .close()
        )
        shape = cq.Workplane("XY").add(base_wire).add(top_wire).loft(ruled=True)

    else:
        # HIP / HALF_HIP: 四坡顶
        # 底面外轮廓 → 脊线窄矩形, loft 生成
        base_wire = (
            cq.Workplane("XY")
            .workplane(offset=eave_z)
            .polyline(eave_pts)
            .close()
        )
        ridge_half_w = roof.thickness / 2
        r0, r1 = ridge_pts_base[0], ridge_pts_base[1]
        if length_x >= length_y:
            ridge_rect = [
                (r0[0], r0[1] - ridge_half_w),
                (r1[0], r1[1] - ridge_half_w),
                (r1[0], r1[1] + ridge_half_w),
                (r0[0], r0[1] + ridge_half_w),
            ]
        else:
            ridge_rect = [
                (r0[0] - ridge_half_w, r0[1]),
                (r1[0] - ridge_half_w, r1[1]),
                (r1[0] + ridge_half_w, r1[1]),
                (r0[0] + ridge_half_w, r0[1]),
            ]
        top_wire = (
            cq.Workplane("XY")
            .workplane(offset=ridge_z)
            .polyline(ridge_rect)
            .close()
        )
        shape = cq.Workplane("XY").add(base_wire).add(top_wire).loft(ruled=True)

    return BrepResult(
        shape=shape,
        element_id=f"roof_{roof.roof_type.value}_{base_z:.0f}",
        area=_polygon_area(eave_pts),
        geometry_valid=True,
        color_rgb=roof.resolved_appearance().color_rgb,
        opacity=roof.resolved_appearance().opacity,
    )


def railing_to_brep(
    railing: "Railing",
    grid: GridSystem,
) -> BrepResult:
    """栏杆 → BREP 实体.

    沿路径生成: 立柱 (按间距) + 顶部扶手 (连续) + 可选底部横杆。

    Args:
        railing: 栏杆数据对象。
        grid: 轴网系统。

    Returns:
        BrepResult (union of all sub-shapes)。
    """
    import cadquery as cq

    base_z = grid.level_elevation(railing.level)
    path_pts = railing.path_points

    if len(path_pts) < 2:
        return BrepResult(
            shape=None, element_id="railing_invalid",
            geometry_valid=False, warnings=["Railing needs at least 2 path points"],
        )

    shapes = []

    # ── 1. 立柱: 沿路径按间距放置 ──
    # 计算路径总长和每段长度
    segments = []
    total_length = 0.0
    for i in range(len(path_pts) - 1):
        sx, sy = path_pts[i]
        ex, ey = path_pts[i + 1]
        seg_len = math.sqrt((ex - sx) ** 2 + (ey - sy) ** 2)
        segments.append((sx, sy, ex, ey, seg_len))
        total_length += seg_len

    # 生成立柱位置 (起点、终点各一根 + 中间按间距)
    post_positions = []
    if total_length < 1e-6:
        return BrepResult(
            shape=None, element_id="railing_invalid",
            geometry_valid=False, warnings=["Railing path length is zero"],
        )

    n_posts = max(2, int(total_length / railing.post_spacing) + 1)
    for i in range(n_posts):
        t = i / max(1, n_posts - 1) * total_length
        # 在路径上找到 t 对应的点
        accumulated = 0.0
        for sx, sy, ex, ey, seg_len in segments:
            if accumulated + seg_len >= t - 1e-6 or sx == segments[-1][0]:
                frac = (t - accumulated) / seg_len if seg_len > 1e-6 else 0
                frac = max(0.0, min(1.0, frac))
                px = sx + (ex - sx) * frac
                py = sy + (ey - sy) * frac
                post_positions.append((px, py))
                break
            accumulated += seg_len

    # 生成立柱几何
    for px, py in post_positions:
        post = (
            cq.Workplane("XY")
            .workplane(offset=base_z)
            .center(px, py)
            .rect(railing.post_width, railing.post_depth)
            .extrude(railing.height)
        )
        shapes.append(post)

    # ── 2. 顶部扶手: 沿路径各段连续梁 ──
    rail_z = base_z + railing.height - railing.rail_height
    for sx, sy, ex, ey, seg_len in segments:
        if seg_len < 1e-6:
            continue
        mid_x = (sx + ex) / 2
        mid_y = (sy + ey) / 2
        angle = math.degrees(math.atan2(ey - sy, ex - sx))

        rail = (
            cq.Workplane("XY")
            .workplane(offset=rail_z)
            .center(mid_x, mid_y)
            .rect(seg_len, railing.rail_width)
            .extrude(railing.rail_height)
        )
        if abs(angle) > 0.01:
            rail = rail.rotate(
                (mid_x, mid_y, rail_z),
                (mid_x, mid_y, rail_z + 1),
                angle,
            )
        shapes.append(rail)

    # ── 3. 底部横杆 (可选) ──
    if railing.bottom_rail:
        bottom_z = base_z + railing.bottom_rail_height - railing.rail_height
        for sx, sy, ex, ey, seg_len in segments:
            if seg_len < 1e-6:
                continue
            mid_x = (sx + ex) / 2
            mid_y = (sy + ey) / 2
            angle = math.degrees(math.atan2(ey - sy, ex - sx))

            bottom = (
                cq.Workplane("XY")
                .workplane(offset=bottom_z)
                .center(mid_x, mid_y)
                .rect(seg_len, railing.rail_width)
                .extrude(railing.rail_height)
            )
            if abs(angle) > 0.01:
                bottom = bottom.rotate(
                    (mid_x, mid_y, bottom_z),
                    (mid_x, mid_y, bottom_z + 1),
                    angle,
                )
            shapes.append(bottom)

    # 合并所有子形状
    if not shapes:
        return BrepResult(
            shape=None, element_id="railing_empty",
            geometry_valid=False, warnings=["No railing geometry generated"],
        )

    result_shape = shapes[0]
    for s in shapes[1:]:
        result_shape = result_shape.union(s)

    return BrepResult(
        shape=result_shape,
        element_id=f"railing_{path_pts[0][0]:.0f}_{path_pts[0][1]:.0f}",
        geometry_valid=True,
        color_rgb=railing.resolved_appearance().color_rgb,
        opacity=railing.resolved_appearance().opacity,
    )


def batch_railings_to_brep(
    railings: list["Railing"],
    grid: GridSystem,
) -> list[BrepResult]:
    """批量栏杆 → BREP."""
    return [railing_to_brep(r, grid) for r in railings]
