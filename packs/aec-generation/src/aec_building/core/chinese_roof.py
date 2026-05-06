"""中国传统建筑屋顶 — 基于 OCP 的光滑曲面建模.

支持庑殿顶 (hip roof) 的四面弧形屋面:
- 反宇曲线 (concave longitudinal profile)
- 翘角 (upturned eave corners)
- 正脊 + 垂脊 + 戗脊 (ridges)
- 鸱吻 (chiwen) + 走兽 (zoushou) 脊饰

每个屋面是 OCP BRepOffsetAPI_ThruSections 放样的光滑曲面。
"""

from __future__ import annotations

import math
from typing import Sequence


def _make_roof_panel(
    eave_pts: list[tuple[float, float]],
    ridge_pts: list[tuple[float, float]],
    z_eave: float,
    z_ridge: float,
    n_sections: int = 14,
    concavity: float = 0.6,
    sag: float = 0.08,
    upturn: float = 0.12,
    thickness: float = 300.0,
) -> object | None:
    """创建单面弧形屋面板 (从檐口到脊线的放样曲面).

    Args:
        eave_pts: 檐口两端点 [(x1,y1), (x2,y2)]
        ridge_pts: 脊线两端点 [(x1,y1), (x2,y2)]
        z_eave: 檐口标高
        z_ridge: 脊线标高
        n_sections: 截面数
        concavity: 纵向凹曲程度 (0.5-0.7, 越大越凹)
        sag: 横向下垂 (反宇)
        upturn: 角部翘起
        thickness: 屋面厚度

    Returns:
        OCP TopoDS_Shape, 或 None
    """
    from OCP.gp import gp_Pnt
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeWire
    from OCP.BRepOffsetAPI import BRepOffsetAPI_ThruSections
    from OCP.Geom import Geom_BezierCurve
    from OCP.TColgp import TColgp_Array1OfPnt

    loft = BRepOffsetAPI_ThruSections(True, False)
    h_total = z_ridge - z_eave
    added = 0

    for i in range(n_sections + 1):
        t = i / n_sections  # 0=檐口, 1=脊线

        # 插值檐口→脊线端点
        x1 = eave_pts[0][0] + (ridge_pts[0][0] - eave_pts[0][0]) * t
        y1 = eave_pts[0][1] + (ridge_pts[0][1] - eave_pts[0][1]) * t
        x2 = eave_pts[1][0] + (ridge_pts[1][0] - eave_pts[1][0]) * t
        y2 = eave_pts[1][1] + (ridge_pts[1][1] - eave_pts[1][1]) * t

        # 纵向凹曲线 (反宇): 檐口处陡, 脊线处缓
        z_curve = z_eave + h_total * (1 - (1 - t) ** concavity)

        # 横向下垂 (中间略低于两端)
        mid_sag = sag * h_total * math.sin(math.pi * t) * (1 - t)

        # 翘角 (檐口附近两端上翘)
        tip_lift = upturn * h_total * (1 - t) ** 2.5

        mx = (x1 + x2) / 2
        my = (y1 + y2) / 2

        # 5 点 Bezier 截面: 边→中间凹→边
        pts = TColgp_Array1OfPnt(1, 5)
        pts.SetValue(1, gp_Pnt(x1, y1, z_curve + tip_lift))
        pts.SetValue(2, gp_Pnt(
            x1 * 0.65 + mx * 0.35,
            y1 * 0.65 + my * 0.35,
            z_curve - mid_sag * 0.4 + tip_lift * 0.4,
        ))
        pts.SetValue(3, gp_Pnt(mx, my, z_curve - mid_sag))
        pts.SetValue(4, gp_Pnt(
            x2 * 0.65 + mx * 0.35,
            y2 * 0.65 + my * 0.35,
            z_curve - mid_sag * 0.4 + tip_lift * 0.4,
        ))
        pts.SetValue(5, gp_Pnt(x2, y2, z_curve + tip_lift))

        bezier = Geom_BezierCurve(pts)
        edge = BRepBuilderAPI_MakeEdge(bezier).Edge()
        wire = BRepBuilderAPI_MakeWire(edge).Wire()
        loft.AddWire(wire)
        added += 1

    if added < 3:
        return None

    loft.Build()
    return loft.Shape() if loft.IsDone() else None


