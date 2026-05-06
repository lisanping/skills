"""GB 50016-2014 建筑设计防火规范 — 确定性规则检查.

对应案例 Tool Call 16 发现的违规：
- §5.5.17: 三层办公建筑应设置两部疏散楼梯
- §6.2.2: L 形建筑折角处窗间距要求

每条规范条款实现为一个独立纯函数。
"""

from __future__ import annotations

from typing import Any

from aec_building.compliance.checker import ComplianceResult, Severity, Violation


def check_gb50016(building_info: dict[str, Any], scope: list[str]) -> ComplianceResult:
    """执行 GB 50016-2014 全部适用条款检查."""
    result = ComplianceResult(standard="GB 50016-2014")

    if "fire_escape" in scope:
        _check_egress_stairs(building_info, result)
        _check_egress_distance(building_info, result)
        _check_smoke_proof_stairwell(building_info, result)
        _check_egress_distance_geometry(building_info, result)

    if "fire_compartment" in scope:
        _check_fire_compartment_area(building_info, result)

    if "exit_width" in scope:
        _check_exit_width(building_info, result)

    if "l_shape_corner" in scope or "fire_escape" in scope:
        _check_l_shape_corner_distance(building_info, result)

    return result


def _check_egress_stairs(info: dict, result: ComplianceResult) -> None:
    """§5.5.17: 疏散楼梯数量检查.

    多层公共建筑（含办公），除符合特定豁免条件外，
    每个防火分区应设置不少于 2 部疏散楼梯。
    """
    floors = info.get("floors", 1)
    stair_count = info.get("stair_count", 0)
    area_per_floor = info.get("area_per_floor", 0)

    if floors <= 1:
        result.passes.append("egress_stairs_single_story")
        return

    # 豁免条件：2-3 层，单层面积 ≤ 200m²，人数 ≤ 50
    # 普通办公楼不满足豁免
    min_required = 2

    if stair_count < min_required:
        # 推算补设楼梯的建议位置：优先放在建筑远端
        fix_action = {
            "tool": "create_staircase",
            "params": {
                "base_level": "F1",
                "top_level": f"F{floors}",
                "stair_type": "u_turn",
            },
            "description": f"在建筑另一端补设{min_required - stair_count}部疏散楼梯",
        }
        result.violations.append(Violation(
            code="GB 50016-2014 §5.5.17",
            severity=Severity.WARNING,
            description=f"{floors}层办公建筑应设置{min_required}部疏散楼梯，当前仅{stair_count}部",
            location=f"F2-F{floors}",
            suggestion=f"补设{min_required - stair_count}部疏散楼梯",
            fix_action=fix_action,
        ))
    else:
        result.passes.append("egress_stairs")


def _check_egress_distance(info: dict, result: ComplianceResult) -> None:
    """§5.5.17-4: 疏散距离检查.

    办公建筑直通疏散走道的房间门至最近安全出口距离：
    - 位于两个出口之间: ≤ 40m（设自动喷淋 ≤ 50m）
    - 位于袋形走道: ≤ 22m（设自动喷淋 ≤ 27.5m）
    """
    max_egress_distance = info.get("max_egress_distance", 0)
    has_sprinkler = info.get("has_sprinkler", False)

    limit = 50000 if has_sprinkler else 40000  # mm

    if max_egress_distance > 0 and max_egress_distance > limit:
        result.violations.append(Violation(
            code="GB 50016-2014 §5.5.17",
            severity=Severity.ERROR,
            description=f"最大疏散距离 {max_egress_distance/1000:.1f}m 超过限值 {limit/1000:.1f}m",
            suggestion="增加安全出口或调整走道布局",
        ))
    else:
        result.passes.append("egress_distance")


def _check_fire_compartment_area(info: dict, result: ComplianceResult) -> None:
    """§5.3: 防火分区面积检查.

    多层办公建筑（非高层），防火分区面积限值：
    - 无自动灭火: 2500 m²
    - 有自动喷淋: 5000 m²
    """
    area_per_floor = info.get("area_per_floor", 0)
    has_sprinkler = info.get("has_sprinkler", False)

    limit = 5000 if has_sprinkler else 2500  # m²

    if area_per_floor > limit:
        result.violations.append(Violation(
            code="GB 50016-2014 §5.3",
            severity=Severity.ERROR,
            description=f"单层面积 {area_per_floor}m² 超过防火分区限值 {limit}m²",
            suggestion="增设防火墙分隔为多个防火分区，或增设自动喷淋系统",
        ))
    else:
        result.passes.append("fire_compartment_area")


