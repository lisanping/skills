"""曲面壳体几何工具 — 基于 OCP (OpenCascade) 的光滑放样曲面.

用于生成悉尼歌剧院式的帆形/壳体屋顶。
使用 BRepOffsetAPI_ThruSections 在截面轮廓之间做光滑放样 (loft)。

真实悉尼歌剧院: 壳体是从同一球面 (R≈75.2m) 切出的球面三角形。
所有壳体朝同一方向展开 (朝海港/南方), 像嵌套的橘子瓣。
每组有 3-4 个壳, 从前到后递缩。

需要: cadquery (提供 OCP 绑定)
"""

from __future__ import annotations

import math
from typing import Sequence


def make_opera_shell(
    cx: float,
    cy: float,
    base_width: float,
    rise_height: float,
    depth: float,
    z_base: float = 0.0,
    n_sections: int = 24,
) -> object:
    """创建单个歌剧院壳体 — 从底边弧线升起到脊线尖点.

    几何: 底边是宽弧 (在 cy 处, 沿 X 方向),
    向北(+Y)升起并收窄, 顶端汇聚到脊线尖点。
    截面是半圆弧, 从底部(大弧)渐变到顶部(小弧→点)。

    这模拟了真实歌剧院壳体: 从观众视角 (南面) 看到的
    是壳体的张开口, 壳体向后(北)升起弯曲。

    Args:
        cx, cy: 壳体底边中心 (mm)
        base_width: 底边全宽 (mm, 沿 X)
        rise_height: 脊线最高点相对 z_base (mm)
        depth: 壳体纵深 (mm, 从底边到脊线顶点, 沿 Y)
        z_base: 底边标高 (mm)
        n_sections: 截面数

    Returns:
        OCP TopoDS_Shape, 或 None
    """
    from OCP.gp import gp_Pnt
    from OCP.BRepBuilderAPI import (
        BRepBuilderAPI_MakeEdge,
        BRepBuilderAPI_MakeWire,
        BRepBuilderAPI_MakeVertex,
    )
    from OCP.BRepOffsetAPI import BRepOffsetAPI_ThruSections
    from OCP.Geom import Geom_BezierCurve
    from OCP.TColgp import TColgp_Array1OfPnt

    loft = BRepOffsetAPI_ThruSections(True, False)
    added = 0

    for i in range(n_sections + 1):
        t = i / n_sections  # 0 = 底边, 1 = 脊线顶

        # 宽度: cos 衰减 (底部宽, 顶部收拢到 0)
        w = base_width * 0.5 * max(math.cos(t * math.pi * 0.5) ** 0.8, 0.0)

        if w < 60:
            break

        # Y 位置: 从底边向北移动
        y_pos = cy + depth * t

        # Z 位置: 正弦上升曲线
        z = z_base + rise_height * math.sin(t * math.pi * 0.5)

        # 截面弧高: 宽度的 50-70%, 顶部弧度更圆
        arch_ratio = 0.5 + 0.25 * t
        arch_h = w * arch_ratio

        # 7 点 Bezier 半圆弧截面
        pts = TColgp_Array1OfPnt(1, 7)
        pts.SetValue(1, gp_Pnt(cx - w, y_pos, z))
        pts.SetValue(2, gp_Pnt(cx - w * 0.66, y_pos, z + arch_h * 0.6))
        pts.SetValue(3, gp_Pnt(cx - w * 0.25, y_pos, z + arch_h * 0.95))
        pts.SetValue(4, gp_Pnt(cx, y_pos, z + arch_h))
        pts.SetValue(5, gp_Pnt(cx + w * 0.25, y_pos, z + arch_h * 0.95))
        pts.SetValue(6, gp_Pnt(cx + w * 0.66, y_pos, z + arch_h * 0.6))
        pts.SetValue(7, gp_Pnt(cx + w, y_pos, z))

        bezier = Geom_BezierCurve(pts)
        arc_edge = BRepBuilderAPI_MakeEdge(bezier).Edge()
        base_edge = BRepBuilderAPI_MakeEdge(
            gp_Pnt(cx + w, y_pos, z), gp_Pnt(cx - w, y_pos, z)
        ).Edge()

        wire = BRepBuilderAPI_MakeWire()
        wire.Add(arc_edge)
        wire.Add(base_edge)
        loft.AddWire(wire.Wire())
        added += 1

    if added < 3:
        return None

    # 脊线顶点
    tip_y = cy + depth * 0.97
    tip_z = z_base + rise_height * 0.99
    tip = BRepBuilderAPI_MakeVertex(gp_Pnt(cx, tip_y, tip_z)).Vertex()
    loft.AddVertex(tip)

    loft.Build()
    return loft.Shape() if loft.IsDone() else None


