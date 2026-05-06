"""约束提取器 — 从结构化输入生成约束集.

对应案例 Phase 0 §2.1-2.2：提取显式约束并推断隐含约束。
纯 Python 实现，不依赖 LLM（确定性规则）。
"""

from __future__ import annotations

from aec_building.constraints.schema import (
    ConstraintPriority,
    ConstraintSet,
    ConstraintSource,
    ConstraintType,
    DesignConstraint,
)


def extract_office_building_constraints(
    floors: int,
    area_per_floor: float,
    shape: str,
    structure: str,
    max_span: float,
    floor_height: float = 3900.0,
    has_atrium: bool = False,
    core_position: str = "",
    entrance_position: str = "",
    site_constraints: dict | None = None,
) -> ConstraintSet:
    """从办公楼参数中提取完整约束集.

    对应案例 §2.1（显式约束）+ §2.2（隐含约束）。

    Args:
        floors: 层数。
        area_per_floor: 每层面积 (m²)。
        shape: 平面形状（如 "L", "U", "rectangular"）。
        structure: 结构体系（如 "steel_frame", "concrete"）。
        max_span: 最大柱距 (m)。
        floor_height: 层高 (mm)，默认 3900。
        has_atrium: 是否有中庭。
        core_position: 核心筒位置（如 "north"）。
        entrance_position: 主入口位置（如 "south"）。
        site_constraints: 场地约束字典。

    Returns:
        完整的约束集合。
    """
    cs = ConstraintSet()

    # ── 显式约束 ──

    cs.add(DesignConstraint(
        name="层数",
        constraint_type=ConstraintType.HEIGHT,
        value=floors,
        source=ConstraintSource.EXPLICIT,
        priority=ConstraintPriority.HARD,
    ))

    cs.add(DesignConstraint(
        name="每层面积",
        constraint_type=ConstraintType.AREA,
        value=area_per_floor,
        tolerance=0.05,  # ±5%
        source=ConstraintSource.EXPLICIT,
        priority=ConstraintPriority.SOFT,
    ))

    cs.add(DesignConstraint(
        name="平面形状",
        constraint_type=ConstraintType.SHAPE,
        value=shape,
        source=ConstraintSource.EXPLICIT,
        priority=ConstraintPriority.HARD,
    ))

    cs.add(DesignConstraint(
        name="结构体系",
        constraint_type=ConstraintType.MATERIAL,
        value=structure,
        source=ConstraintSource.EXPLICIT,
        priority=ConstraintPriority.HARD,
    ))

    cs.add(DesignConstraint(
        name="最大柱距",
        constraint_type=ConstraintType.SPAN,
        value=max_span,
        source=ConstraintSource.EXPLICIT,
        priority=ConstraintPriority.HARD,
    ))

    if has_atrium:
        cs.add(DesignConstraint(
            name="中庭",
            constraint_type=ConstraintType.FUNCTION,
            value="atrium_required",
            source=ConstraintSource.EXPLICIT,
            priority=ConstraintPriority.HARD,
        ))

    if core_position:
        cs.add(DesignConstraint(
            name="核心筒位置",
            constraint_type=ConstraintType.POSITION,
            value=core_position,
            source=ConstraintSource.EXPLICIT,
            priority=ConstraintPriority.HARD,
        ))

    if entrance_position:
        cs.add(DesignConstraint(
            name="主入口位置",
            constraint_type=ConstraintType.POSITION,
            value=entrance_position,
            source=ConstraintSource.EXPLICIT,
            priority=ConstraintPriority.SOFT,
        ))

    # ── 隐含约束（Agent 推断，案例 §2.2）──

    total_height = floors * floor_height
    cs.add(DesignConstraint(
        name="建筑总高",
        constraint_type=ConstraintType.HEIGHT,
        value=total_height,
        source=ConstraintSource.INFERRED,
        priority=ConstraintPriority.SOFT,
        rationale=f"层高假设 {floor_height}mm × {floors} 层",
    ))

    # 高度 < 24m → 不属于高层，消防要求相对简单
    if total_height < 24000:
        cs.add(DesignConstraint(
            name="建筑类别",
            constraint_type=ConstraintType.CODE,
            value="multi_story",
            source=ConstraintSource.INFERRED,
            priority=ConstraintPriority.HARD,
            rationale="总高 < 24m，属多层建筑",
        ))

    # 面积 < 2500m² → 单一防火分区
    if area_per_floor < 2500:
        cs.add(DesignConstraint(
            name="防火分区",
            constraint_type=ConstraintType.CODE,
            value="single_compartment",
            source=ConstraintSource.INFERRED,
            priority=ConstraintPriority.HARD,
            rationale=f"单层 {area_per_floor}m² 不超过规范限值",
        ))

    # 疏散楼梯数量推断（GB 50016）
    if floors >= 2:
        min_stairs = 2 if area_per_floor > 200 else 1
        cs.add(DesignConstraint(
            name="最少疏散楼梯数",
            constraint_type=ConstraintType.CODE,
            value=min_stairs,
            source=ConstraintSource.CODE_REQUIRED,
            priority=ConstraintPriority.HARD,
            rationale="GB 50016-2014 §5.5.17: 多层公共建筑应设 ≥2 部疏散楼梯",
        ))

    # 场地约束（如有）
    if site_constraints:
        for name, value in site_constraints.items():
            cs.add(DesignConstraint(
                name=name,
                constraint_type=ConstraintType.SITE,
                value=value,
                source=ConstraintSource.EXPLICIT,
                priority=ConstraintPriority.HARD,
            ))
    else:
        cs.add(DesignConstraint(
            name="场地信息",
            constraint_type=ConstraintType.SITE,
            value="unknown",
            source=ConstraintSource.INFERRED,
            priority=ConstraintPriority.SOFT,
            rationale="用户未提供场地信息，推进但标记不确定性",
        ))

    return cs