def make_hip_roof(
    cx: float,
    cy: float,
    eave_hw: float,
    eave_hd: float,
    ridge_hw: float,
    z_eave: float,
    z_ridge: float,
    concavity: float = 0.6,
    sag: float = 0.08,
    upturn: float = 0.12,
) -> list[tuple[object, str]]:
    """创建完整的庑殿顶 (四面弧形屋面 + 正脊).

    庑殿顶特征: 四面坡, 前后坡面大, 两侧三角形坡面。
    正脊线比檐口短, 没有山墙。

    Args:
        cx, cy: 屋顶中心
        eave_hw, eave_hd: 檐口半宽/半深 (含出檐)
        ridge_hw: 正脊半长 (< eave_hw)
        z_eave: 檐口标高
        z_ridge: 正脊标高
        concavity: 反宇凹度
        sag: 横向下垂
        upturn: 翘角

    Returns:
        [(shape, panel_name), ...] — 屋面板 + 名称
    """
    panels = []

    # 檐口四角
    sw = (cx - eave_hw, cy - eave_hd)
    se = (cx + eave_hw, cy - eave_hd)
    ne = (cx + eave_hw, cy + eave_hd)
    nw = (cx - eave_hw, cy + eave_hd)

    # 脊线端点
    ridge_w = (cx - ridge_hw, cy)
    ridge_e = (cx + ridge_hw, cy)

    # 南坡 (前面, 面积最大)
    south = _make_roof_panel(
        eave_pts=[sw, se], ridge_pts=[ridge_w, ridge_e],
        z_eave=z_eave, z_ridge=z_ridge,
        concavity=concavity, sag=sag, upturn=upturn,
    )
    if south:
        panels.append((south, "south"))

    # 北坡 (后面)
    north = _make_roof_panel(
        eave_pts=[ne, nw], ridge_pts=[ridge_e, ridge_w],
        z_eave=z_eave, z_ridge=z_ridge,
        concavity=concavity, sag=sag, upturn=upturn,
    )
    if north:
        panels.append((north, "north"))

    # 东坡 (三角形)
    east = _make_roof_panel(
        eave_pts=[se, ne], ridge_pts=[(cx + ridge_hw, cy), (cx + ridge_hw, cy)],
        z_eave=z_eave, z_ridge=z_ridge,
        concavity=concavity, sag=sag * 0.5, upturn=upturn,
    )
    if east:
        panels.append((east, "east"))

    # 西坡 (三角形)
    west = _make_roof_panel(
        eave_pts=[nw, sw], ridge_pts=[(cx - ridge_hw, cy), (cx - ridge_hw, cy)],
        z_eave=z_eave, z_ridge=z_ridge,
        concavity=concavity, sag=sag * 0.5, upturn=upturn,
    )
    if west:
        panels.append((west, "west"))

    return panels


def make_ridge_beam(
    p1: tuple[float, float, float],
    p2: tuple[float, float, float],
    width: float = 600.0,
    height: float = 800.0,
) -> object | None:
    """创建脊线构件 (正脊/垂脊/戗脊).

    用矩形截面沿两点拉伸。

    Returns:
        OCP TopoDS_Shape 或 None
    """
    from OCP.gp import gp_Pnt, gp_Vec
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeWire, BRepBuilderAPI_MakeFace
    from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
    import math

    x1, y1, z1 = p1
    x2, y2, z2 = p2
    dx, dy, dz = x2 - x1, y2 - y1, z2 - z1
    length = math.sqrt(dx * dx + dy * dy + dz * dz)
    if length < 10:
        return None

    # 在 p1 处创建矩形截面, 沿 p1→p2 方向拉伸
    nx, ny = -dy / math.sqrt(dx*dx + dy*dy + 0.001), dx / math.sqrt(dx*dx + dy*dy + 0.001)
    hw, hh = width / 2, height / 2

    pts = [
        gp_Pnt(x1 + nx * hw, y1 + ny * hw, z1 - hh),
        gp_Pnt(x1 - nx * hw, y1 - ny * hw, z1 - hh),
        gp_Pnt(x1 - nx * hw, y1 - ny * hw, z1 + hh),
        gp_Pnt(x1 + nx * hw, y1 + ny * hw, z1 + hh),
    ]

    wire = BRepBuilderAPI_MakeWire()
    for i in range(4):
        edge = BRepBuilderAPI_MakeEdge(pts[i], pts[(i + 1) % 4]).Edge()
        wire.Add(edge)
    face = BRepBuilderAPI_MakeFace(wire.Wire()).Face()

    prism = BRepPrimAPI_MakePrism(face, gp_Vec(dx, dy, dz))
    prism.Build()
    return prism.Shape() if prism.IsDone() else None