def make_opera_shell_group(
    cx: float,
    cy: float,
    base_width: float,
    rise_height: float,
    depth: float,
    z_base: float = 0.0,
    n_shells: int = 3,
    step_back: float = 6000.0,
    scale_decay: float = 0.78,
) -> list[object]:
    """创建一组嵌套壳体 (前大后小, 都朝同一方向).

    模拟悉尼歌剧院每一侧的壳体组:
    最前面的壳最大, 后面每个递缩并向后退。

    Args:
        cx, cy: 第一个(最前)壳的底边中心
        base_width: 最前壳底宽
        rise_height: 最前壳最高点
        depth: 最前壳纵深
        z_base: 起始标高
        n_shells: 壳体数量
        step_back: 每个壳向后退的距离 (mm)
        scale_decay: 每个壳的缩放系数

    Returns:
        list of TopoDS_Shape
    """
    shapes = []
    for i in range(n_shells):
        s = scale_decay ** i
        shell = make_opera_shell(
            cx=cx,
            cy=cy + step_back * i,
            base_width=base_width * s,
            rise_height=rise_height * s,
            depth=depth * s,
            z_base=z_base,
        )
        if shell:
            shapes.append(shell)
    return shapes


def ocp_shape_to_trimesh(shape: object, tolerance: float = 500.0, color_rgb: tuple = (200, 200, 200)):
    """将 OCP TopoDS_Shape 转换为 trimesh.Trimesh 对象.

    使用 OCP 内置三角化器, 提取顶点和面索引, 构建 trimesh 网格。

    Args:
        shape: OCP TopoDS_Shape
        tolerance: 三角化精度 (mm), 越小越精细
        color_rgb: (R, G, B) 0-255 颜色

    Returns:
        trimesh.Trimesh 对象, 或 None
    """
    import numpy as np
    import trimesh
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopoDS import TopoDS
    from OCP.TopLoc import TopLoc_Location
    from OCP.BRep import BRep_Tool

    # 三角化
    mesh_algo = BRepMesh_IncrementalMesh(shape, tolerance)
    mesh_algo.Perform()

    all_verts = []
    all_faces = []
    vert_offset = 0

    explorer = TopExp_Explorer(shape, TopAbs_FACE)
    while explorer.More():
        face = TopoDS.Face_s(explorer.Current())
        loc = TopLoc_Location()
        tri = BRep_Tool.Triangulation_s(face, loc)

        if tri is None:
            explorer.Next()
            continue

        n_verts = tri.NbNodes()
        n_tris = tri.NbTriangles()

        # 提取顶点
        trsf = loc.Transformation()
        for i in range(1, n_verts + 1):
            p = tri.Node(i)
            p.Transform(trsf)
            all_verts.append([p.X(), p.Y(), p.Z()])

        # 提取三角面
        for i in range(1, n_tris + 1):
            t = tri.Triangle(i)
            i1, i2, i3 = t.Get()
            all_faces.append([
                i1 - 1 + vert_offset,
                i2 - 1 + vert_offset,
                i3 - 1 + vert_offset,
            ])

        vert_offset += n_verts
        explorer.Next()

    if not all_verts:
        return None

    vertices = np.array(all_verts, dtype=np.float64)
    faces = np.array(all_faces, dtype=np.int32)

    mesh = trimesh.Trimesh(vertices=vertices, faces=faces)

    # 设置颜色
    r, g, b = color_rgb
    face_colors = np.tile([r, g, b, 255], (len(faces), 1)).astype(np.uint8)
    mesh.visual = trimesh.visual.ColorVisuals(mesh=mesh, face_colors=face_colors)

    return mesh
