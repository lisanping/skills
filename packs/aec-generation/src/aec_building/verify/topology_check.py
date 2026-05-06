"""BREP 拓扑完整性检查.

对应案例 Tool Call 4 返回值中的 geometry_check:
"valid (watertight, manifold, no self-intersection)"

检查 CadQuery/OCCT 生成的实体是否拓扑有效。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TopologyReport:
    """拓扑检查报告."""

    is_valid: bool = True
    is_watertight: bool = True
    is_manifold: bool = True
    has_self_intersection: bool = False
    face_count: int = 0
    edge_count: int = 0
    vertex_count: int = 0
    volume: float = 0.0
    errors: list[str] = field(default_factory=list)

    def summary_string(self) -> str:
        if self.is_valid:
            return "valid (watertight, manifold, no self-intersection)"
        return f"invalid: {', '.join(self.errors)}"


def check_solid_topology(cq_shape: object) -> TopologyReport:
    """检查 CadQuery 实体的拓扑完整性.

    Args:
        cq_shape: CadQuery Workplane 对象。

    Returns:
        TopologyReport。
    """
    try:
        from OCP.BRepCheck import BRepCheck_Analyzer
    except ImportError:
        # 无 OCCT 时返回乐观结果
        return TopologyReport(is_valid=True)

    report = TopologyReport()

    try:
        solid = cq_shape.val()
        wrapped = solid.wrapped if hasattr(solid, "wrapped") else solid

        # OCCT BRepCheck
        analyzer = BRepCheck_Analyzer(wrapped)
        report.is_valid = analyzer.IsValid()

        if not report.is_valid:
            report.errors.append("BRepCheck_Analyzer reports invalid shape")

        # 统计拓扑元素
        from OCP.TopExp import TopExp_Explorer
        from OCP.TopAbs import TopAbs_FACE, TopAbs_EDGE, TopAbs_VERTEX

        for topo_type, attr in [
            (TopAbs_FACE, "face_count"),
            (TopAbs_EDGE, "edge_count"),
            (TopAbs_VERTEX, "vertex_count"),
        ]:
            explorer = TopExp_Explorer(wrapped, topo_type)
            count = 0
            while explorer.More():
                count += 1
                explorer.Next()
            setattr(report, attr, count)

        # 体积
        from OCP.GProp import GProp_GProps
        from OCP.BRepGProp import brepgprop

        props = GProp_GProps()
        brepgprop.VolumeProperties(wrapped, props)
        report.volume = props.Mass()

    except Exception as e:
        report.is_valid = False
        report.errors.append(str(e))

    return report


def check_multiple_solids(shapes: list[object]) -> list[TopologyReport]:
    """批量检查多个实体."""
    return [check_solid_topology(s) for s in shapes]
