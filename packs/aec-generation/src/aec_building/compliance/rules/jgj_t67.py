"""JGJ/T 67-2019 办公建筑设计标准 — 确定性规则检查.

办公建筑特有的设计标准条款。
"""

from __future__ import annotations

from typing import Any

from aec_building.compliance.checker import ComplianceResult, Severity, Violation


def check_jgj_t67(building_info: dict[str, Any], scope: list[str]) -> ComplianceResult:
    """执行 JGJ/T 67-2019 全部适用条款检查."""
    result = ComplianceResult(standard="JGJ/T 67-2019")

    if "accessibility" in scope:
        _check_accessibility(building_info, result)

    if "daylighting" in scope:
        _check_daylighting(building_info, result)

    _check_floor_height(building_info, result)
    _check_corridor_width(building_info, result)

    return result


def _check_accessibility(info: dict, result: ComplianceResult) -> None:
    """§6.4: 无障碍设计.

    办公建筑主要出入口应设置无障碍通道。
    三层及以上办公建筑应设无障碍电梯。
    """
    floors = info.get("floors", 1)
    has_accessible_entrance = info.get("has_accessible_entrance", True)
    has_accessible_elevator = info.get("has_accessible_elevator", None)

    if not has_accessible_entrance:
        result.violations.append(Violation(
            code="JGJ/T 67-2019 §6.4",
            severity=Severity.WARNING,
            description="主要出入口应设置无障碍通道",
            suggestion="在南侧主入口增设无障碍坡道（坡度 ≤ 1:12）",
        ))
    else:
        result.passes.append("accessibility_ramp")

    if floors >= 3 and has_accessible_elevator is False:
        result.violations.append(Violation(
            code="JGJ/T 67-2019 §6.4",
            severity=Severity.WARNING,
            description=f"{floors}层办公建筑应设无障碍电梯",
            suggestion="在核心筒内增设一台无障碍电梯",
        ))


def _check_daylighting(info: dict, result: ComplianceResult) -> None:
    """§5.1: 天然采光.

    办公室窗地面积比 ≥ 1/5。
    """
    window_floor_ratio = info.get("window_floor_ratio", 0)

    if 0 < window_floor_ratio < 0.2:
        result.violations.append(Violation(
            code="JGJ/T 67-2019 §5.1",
            severity=Severity.WARNING,
            description=f"办公室窗地面积比 {window_floor_ratio:.2f} < 1/5",
            suggestion="增大窗户面积或调整办公区域布局",
        ))
    else:
        result.passes.append("daylighting")


def _check_floor_height(info: dict, result: ComplianceResult) -> None:
    """§4.1: 层高要求.

    普通办公室层高不应低于 2.8m（净高不低于 2.6m）。
    """
    floor_height = info.get("floor_height", 3900)  # mm
    # 假设楼板厚 150mm + 吊顶 300mm → 净高 = 层高 - 450
    net_height = floor_height - 450

    if net_height < 2600:
        result.violations.append(Violation(
            code="JGJ/T 67-2019 §4.1",
            severity=Severity.WARNING,
            description=f"办公室净高 {net_height/1000:.2f}m < 2.6m（层高 {floor_height/1000:.1f}m）",
            suggestion="增加层高或减少吊顶厚度",
        ))
    else:
        result.passes.append("floor_height")


def _check_corridor_width(info: dict, result: ComplianceResult) -> None:
    """§4.2: 走道宽度.

    单面办公走道宽度 ≥ 1.3m，双面办公走道宽度 ≥ 1.5m。
    """
    corridor_width = info.get("corridor_width", 0)  # mm
    corridor_type = info.get("corridor_type", "double")

    min_width = 1500 if corridor_type == "double" else 1300

    if 0 < corridor_width < min_width:
        result.violations.append(Violation(
            code="JGJ/T 67-2019 §4.2",
            severity=Severity.WARNING,
            description=(
                f"{'双面' if corridor_type == 'double' else '单面'}办公走道宽 "
                f"{corridor_width/1000:.2f}m < {min_width/1000:.1f}m"
            ),
            suggestion=f"加宽走道至 {min_width/1000:.1f}m 以上",
        ))
    else:
        result.passes.append("corridor_width")
