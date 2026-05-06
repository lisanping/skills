"""任务规划器 — 将设计意图分解为 tool call 序列.

对应案例完整 20 步序列的规划逻辑：
根据约束集自动生成执行计划，包含检查点和回退策略。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class StepStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class PlanStep:
    """执行计划中的一步.

    Attributes:
        id: 步骤编号。
        tool: 要调用的 MCP 工具名。
        description: 步骤描述。
        params: 工具参数。
        status: 当前状态。
        is_checkpoint: 是否为自我验证检查点（案例 4.3）。
        depends_on: 前置步骤 ID 列表。
        retry_count: 已重试次数。
        max_retries: 最大重试次数。
    """

    id: int
    tool: str
    description: str
    params: dict = field(default_factory=dict)
    status: StepStatus = StepStatus.PENDING
    is_checkpoint: bool = False
    depends_on: list[int] = field(default_factory=list)
    retry_count: int = 0
    max_retries: int = 2
    result: dict | None = None
    error: str | None = None


@dataclass
class ExecutionPlan:
    """完整执行计划."""

    steps: list[PlanStep] = field(default_factory=list)

    def add_step(self, **kwargs) -> PlanStep:
        step_id = len(self.steps) + 1
        step = PlanStep(id=step_id, **kwargs)
        self.steps.append(step)
        return step

    @property
    def current_step(self) -> PlanStep | None:
        for s in self.steps:
            if s.status in (StepStatus.PENDING, StepStatus.IN_PROGRESS):
                return s
        return None

    @property
    def progress(self) -> dict:
        total = len(self.steps)
        completed = sum(1 for s in self.steps if s.status == StepStatus.COMPLETED)
        failed = sum(1 for s in self.steps if s.status == StepStatus.FAILED)
        return {
            "total": total,
            "completed": completed,
            "failed": failed,
            "remaining": total - completed - failed,
            "progress_pct": round(completed / total * 100) if total > 0 else 0,
        }


def plan_l_office_building(
    floors: int = 3,
    area_per_floor: float = 800.0,
    max_span: float = 9.0,
    has_atrium: bool = True,
    core_position: str = "north",
) -> ExecutionPlan:
    """为 L 形办公楼生成执行计划.

    对应案例完整 20 步 tool call 序列。
    自动安插检查点（每 5-8 步，案例 4.3）。

    Returns:
        ExecutionPlan 包含所有步骤。
    """
    plan = ExecutionPlan()

    # Phase 1: 基础设施
    plan.add_step(
        tool="create_project",
        description="创建项目 + 轴网 + 标高",
    )

    # Phase 2: 主体结构
    plan.add_step(
        tool="create_floors",
        description=f"创建 {floors} 层 L 形楼板",
        depends_on=[1],
    )

    if has_atrium:
        plan.add_step(
            tool="create_opening",
            description="中庭开洞（基于轴网参照）",
            depends_on=[2],
        )

    plan.add_step(
        tool="place_columns",
        description="批量放置柱子（跳过 NE 切除区）",
        depends_on=[1],
    )

    plan.add_step(
        tool="create_walls",
        description="创建核心筒墙体",
        depends_on=[1],
    )

    # Phase 2.5: 第一次自检
    plan.add_step(
        tool="visual_check",
        description="视觉自查 — 检查柱网/楼板/核心筒",
        is_checkpoint=True,
        depends_on=[2, 4, 5],
    )

    # Phase 3: 竖向交通
    plan.add_step(
        tool="create_stair",
        description="核心筒内楼梯（可能失败需重试）",
        depends_on=[5],
    )

    plan.add_step(
        tool="create_stair",
        description="第二部疏散楼梯（合规要求）",
        depends_on=[5],
    )

    # Phase 4: 外围护
    plan.add_step(
        tool="create_walls",
        description="南侧幕墙 + 其他外墙",
        depends_on=[1],
    )

    plan.add_step(
        tool="create_doors",
        description="批量放置办公室门",
        depends_on=[9],
    )

    # Phase 5: 验证
    plan.add_step(
        tool="check_compliance",
        description="规范合规检查（GB 50016 + JGJ/T 67）",
        depends_on=[7, 8],
    )

    # Phase 5.5: 第二次自检
    plan.add_step(
        tool="visual_check",
        description="最终视觉自查",
        is_checkpoint=True,
        depends_on=[11],
    )

    # Phase 6: 导出
    plan.add_step(
        tool="export_model",
        description="导出 STEP + IFC",
        depends_on=[12],
    )

    plan.add_step(
        tool="generate_report",
        description="生成交付报告",
        depends_on=[13],
    )

    return plan
