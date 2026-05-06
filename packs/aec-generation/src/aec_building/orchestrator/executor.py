"""执行引擎 — 按 ExecutionPlan 逐步调用 MCP 工具.

对应案例 §4.3（自我验证节点）和 §4.4（失败即信号）：
- 按依赖顺序执行步骤
- 检查点处暂停并验证
- 失败时使用 recovery strategy 自动修复并重试

核心模式（案例 TC 10→11→12）：
  楼梯创建失败 → 扩大核心筒 → 重新创建楼梯
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable

from aec_building.mcp.server import GeometryKernelMCP, ToolResponse
from aec_building.orchestrator.planner import ExecutionPlan, PlanStep, StepStatus

logger = logging.getLogger(__name__)


@dataclass
class RecoveryAction:
    """失败恢复动作.

    当某个步骤失败时，执行一系列修复动作后重试原步骤。
    """

    description: str
    tool: str
    params: dict = field(default_factory=dict)


@dataclass
class RecoveryStrategy:
    """失败恢复策略.

    绑定到特定的失败模式，当错误消息匹配时触发。
    """

    error_pattern: str  # 错误消息中包含的关键字
    actions: list[RecoveryAction] = field(default_factory=list)
    description: str = ""


@dataclass
class ExecutionResult:
    """执行引擎的最终结果."""

    plan: ExecutionPlan
    success: bool
    steps_completed: int
    steps_failed: int
    steps_skipped: int
    log: list[str] = field(default_factory=list)

    @property
    def summary(self) -> dict:
        return {
            "success": self.success,
            "steps_completed": self.steps_completed,
            "steps_failed": self.steps_failed,
            "steps_skipped": self.steps_skipped,
            "progress": self.plan.progress,
        }


class Executor:
    """按 ExecutionPlan 执行 MCP 工具调用.

    职责：
    1. 按依赖拓扑序执行步骤
    2. 将 PlanStep.tool + params 映射到 MCP 方法调用
    3. 失败时查找匹配的 RecoveryStrategy 并重试
    4. 检查点步骤触发 checkpoint_callback
    """

    def __init__(
        self,
        mcp: GeometryKernelMCP,
        plan: ExecutionPlan,
        *,
        param_resolver: Callable[[PlanStep, GeometryKernelMCP], dict] | None = None,
        recovery_strategies: list[RecoveryStrategy] | None = None,
        checkpoint_callback: Callable[[PlanStep, GeometryKernelMCP], bool] | None = None,
    ) -> None:
        self.mcp = mcp
        self.plan = plan
        self._param_resolver = param_resolver or _default_param_resolver
        self._recovery_strategies = recovery_strategies or []
        self._checkpoint_cb = checkpoint_callback
        self._log: list[str] = []

    def run(self) -> ExecutionResult:
        """执行完整计划.

        按步骤 ID 顺序执行。每步先检查依赖是否满足，
        然后调用 MCP 工具，处理结果。

        Returns:
            ExecutionResult 包含执行结果和日志。
        """
        for step in self.plan.steps:
            # 检查依赖是否满足
            if not self._deps_satisfied(step):
                step.status = StepStatus.SKIPPED
                self._log_step(step, "SKIPPED: 依赖未满足")
                continue

            # 执行步骤
            success = self._execute_step(step)

            if not success and step.status == StepStatus.FAILED:
                # 查找恢复策略
                recovered = self._try_recovery(step)
                if not recovered:
                    self._log_step(step, f"FAILED: {step.error}")
                    # 非关键步骤可以继续，关键步骤中断
                    if step.tool in ("create_project", "create_floors", "place_columns"):
                        self._log_step(step, "ABORT: 关键步骤失败，中断执行")
                        break

        return self._build_result()

    def _execute_step(self, step: PlanStep) -> bool:
        """执行单个步骤."""
        step.status = StepStatus.IN_PROGRESS
        self._log_step(step, "IN_PROGRESS")

        # 检查点步骤
        if step.is_checkpoint:
            return self._execute_checkpoint(step)

        # 解析参数
        try:
            params = self._param_resolver(step, self.mcp)
        except Exception as e:
            step.status = StepStatus.FAILED
            step.error = f"参数解析失败: {e}"
            return False

        # 调用 MCP 工具
        try:
            resp = self._call_tool(step.tool, params)
        except Exception as e:
            step.status = StepStatus.FAILED
            step.error = str(e)
            return False

        # 检查响应
        if resp.status == "error":
            step.status = StepStatus.FAILED
            step.error = str(resp.data.get("message", resp.data))
            step.result = resp.to_dict()
            return False

        step.status = StepStatus.COMPLETED
        step.result = resp.to_dict()
        self._log_step(step, f"COMPLETED: {resp.status}")
        return True

    def _execute_checkpoint(self, step: PlanStep) -> bool:
        """执行检查点 — 自我验证."""
        if self._checkpoint_cb:
            passed = self._checkpoint_cb(step, self.mcp)
            if not passed:
                step.status = StepStatus.FAILED
                step.error = "检查点验证失败"
                self._log_step(step, "CHECKPOINT FAILED")
                return False

        # 默认：获取摘要作为检查
        resp = self.mcp.get_summary()
        step.status = StepStatus.COMPLETED
        step.result = resp.to_dict()
        self._log_step(step, f"CHECKPOINT OK: {resp.data.get('total_elements', 0)} elements")
        return True

    def _call_tool(self, tool_name: str, params: dict) -> ToolResponse:
        """将工具名映射到 MCP 方法并调用."""
        method_map = {
            "create_project": self.mcp.create_project,
            "create_floors": self.mcp.create_floors,
            "place_columns": self.mcp.place_columns,
            "create_walls": self.mcp.create_walls,
            "create_opening": self.mcp.create_opening,
            "modify_element": self.mcp.modify_element,
            "check_compliance": self.mcp.check_compliance,
            "export_model": self.mcp.export_model,
            "get_summary": self.mcp.get_summary,
            "create_curtain_wall": self.mcp.create_curtain_wall,
            "auto_place_doors": self.mcp.auto_place_doors,
            "place_beams": self.mcp.place_beams,
            "visual_check": self.mcp.visual_check,
            "take_snapshot": self.mcp.take_snapshot,
            "rollback": self.mcp.rollback,
            "state_diff": self.mcp.state_diff,
        }

        method = method_map.get(tool_name)
        if method is None:
            # 未实现的工具返回 partial_success
            return ToolResponse(
                status="partial_success",
                data={"message": f"工具 '{tool_name}' 尚未实现，已跳过"},
                warnings=[f"未实现: {tool_name}"],
            )

        return method(**params)

    def _deps_satisfied(self, step: PlanStep) -> bool:
        """检查步骤的所有依赖是否已完成."""
        for dep_id in step.depends_on:
            dep_step = self.plan.steps[dep_id - 1]  # ID 从 1 开始
            if dep_step.status not in (StepStatus.COMPLETED,):
                return False
        return True

    def _try_recovery(self, step: PlanStep) -> bool:
        """尝试恢复策略 — 对应案例 TC 10→11→12 模式.

        当步骤失败时，查找匹配的恢复策略：
        1. 执行恢复动作（如修改核心筒边界）
        2. 重试原步骤
        """
        if step.retry_count >= step.max_retries:
            return False

        error_msg = step.error or ""
        for strategy in self._recovery_strategies:
            if strategy.error_pattern in error_msg:
                self._log_step(step, f"RECOVERY: {strategy.description}")

                # 执行恢复动作
                for action in strategy.actions:
                    try:
                        self._call_tool(action.tool, action.params)
                        self._log_step(step, f"  修复: {action.description}")
                    except Exception as e:
                        self._log_step(step, f"  修复失败: {e}")
                        return False

                # 重试
                step.retry_count += 1
                step.status = StepStatus.PENDING
                step.error = None
                return self._execute_step(step)

        return False

    def _log_step(self, step: PlanStep, message: str) -> None:
        entry = f"[Step {step.id}] {step.description}: {message}"
        self._log.append(entry)
        logger.info(entry)

    def _build_result(self) -> ExecutionResult:
        completed = sum(1 for s in self.plan.steps if s.status == StepStatus.COMPLETED)
        failed = sum(1 for s in self.plan.steps if s.status == StepStatus.FAILED)
        skipped = sum(1 for s in self.plan.steps if s.status == StepStatus.SKIPPED)

        return ExecutionResult(
            plan=self.plan,
            success=failed == 0,
            steps_completed=completed,
            steps_failed=failed,
            steps_skipped=skipped,
            log=self._log,
        )


# ── 默认参数解析器 ──

def _default_param_resolver(step: PlanStep, mcp: GeometryKernelMCP) -> dict:
    """从步骤定义和当前建筑状态推导工具参数.

    如果 step.params 已填充，直接使用。
    否则根据工具类型从建筑状态推导默认参数。
    """
    if step.params:
        return step.params

    # 根据工具类型推导参数
    tool = step.tool

    if tool == "create_project":
        return {
            "name": "L_Office_v1",
            "x_grid_names": ["A", "B", "C", "D", "E"],
            "x_grid_positions": [0, 8000, 16000, 24000, 32000],
            "y_grid_names": ["1", "2", "3", "4"],
            "y_grid_positions": [0, 7000, 13000, 20000],
            "level_names": ["F1", "F2", "F3", "Roof"],
            "level_elevations": [0, 3900, 7800, 11700],
        }

    if tool == "create_floors":
        return {
            "boundary_points": [
                (0, 0), (32000, 0), (32000, 13000),
                (16000, 13000), (16000, 20000), (0, 20000),
            ],
            "levels": ["F1", "F2", "F3"],
        }

    if tool == "create_opening":
        # 从建筑状态获取楼板 ID
        slab_ids = [be.id for be in mcp.building.slabs]
        return {
            "x_grid_start": "B",
            "x_grid_end": "D",
            "y_grid_start": "1",
            "y_grid_end": "2",
            "target_slab_ids": slab_ids,
            "inset": 500.0,
        }

    if tool == "place_columns":
        return {
            "base_level": "F1",
            "top_level": "Roof",
            "skip_x": ["C", "D", "E"],
            "skip_y": ["3", "4"],
        }

    if tool == "create_walls":
        return {
            "walls": [
                {"start": [8000, 0], "end": [8000, 7000],
                 "base_level": "F1", "top_level": "Roof", "wall_type": "fire"},
                {"start": [8000, 7000], "end": [16000, 7000],
                 "base_level": "F1", "top_level": "Roof", "wall_type": "fire"},
                {"start": [16000, 7000], "end": [16000, 0],
                 "base_level": "F1", "top_level": "Roof", "wall_type": "fire"},
            ],
        }

    if tool == "check_compliance":
        return {
            "standards": ["GB_50016_2014", "JGJ_T_67_2019"],
            "scope": ["fire_escape", "fire_compartment"],
            "extra_info": {
                "stair_count": 2,
                "shape": "L",
            },
        }

    if tool == "export_model":
        return {
            "output_path": "output/l_office_v1",
            "formats": ["step"],
        }

    # 未知工具 — 返回空参数
    return {}


# ── 预定义恢复策略 ──

def stair_recovery_strategy() -> RecoveryStrategy:
    """楼梯失败恢复策略.

    对应案例 TC 10→11→12：
    楼梯空间不足 → 扩大核心筒南墙 → 重新创建楼梯。
    """
    return RecoveryStrategy(
        error_pattern="STAIR_GEOMETRY_INVALID",
        description="楼梯空间不足 → 扩大核心筒",
        actions=[
            RecoveryAction(
                description="核心筒南墙向南扩 1m",
                tool="modify_element",
                params={
                    "element_id": "wall_0002",  # 核心筒南墙
                    "changes": {"end": (16000, 7000)},
                },
            ),
        ],
    )


def run_l_office_plan(
    output_path: str = "output/l_office_v1",
) -> ExecutionResult:
    """一键执行 L 形办公楼完整计划.

    将 planner + executor + MCP 串联为端到端流程。

    Args:
        output_path: 导出文件路径前缀。

    Returns:
        ExecutionResult。
    """
    from aec_building.orchestrator.planner import plan_l_office_building

    plan = plan_l_office_building()
    mcp = GeometryKernelMCP()

    executor = Executor(
        mcp=mcp,
        plan=plan,
        recovery_strategies=[stair_recovery_strategy()],
    )

    return executor.run()
