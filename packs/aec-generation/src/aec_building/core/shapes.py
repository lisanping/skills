"""BREP 实体构造器 — 从轮廓线生成 BREP Solid.

依赖 CadQuery / OCCT，提供面向 AEC 的高层接口。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from .primitives import Point3D


def make_extruded_solid(
    profile_points: Sequence[Point3D],
    height: float,
) -> object:
    """从 2D 轮廓点列表拉伸生成 BREP 实体.

    Args:
        profile_points: 闭合轮廓顶点（XY 平面），按逆时针排列。
        height: 拉伸高度（沿 Z 轴正方向），单位 mm。

    Returns:
        CadQuery Workplane 对象（包含一个 Solid）。
    """
    import cadquery as cq

    pts = [(p.x, p.y) for p in profile_points]
    result = cq.Workplane("XY").polyline(pts).close().extrude(height)
    return result


def make_l_shape_floor(
    total_x: float,
    total_y: float,
    cutout_x: float,
    cutout_y: float,
    thickness: float,
    cutout_corner: str = "NE",
) -> object:
    """生成 L 形楼板 BREP.

    Args:
        total_x: 外包矩形 X 方向总长 (mm)。
        total_y: 外包矩形 Y 方向总长 (mm)。
        cutout_x: 切除矩形 X 方向尺寸 (mm)。
        cutout_y: 切除矩形 Y 方向尺寸 (mm)。
        thickness: 楼板厚度 (mm)。
        cutout_corner: 切除角位置，"NE"/"NW"/"SE"/"SW"。

    Returns:
        CadQuery Workplane 对象。
    """
    import cadquery as cq

    base = cq.Workplane("XY").box(total_x, total_y, thickness)

    # 根据切除角计算偏移
    offsets = {
        "NE": ((total_x - cutout_x) / 2, (total_y - cutout_y) / 2),
        "NW": (-(total_x - cutout_x) / 2, (total_y - cutout_y) / 2),
        "SE": ((total_x - cutout_x) / 2, -(total_y - cutout_y) / 2),
        "SW": (-(total_x - cutout_x) / 2, -(total_y - cutout_y) / 2),
    }
    ox, oy = offsets[cutout_corner]

    cutout = (
        cq.Workplane("XY")
        .center(ox, oy)
        .box(cutout_x, cutout_y, thickness)
    )
    result = base.cut(cutout)
    return result
