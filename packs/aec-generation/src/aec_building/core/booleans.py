"""BREP 布尔运算 — 对 CadQuery 布尔操作的薄封装.

提供 cut / union / intersect 操作，用于中庭开洞、
构件组装等场景。延迟导入 CadQuery 以支持纯 Python 测试。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


def boolean_cut(base: object, tool: object) -> object:
    """布尔减：从 base 中切除 tool 形状.

    对应案例 Tool Call 6：中庭开洞。

    Args:
        base: CadQuery Workplane（被切对象）。
        tool: CadQuery Workplane（切除工具体）。

    Returns:
        切除后的 CadQuery Workplane。
    """
    return base.cut(tool)


def boolean_union(shape_a: object, shape_b: object) -> object:
    """布尔并：合并两个实体.

    Args:
        shape_a: CadQuery Workplane。
        shape_b: CadQuery Workplane。

    Returns:
        合并后的 CadQuery Workplane。
    """
    return shape_a.union(shape_b)


def boolean_intersect(shape_a: object, shape_b: object) -> object:
    """布尔交：取两个实体的交集.

    Args:
        shape_a: CadQuery Workplane。
        shape_b: CadQuery Workplane。

    Returns:
        交集 CadQuery Workplane。
    """
    return shape_a.intersect(shape_b)


def make_opening_tool(
    boundary_points: list[tuple[float, float]] | None = None,
    base_z: float = 0.0,
    height: float = 200.0,
    *,
    x_min: float | None = None,
    y_min: float | None = None,
    x_max: float | None = None,
    y_max: float | None = None,
    z_base: float | None = None,
    z_height: float | None = None,
) -> object:
    """创建一个用于开洞的工具体（拉伸棱柱）.

    支持两种调用方式：
      1. make_opening_tool(boundary_points=pts, base_z=z, height=h)
      2. make_opening_tool(x_min=..., y_min=..., x_max=..., y_max=..., z_base=..., z_height=...)

    Returns:
        CadQuery Workplane 用作 boolean_cut 的 tool 参数。
    """
    import cadquery as cq

    # 支持矩形快捷方式
    if x_min is not None and x_max is not None and y_min is not None and y_max is not None:
        boundary_points = [
            (x_min, y_min), (x_max, y_min),
            (x_max, y_max), (x_min, y_max),
        ]
    if z_base is not None:
        base_z = z_base
    if z_height is not None:
        height = z_height

    if boundary_points is None:
        raise ValueError("Must provide boundary_points or x_min/y_min/x_max/y_max")

    pts = [(p[0], p[1]) for p in boundary_points]
    tool = (
        cq.Workplane("XY")
        .workplane(offset=base_z)
        .polyline(pts)
        .close()
        .extrude(height)
    )
    return tool
