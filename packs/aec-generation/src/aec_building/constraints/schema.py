"""设计约束数据模型.

对应案例 Phase 0（意图理解与约束提取）：
将用户输入解析为结构化约束，分为显式约束和隐含约束。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ConstraintType(Enum):
    """约束类型."""

    AREA = "area"                # 面积约束
    SHAPE = "shape"              # 形状约束
    HEIGHT = "height"            # 高度约束
    SPAN = "span"                # 跨距约束
    POSITION = "position"        # 位置约束
    MATERIAL = "material"        # 材料约束
    FUNCTION = "function"        # 功能约束（中庭、入口等）
    SITE = "site"                # 场地约束
    CODE = "code"                # 规范约束


class ConstraintSource(Enum):
    """约束来源."""

    EXPLICIT = "explicit"        # 用户明确提出
    INFERRED = "inferred"        # Agent 推断补充
    CODE_REQUIRED = "code"       # 规范强制要求


class ConstraintPriority(Enum):
    """约束优先级."""

    HARD = "hard"                # 硬约束，必须满足
    SOFT = "soft"                # 软约束，允许 ±5% 容差
    PREFERENCE = "preference"    # 偏好，尽量满足


@dataclass
class DesignConstraint:
    """单条设计约束.

    Attributes:
        name: 约束名称（如 "每层面积"）。
        constraint_type: 约束类型。
        value: 约束值（数值、字符串、或复合结构）。
        tolerance: 容差（仅对数值约束有效），如 0.05 表示 ±5%。
        source: 约束来源。
        priority: 优先级。
        rationale: 推理依据（隐含约束需要说明）。
    """

    name: str
    constraint_type: ConstraintType
    value: object
    tolerance: float = 0.0
    source: ConstraintSource = ConstraintSource.EXPLICIT
    priority: ConstraintPriority = ConstraintPriority.HARD
    rationale: str = ""

    def check_numeric(self, actual: float) -> bool:
        """检查数值约束是否满足（含容差）."""
        if not isinstance(self.value, (int, float)):
            return False
        target = float(self.value)
        if self.tolerance > 0:
            return abs(actual - target) / target <= self.tolerance
        return actual == target


@dataclass
class ConstraintSet:
    """设计约束集合.

    对应案例 Phase 0 的完整约束表：
    管理显式约束、隐含约束，提供冲突检测。
    """

    constraints: list[DesignConstraint] = field(default_factory=list)

    def add(self, constraint: DesignConstraint) -> None:
        self.constraints.append(constraint)

    def get_by_type(self, ctype: ConstraintType) -> list[DesignConstraint]:
        return [c for c in self.constraints if c.constraint_type == ctype]

    def get_explicit(self) -> list[DesignConstraint]:
        return [c for c in self.constraints if c.source == ConstraintSource.EXPLICIT]

    def get_inferred(self) -> list[DesignConstraint]:
        return [c for c in self.constraints if c.source == ConstraintSource.INFERRED]

    def get_hard(self) -> list[DesignConstraint]:
        return [c for c in self.constraints if c.priority == ConstraintPriority.HARD]

    def summary(self) -> dict:
        """约束集摘要，用于 Agent 上下文."""
        return {
            "total": len(self.constraints),
            "explicit": len(self.get_explicit()),
            "inferred": len(self.get_inferred()),
            "hard": len(self.get_hard()),
            "types": list({c.constraint_type.value for c in self.constraints}),
        }
