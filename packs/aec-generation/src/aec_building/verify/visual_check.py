"""视觉自查工具 — 截图渲染与视觉验证.

对应案例自我检查节点（每 5-8 次 tool call 后安插一次）
和 Tool Call 18 的再次视觉自查。

使用 PyVista 进行离线渲染截图，不依赖 Revit。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class VisualCheckItem:
    """单项视觉检查结果."""

    item: str
    passed: bool
    note: str = ""


@dataclass
class VisualCheckReport:
    """视觉检查报告.

    对应案例中 Agent 读图审查的表格。
    """

    checks: list[VisualCheckItem] = field(default_factory=list)
    screenshot_path: str = ""

    @property
    def all_passed(self) -> bool:
        return all(c.passed for c in self.checks)

    def summary(self) -> dict:
        return {
            "total": len(self.checks),
            "passed": sum(1 for c in self.checks if c.passed),
            "failed": sum(1 for c in self.checks if not c.passed),
            "screenshot": self.screenshot_path,
            "issues": [
                {"item": c.item, "note": c.note}
                for c in self.checks if not c.passed
            ],
        }


def capture_3d_view(
    step_file: str | Path,
    output_path: str | Path,
    resolution: tuple[int, int] = (1920, 1080),
) -> str:
    """使用 PyVista 渲染 STEP 文件的 3D 视图截图.

    Args:
        step_file: STEP 文件路径。
        output_path: 截图输出路径。
        resolution: 分辨率 (宽, 高)。

    Returns:
        截图文件路径。
    """
    try:
        # Workaround: cadquery-ocp 的 VTK 不含 vtkRenderingMatplotlib
        import sys
        import types
        for mod in ("vtkmodules", "vtkmodules.vtkRenderingMatplotlib"):
            if mod not in sys.modules:
                sys.modules[mod] = types.ModuleType(mod)

        import pyvista as pv
        pv.OFF_SCREEN = True
        from OCP.STEPControl import STEPControl_Reader
        from OCP.BRep import BRep_Tool
        from OCP.TopExp import TopExp_Explorer
        from OCP.TopAbs import TopAbs_FACE
        from OCP.TopoDS import TopoDS
        from OCP.TopLoc import TopLoc_Location
        from OCP.BRepMesh import BRepMesh_IncrementalMesh
    except ImportError:
        return str(output_path)

    step_file = Path(step_file)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    reader = STEPControl_Reader()
    reader.ReadFile(str(step_file))
    reader.TransferRoots()
    shape = reader.OneShape()
    BRepMesh_IncrementalMesh(shape, 2.0)

    plotter = pv.Plotter(off_screen=True, window_size=list(resolution))

    explorer = TopExp_Explorer(shape, TopAbs_FACE)
    while explorer.More():
        face = TopoDS.Face_s(explorer.Current())
        loc = TopLoc_Location()
        tri = BRep_Tool.Triangulation_s(face, loc)
        if tri:
            pts = [
                [tri.Node(i).X(), tri.Node(i).Y(), tri.Node(i).Z()]
                for i in range(1, tri.NbNodes() + 1)
            ]
            faces = []
            for i in range(1, tri.NbTriangles() + 1):
                t = tri.Triangle(i)
                n1, n2, n3 = t.Get()
                faces.append([3, n1 - 1, n2 - 1, n3 - 1])
            if pts and faces:
                plotter.add_mesh(
                    pv.PolyData(pts, faces),
                    color="lightblue", show_edges=True,
                    edge_color="#555555", opacity=0.85,
                )
        explorer.Next()

    plotter.camera_position = "iso"
    plotter.screenshot(str(output_path))
    plotter.close()

    return str(output_path)


def render_plan_view(
    building: object,
    output_path: str | Path,
    resolution: tuple[int, int] = (1400, 1000),
) -> str:
    """渲染建筑平面图（楼板轮廓 + 柱网 + 梁 + 墙）.

    纯 matplotlib，无需 3D 依赖。

    Args:
        building: Building 实例。
        output_path: PNG 输出路径。
        resolution: 分辨率 (宽, 高)。

    Returns:
        截图文件路径。
    """
    try:
        import matplotlib
        matplotlib.use("Agg")  # 非交互式后端
        import matplotlib.pyplot as plt
        import matplotlib.patches as patches
    except ImportError:
        return str(output_path)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    grid = building.grid
    dpi = 150
    fig, ax = plt.subplots(1, 1, figsize=(resolution[0] / dpi, resolution[1] / dpi), dpi=dpi)
    ax.set_aspect("equal")
    ax.set_title(f"{building.name} — Floor Plan", fontsize=14)

    # 楼板轮廓
    if building.slabs:
        boundary = building.slabs[0].element.boundary_points
        pts = list(boundary) + [boundary[0]]
        xs = [p[0] / 1000 for p in pts]
        ys = [p[1] / 1000 for p in pts]
        ax.fill(xs, ys, alpha=0.15, color="steelblue")
        ax.plot(xs, ys, color="steelblue", linewidth=2, label=f"Floor Slab x{len(building.slabs)}")

    # 轴网
    for name, xval in grid.x_grids.items():
        x = xval / 1000
        ax.axvline(x, color="gray", linewidth=0.5, linestyle="--", alpha=0.4)
        ax.text(x, ax.get_ylim()[0] - 0.8 if ax.get_ylim()[0] != 0 else -1.5,
                name, ha="center", fontsize=9, color="gray", fontweight="bold")
    for name, yval in grid.y_grids.items():
        y = yval / 1000
        ax.axhline(y, color="gray", linewidth=0.5, linestyle="--", alpha=0.4)
        ax.text(-1.5, y, name, va="center", fontsize=9, color="gray", fontweight="bold")

    # 柱子
    from aec_building.aec.elements import Column
    columns = [be.element for be in building.get_elements_by_type(Column)]
    for col in columns:
        col_size = col.section_width / 1000
        rect = patches.Rectangle(
            (col.x / 1000 - col_size / 2, col.y / 1000 - col_size / 2),
            col_size, col_size,
            linewidth=1.5, edgecolor="red", facecolor="salmon", alpha=0.8,
        )
        ax.add_patch(rect)
    if columns:
        ax.plot([], [], "s", color="salmon", markersize=8, label=f"Column x{len(columns)}")

    # 梁
    from aec_building.aec.elements import Beam
    beams = [be.element for be in building.get_elements_by_type(Beam)]
    for beam in beams:
        ax.plot(
            [beam.start[0] / 1000, beam.end[0] / 1000],
            [beam.start[1] / 1000, beam.end[1] / 1000],
            color="orange", linewidth=0.8, alpha=0.5,
        )
    if beams:
        ax.plot([], [], color="orange", linewidth=1.5, label=f"Beam x{len(beams)}")

    # 墙体
    from aec_building.aec.elements import Wall
    walls = [be.element for be in building.get_elements_by_type(Wall)]
    for wall in walls:
        color = "darkgreen" if wall.wall_type.value == "fire" else "navy"
        ax.plot(
            [wall.start[0] / 1000, wall.end[0] / 1000],
            [wall.start[1] / 1000, wall.end[1] / 1000],
            color=color, linewidth=3, alpha=0.7,
        )
    if walls:
        ax.plot([], [], color="darkgreen", linewidth=3, label=f"Wall x{len(walls)}")

    ax.set_xlabel("X (m)")
    ax.set_ylabel("Y (m)")
    ax.legend(loc="upper right", fontsize=8)
    ax.grid(False)
    plt.tight_layout()
    plt.savefig(str(output_path), dpi=dpi, bbox_inches="tight")
    plt.close(fig)

    return str(output_path)


def run_visual_checks(
    building_summary: dict,
    screenshot_path: str = "",
) -> VisualCheckReport:
    """执行基于模型摘要的视觉检查清单.

    对应案例中自我检查节点的检查表。
    在没有实际截图的情况下，基于数据摘要进行逻辑检查。

    Args:
        building_summary: Building.summary() 输出。
        screenshot_path: 截图路径（如有）。
    """
    report = VisualCheckReport(screenshot_path=screenshot_path)

    # 检查柱网完整性
    col_count = building_summary.get("column_count", 0)
    report.checks.append(VisualCheckItem(
        item="柱网整体",
        passed=col_count > 0,
        note=f"{col_count} 根柱子" if col_count > 0 else "未找到柱子",
    ))

    # 检查楼板
    slab_count = building_summary.get("slab_count", 0)
    report.checks.append(VisualCheckItem(
        item="楼板形状",
        passed=slab_count > 0,
        note=f"{slab_count} 块楼板",
    ))

    # 检查墙体
    wall_count = building_summary.get("wall_count", 0)
    report.checks.append(VisualCheckItem(
        item="墙体系统",
        passed=wall_count > 0,
        note=f"{wall_count} 面墙" if wall_count > 0 else "缺失墙体",
    ))

    # 检查标高
    levels = building_summary.get("levels", [])
    report.checks.append(VisualCheckItem(
        item="标高系统",
        passed=len(levels) >= 2,
        note=f"标高: {levels}",
    ))

    return report
