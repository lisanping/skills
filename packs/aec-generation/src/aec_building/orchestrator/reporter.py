"""交付报告生成器.

对应案例 Tool Call 20 和案例 4.6：
交付清单 > 单纯文件。将过程知识显性化给用户。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DeliveryItem:
    """交付物条目."""

    filename: str
    description: str
    format: str


@dataclass
class ConstraintStatus:
    """约束满足状态."""

    name: str
    satisfied: bool
    note: str = ""


@dataclass
class DeliveryReport:
    """完整交付报告.

    对应案例 Tool Call 20 的交付报告结构。
    """

    deliverables: list[DeliveryItem] = field(default_factory=list)
    key_parameters: dict[str, Any] = field(default_factory=dict)
    constraints_status: list[ConstraintStatus] = field(default_factory=list)
    open_issues: list[str] = field(default_factory=list)
    editability_notes: list[str] = field(default_factory=list)


def generate_report(
    building_summary: dict,
    compliance_result: dict | None = None,
    exported_files: list[str] | None = None,
) -> DeliveryReport:
    """生成交付报告.

    Args:
        building_summary: Building.summary() 输出。
        compliance_result: 合规检查结果。
        exported_files: 已导出的文件列表。
    """
    report = DeliveryReport()

    # 交付物
    for f in (exported_files or []):
        ext = f.rsplit(".", 1)[-1] if "." in f else "unknown"
        desc_map = {
            "step": "BREP 几何模型（可导入各类 CAD 软件）",
            "ifc": "开放标准 BIM 模型（IFC4）",
            "stl": "三角化网格（用于可视化/3D 打印）",
        }
        report.deliverables.append(DeliveryItem(
            filename=f,
            description=desc_map.get(ext, f"{ext} 格式文件"),
            format=ext,
        ))

    # 关键参数
    report.key_parameters = {
        "总楼板数": building_summary.get("slab_count", 0),
        "柱子数": building_summary.get("column_count", 0),
        "墙体数": building_summary.get("wall_count", 0),
        "轴网X": building_summary.get("grid_x", []),
        "轴网Y": building_summary.get("grid_y", []),
        "标高": building_summary.get("levels", []),
    }

    # 已知未决事项
    report.open_issues = [
        "场地红线、日照间距未知 — 建议补充场地信息",
        "MEP 系统未建模 — 需机电工程师深化",
        "幕墙分格为初步方案 — 建议立面设计师优化",
    ]

    # 可编辑性说明
    report.editability_notes = [
        "所有尺寸基于轴网参照，调整轴网间距会联动更新：楼板边界、柱位、中庭开洞、外墙",
        "以下内容需手动调整：楼梯参数、幕墙分格",
    ]

    return report


def format_report_markdown(report: DeliveryReport) -> str:
    """将交付报告格式化为 Markdown 文本."""
    lines = ["# 交付报告\n"]

    lines.append("## 交付物清单\n")
    for d in report.deliverables:
        lines.append(f"- `{d.filename}` — {d.description}")

    lines.append("\n## 关键参数\n")
    lines.append("| 参数 | 值 |")
    lines.append("|------|-----|")
    for k, v in report.key_parameters.items():
        lines.append(f"| {k} | {v} |")

    if report.constraints_status:
        lines.append("\n## 约束满足状态\n")
        for cs in report.constraints_status:
            mark = "✓" if cs.satisfied else "✗"
            lines.append(f"- {mark} {cs.name}" + (f" — {cs.note}" if cs.note else ""))

    lines.append("\n## 未决事项\n")
    for issue in report.open_issues:
        lines.append(f"- ⚠ {issue}")

    lines.append("\n## 可编辑性说明\n")
    for note in report.editability_notes:
        lines.append(f"- {note}")

    return "\n".join(lines)