def _check_exit_width(info: dict, result: ComplianceResult) -> None:
    """§5.5.18: 安全出口净宽度.

    办公建筑每层安全出口最小净宽:
    按百人疏散宽度 ≥ 1.0m/百人 计算。
    """
    area_per_floor = info.get("area_per_floor", 0)
    total_exit_width = info.get("total_exit_width", 0)  # mm

    # 办公建筑人员密度约 1人/8m²
    occupancy = area_per_floor / 8
    required_width = occupancy / 100 * 1000  # mm（百人 1m）

    if total_exit_width > 0 and total_exit_width < required_width:
        result.violations.append(Violation(
            code="GB 50016-2014 §5.5.18",
            severity=Severity.WARNING,
            description=(
                f"安全出口总净宽 {total_exit_width/1000:.1f}m "
                f"不足，需 ≥ {required_width/1000:.1f}m"
            ),
            suggestion="加宽安全出口或增设出口",
        ))
    else:
        result.passes.append("exit_width")


def _check_l_shape_corner_distance(info: dict, result: ComplianceResult) -> None:
    """§6.2.2: L 形建筑折角处外墙间距.

    两座建筑的外墙为非防火墙，当相邻较高一面外墙的耐火极限
    不低于规定值时，其防火间距可不限。但 L 形、U 形建筑的
    两翼外墙间最近距离 < 4m 时，窗间距应 ≥ 4m。
    """
    shape = info.get("shape", "")
    corner_min_distance = info.get("corner_min_distance", 0)  # mm

    if shape in ("L", "U") and 0 < corner_min_distance < 4000:
        result.violations.append(Violation(
            code="GB 50016-2014 §6.2.2",
            severity=Severity.WARNING,
            description=(
                f"L形建筑内折角处两翼外墙间最近距离 {corner_min_distance/1000:.1f}m < 4m，"
                "窗间距应 ≥ 4m"
            ),
            location="L-shape corner",
            suggestion="调整折角处窗户位置，确保窗间距 ≥ 4m，或使用防火窗",
            fix_action={
                "tool": "modify_element",
                "params": {},
                "description": "调整 L 形折角处窗户位置，确保窗间距 ≥ 4m",
            },
        ))
    else:
        result.passes.append("l_shape_corner")


def _check_smoke_proof_stairwell(info: dict, result: ComplianceResult) -> None:
    """§5.5.27: 防烟楼梯间要求.

    建筑高度 > 33m 的住宅 或 > 32m 的公共建筑，
    疏散楼梯应采用防烟楼梯间。

    建筑高度 ≤ 33m（多层办公）可采用封闭楼梯间。
    """
    building_height = info.get("building_height", 0)  # mm
    has_smoke_proof_stairs = info.get("has_smoke_proof_stairs", False)

    if building_height <= 0:
        result.passes.append("smoke_proof_stairwell")
        return

    limit = 32000  # 32m，公共建筑

    if building_height > limit and not has_smoke_proof_stairs:
        result.violations.append(Violation(
            code="GB 50016-2014 §5.5.27",
            severity=Severity.ERROR,
            description=(
                f"建筑高度 {building_height / 1000:.1f}m > 32m，"
                "疏散楼梯应采用防烟楼梯间"
            ),
            location="全楼",
            suggestion="将疏散楼梯改为防烟楼梯间（设前室或合用前室）",
        ))
    else:
        result.passes.append("smoke_proof_stairwell")


def _check_egress_distance_geometry(info: dict, result: ComplianceResult) -> None:
    """§5.5.17: 基于几何的疏散距离计算.

    如果提供了楼梯位置和楼板几何，计算最远点到最近楼梯的距离。
    办公建筑限值：
    - 两个方向疏散: ≤ 40m（有喷淋 50m）
    - 袋形走道: ≤ 22m（有喷淋 27.5m）
    """
    stair_positions = info.get("stair_positions", [])  # [(x, y), ...]
    floor_boundary = info.get("floor_boundary", [])     # [(x, y), ...]
    has_sprinkler = info.get("has_sprinkler", False)

    if not stair_positions or not floor_boundary:
        # 无几何信息则跳过
        return

    import math

    # 采样楼板边界上的点和内部网格点
    sample_points = list(floor_boundary)

    # 在边界包围盒内按 2m 网格采样
    xs = [p[0] for p in floor_boundary]
    ys = [p[1] for p in floor_boundary]
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)

    step = 2000  # 2m 采样间距
    for x in range(int(x_min), int(x_max), step):
        for y in range(int(y_min), int(y_max), step):
            sample_points.append((x, y))

    # 计算每个采样点到最近楼梯的距离
    max_distance = 0.0
    for px, py in sample_points:
        min_dist_to_stair = float("inf")
        for sx, sy in stair_positions:
            dist = math.sqrt((px - sx) ** 2 + (py - sy) ** 2)
            min_dist_to_stair = min(min_dist_to_stair, dist)
        max_distance = max(max_distance, min_dist_to_stair)

    limit = 50000 if has_sprinkler else 40000  # mm

    if max_distance > limit:
        result.violations.append(Violation(
            code="GB 50016-2014 §5.5.17",
            severity=Severity.WARNING,
            description=(
                f"最远疏散距离 {max_distance / 1000:.1f}m "
                f"超过限值 {limit / 1000:.1f}m（基于几何计算）"
            ),
            location="楼板最远点",
            suggestion="增加安全出口或调整楼梯位置",
        ))
    else:
        result.passes.append("egress_distance_geometry")