def make_chiwen(
    x: float, y: float, z: float,
    height: float = 2500.0,
    width: float = 800.0,
    depth: float = 1200.0,
    facing: str = "north",
) -> object | None:
    """创建鸱吻 (正脊两端的龙头形脊饰).

    用简化的弯曲体模拟: 底部方形→中部圆弧→顶部尾巴翘起。
    """
    from OCP.gp import gp_Pnt
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeWire
    from OCP.BRepOffsetAPI import BRepOffsetAPI_ThruSections
    from OCP.Geom import Geom_BezierCurve
    from OCP.TColgp import TColgp_Array1OfPnt

    loft = BRepOffsetAPI_ThruSections(True, False)
    n = 8
    hw, hd = width / 2, depth / 2

    # 方向
    dy_dir = 1.0 if facing == "north" else -1.0

    for i in range(n + 1):
        t = i / n
        # 从底部方形到顶部窄+翘起
        w = hw * (1 - 0.3 * t)
        d = hd * (1 - 0.5 * t)
        z_pos = z + height * t
        y_offset = dy_dir * depth * 0.4 * math.sin(t * math.pi * 0.7)  # 弯曲

        # 矩形截面 (简化)
        cx_l = x - w
        cx_r = x + w
        cy_f = y + y_offset - d
        cy_b = y + y_offset + d

        pts = TColgp_Array1OfPnt(1, 5)
        pts.SetValue(1, gp_Pnt(cx_l, cy_f, z_pos))
        pts.SetValue(2, gp_Pnt(cx_l, cy_b, z_pos))
        pts.SetValue(3, gp_Pnt(cx_r, cy_b, z_pos))
        pts.SetValue(4, gp_Pnt(cx_r, cy_f, z_pos))
        pts.SetValue(5, gp_Pnt(cx_l, cy_f, z_pos))  # 闭合

        bezier = Geom_BezierCurve(pts)
        edge = BRepBuilderAPI_MakeEdge(bezier).Edge()
        wire = BRepBuilderAPI_MakeWire(edge).Wire()
        loft.AddWire(wire)

    loft.Build()
    return loft.Shape() if loft.IsDone() else None


def make_zoushou(
    x: float, y: float, z: float,
    height: float = 800.0,
    width: float = 400.0,
) -> object | None:
    """创建走兽 (垂脊/戗脊上的小兽).

    用简化的圆锥体模拟。
    """
    from OCP.gp import gp_Pnt, gp_Dir, gp_Ax2
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCone

    try:
        ax = gp_Ax2(gp_Pnt(x, y, z), gp_Dir(0, 0, 1))
        cone = BRepPrimAPI_MakeCone(ax, width / 2, width / 6, height)
        cone.Build()
        return cone.Shape() if cone.IsDone() else None
    except Exception:
        return None


def make_full_wudian_roof(
    cx: float,
    cy: float,
    hall_hw: float,
    hall_hd: float,
    overhang: float,
    z_eave: float,
    z_ridge: float,
    ridge_ratio: float = 0.65,
    n_zoushou: int = 5,
) -> list[tuple[object, tuple[int, int, int]]]:
    """创建完整的庑殿顶 (四面弧形屋面 + 脊线 + 脊饰).

    Returns:
        [(shape, color_rgb), ...] — 所有 OCP 形体 + 颜色
    """
    eave_hw = hall_hw + overhang
    eave_hd = hall_hd + overhang
    ridge_hw = hall_hw * ridge_ratio

    TILE_COLOR = (210, 175, 45)    # 琉璃黄
    RIDGE_COLOR = (195, 165, 55)   # 金色脊
    CHIWEN_COLOR = (160, 140, 60)  # 深金
    ZOUSHOU_COLOR = (180, 160, 70) # 走兽色

    shapes = []

    # 四面弧形屋面板
    panels = make_hip_roof(
        cx, cy, eave_hw, eave_hd, ridge_hw,
        z_eave, z_ridge,
    )
    for shape, name in panels:
        shapes.append((shape, TILE_COLOR))

    # 正脊 (东西向)
    main_ridge = make_ridge_beam(
        (cx - ridge_hw, cy, z_ridge),
        (cx + ridge_hw, cy, z_ridge),
        width=500, height=700,
    )
    if main_ridge:
        shapes.append((main_ridge, RIDGE_COLOR))

    # 垂脊 (从正脊端点到檐角, 4 条)
    corners = [
        (cx - eave_hw, cy - eave_hd, z_eave),
        (cx + eave_hw, cy - eave_hd, z_eave),
        (cx + eave_hw, cy + eave_hd, z_eave),
        (cx - eave_hw, cy + eave_hd, z_eave),
    ]
    ridge_ends = [
        (cx - ridge_hw, cy, z_ridge),
        (cx + ridge_hw, cy, z_ridge),
        (cx + ridge_hw, cy, z_ridge),
        (cx - ridge_hw, cy, z_ridge),
    ]
    for corner, rend in zip(corners, ridge_ends):
        hip = make_ridge_beam(rend, corner, width=350, height=500)
        if hip:
            shapes.append((hip, RIDGE_COLOR))

    # 鸱吻 (正脊两端)
    for rx, facing in [(cx - ridge_hw, "south"), (cx + ridge_hw, "north")]:
        cw = make_chiwen(rx, cy, z_ridge, height=2200, facing=facing)
        if cw:
            shapes.append((cw, CHIWEN_COLOR))

    # 走兽 (每条垂脊上等距排列)
    for corner, rend in zip(corners, ridge_ends):
        for j in range(1, n_zoushou + 1):
            t = j / (n_zoushou + 1)
            zx = rend[0] + (corner[0] - rend[0]) * t
            zy = rend[1] + (corner[1] - rend[1]) * t
            zz = rend[2] + (corner[2] - rend[2]) * t
            beast = make_zoushou(zx, zy, zz + 250, height=600, width=300)
            if beast:
                shapes.append((beast, ZOUSHOU_COLOR))

    return shapes
