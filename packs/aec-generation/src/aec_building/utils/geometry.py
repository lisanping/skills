"""几何辅助函数 — 多边形生成、环形布点等.

可用于非矩形平面建筑建模（八角塔、圆形大厅等）。
"""

from __future__ import annotations

import math


def regular_polygon_points(
    cx: float,
    cy: float,
    radius: float,
    n: int = 8,
    start_angle: float = 22.5,
) -> list[tuple[float, float]]:
    """生成正多边形顶点坐标.

    Args:
        cx, cy: 中心点 (mm)。
        radius: 外接圆半径 (mm)。
        n: 边数（默认 8 = 八角形）。
        start_angle: 起始角度 (度)。

    Returns:
        n 个顶点 [(x, y), ...]。
    """
    pts = []
    for i in range(n):
        angle = math.radians(start_angle + i * 360 / n)
        pts.append((
            round(cx + radius * math.cos(angle), 1),
            round(cy + radius * math.sin(angle), 1),
        ))
    return pts


def octagon_points(
    cx: float, cy: float, radius: float, start_angle: float = 22.5,
) -> list[tuple[float, float]]:
    """生成八角形顶点坐标（regular_polygon_points 的快捷方式）."""
    return regular_polygon_points(cx, cy, radius, n=8, start_angle=start_angle)


def ring_positions(
    cx: float,
    cy: float,
    radius: float,
    n: int = 8,
    offset_angle: float = 0,
) -> list[tuple[float, float]]:
    """生成环形等分点（柱位、灯位等）.

    Args:
        cx, cy: 圆心 (mm)。
        radius: 环半径 (mm)。
        n: 点数。
        offset_angle: 起始偏移角度 (度)。

    Returns:
        n 个坐标 [(x, y), ...]。
    """
    pts = []
    for i in range(n):
        angle = math.radians(offset_angle + i * 360 / n)
        pts.append((
            round(cx + radius * math.cos(angle), 1),
            round(cy + radius * math.sin(angle), 1),
        ))
    return pts


def polygon_area(pts: list[tuple[float, float]]) -> float:
    """Shoelace 公式计算多边形面积 (mm²)."""
    n = len(pts)
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += pts[i][0] * pts[j][1]
        area -= pts[j][0] * pts[i][1]
    return abs(area) / 2.0
