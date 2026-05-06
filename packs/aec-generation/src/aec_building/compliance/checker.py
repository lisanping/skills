"""合规检查引擎 — 对建筑模型执行确定性规范检查.

对应案例 Tool Call 16（"最有价值的一步"）和案例 4.5：
合规检查必须作为独立工具，由确定性代码执行而非 LLM 记忆。

设计原则：
- 每条规范条款 = 一个纯函数，输入建筑数据，输出 pass/violation
- 返回结构化的违规报告，包含条款号、严重性、修复建议
- 规则可组合、可扩展
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Severity(Enum):
    ERROR = "error"          # 硬性违规，必须修改
    WARNING = "warning"      # 应当修改，可能导致报审失败
    INFO = "info"            # 建议，非强制


@dataclass
class Violation:
    """规范违规记录.

    对应案例 TC16 返回的 violations 数组中的单个条目。
    fix_action 提供可执行的修复 tool call 建议，让 Agent 能直接调用。
    """

    code: str                # 规范条款号，如 "GB 50016-2014 §5.5.17"
    severity: Severity
    description: str         # 违规描述
    location: str = ""       # 违规位置（可选）
    suggestion: str = ""     # 修复建议
    fix_action: dict | None = None  # 可执行修复: {tool, params, description}


@dataclass
class ComplianceResult:
    """合规检查完整结果."""

    violations: list[Violation] = field(default_factory=list)
    passes: list[str] = field(default_factory=list)
    standard: str = ""

    @property
    def has_errors(self) -> bool:
        return any(v.severity == Severity.ERROR for v in self.violations)

    @property
    def has_warnings(self) -> bool:
        return any(v.severity == Severity.WARNING for v in self.violations)

    def summary(self) -> dict:
        return {
            "standard": self.standard,
            "violations": len(self.violations),
            "errors": sum(1 for v in self.violations if v.severity == Severity.ERROR),
            "warnings": sum(1 for v in self.violations if v.severity == Severity.WARNING),
            "passes": len(self.passes),
        }


def check_building(
    building_info: dict[str, Any],
    standards: list[str] | None = None,
    scope: list[str] | None = None,
) -> ComplianceResult:
    """对建筑模型执行全面合规检查.

    对应案例 Tool Call 16 的入口函数。

    Args:
        building_info: 建筑信息字典，包含：
            - floors: 层数
            - area_per_floor: 每层面积 (m²)
            - total_height: 建筑总高 (mm)
            - stair_count: 疏散楼梯数量
            - structure_type: 结构类型
            - has_sprinkler: 是否有自动喷淋
            - wall_details: 墙体详情（可选）
        standards: 要检查的规范列表，默认全部。
        scope: 检查范围，如 ["fire_escape", "accessibility"]。

    Returns:
        ComplianceResult 包含所有违规和通过项。
    """
    from aec_building.compliance.rules.gb50016 import check_gb50016
    from aec_building.compliance.rules.jgj_t67 import check_jgj_t67

    standards = standards or ["GB_50016_2014", "JGJ_T_67_2019"]
    scope = scope or ["fire_escape", "fire_compartment", "accessibility", "exit_width"]

    result = ComplianceResult()

    if "GB_50016_2014" in standards:
        gb_result = check_gb50016(building_info, scope)
        result.violations.extend(gb_result.violations)
        result.passes.extend(gb_result.passes)
        result.standard = "GB 50016-2014 + JGJ/T 67-2019"

    if "JGJ_T_67_2019" in standards:
        jgj_result = check_jgj_t67(building_info, scope)
        result.violations.extend(jgj_result.violations)
        result.passes.extend(jgj_result.passes)

    return result
