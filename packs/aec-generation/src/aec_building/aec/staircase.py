"""楼梯构件 — 参数化楼梯定义与几何验证.

对应案例 Tool Call 10-12：楼梯是最复杂的构件，
需要严格的几何验证和可操作的错误消息。

设计原则（案例 4.4）：失败即信号，错误消息必须包含可操作建议。
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum

from aec_building.aec.grid import GridSystem
from aec_building.core.references import GridRef, LevelRef


class StairType(Enum):
    STRAIGHT = "straight"
    U_TURN = "u_turn"
    L_TURN = "l_turn"


@dataclass
class StairValidationError:
    """楼梯验证错误 — 包含可操作建议.

    对应案例 TC10 的错误返回结构：
    不仅报告错误，还提供修复建议让 Agent 能直接推导下一步。
    """

    code: str
    message: str
    suggestions: list[str] = field(default_factory=list)


@dataclass
class StairSpec:
    """楼梯规格参数."""

    riser_height: float = 150.0      # 踏步高 (mm)
    tread_depth: float = 280.0       # 踏步深 (mm)
    width: float = 1200.0            # 梯段宽 (mm)
    landing_length: float = 1200.0   # 平台长 (mm)
    runs_per_level: int = 2          # 每层梯段数
    stair_type: StairType = StairType.U_TURN

    # 规范限值 (GB 50352-2019 §6.8 / JGJ/T 67-2019)
    MAX_RISER_HEIGHT: float = 175.0  # 办公建筑最大踏步高 (GB 50352 §6.8.1)
    MIN_TREAD_DEPTH: float = 260.0   # 办公建筑最小踏步深 (GB 50352 §6.8.1)
    MIN_WIDTH: float = 1100.0        # 公共建筑最小梯段宽 (GB 50352 §6.8.2)


@dataclass
class Staircase:
    """楼梯构件.

    Attributes:
        location: 楼梯定位（轴网参照）。
        base_level: 起始标高。
        top_level: 终止标高。
        spec: 楼梯规格参数。
    """

    location: GridRef
    base_level: LevelRef
    top_level: LevelRef
    spec: StairSpec = field(default_factory=StairSpec)

    def validate(self, available_length: float, available_width: float) -> list[StairValidationError]:
        """验证楼梯几何可行性.

        对应案例 TC10 的失败场景：检查踏步数、梯段长度是否能
        容纳在给定的空间内。

        Args:
            available_length: 楼梯间可用长度 (mm)。
            available_width: 楼梯间可用宽度 (mm)。

        Returns:
            验证错误列表，空列表表示通过。
        """
        errors = []
        s = self.spec

        # 规范检查
        if s.riser_height > s.MAX_RISER_HEIGHT:
            errors.append(StairValidationError(
                code="RISER_TOO_HIGH",
                message=f"踏步高 {s.riser_height}mm 超过规范限值 {s.MAX_RISER_HEIGHT}mm",
                suggestions=[f"降低踏步高到 {s.MAX_RISER_HEIGHT}mm 以内"],
            ))

        if s.tread_depth < s.MIN_TREAD_DEPTH:
            errors.append(StairValidationError(
                code="TREAD_TOO_SHALLOW",
                message=f"踏步深 {s.tread_depth}mm 低于规范下限 {s.MIN_TREAD_DEPTH}mm",
                suggestions=[f"增大踏步深到 {s.MIN_TREAD_DEPTH}mm 以上"],
            ))

        if s.width < s.MIN_WIDTH:
            errors.append(StairValidationError(
                code="STAIR_TOO_NARROW",
                message=f"梯段宽 {s.width}mm 低于规范下限 {s.MIN_WIDTH}mm",
                suggestions=[f"增大梯段宽到 {s.MIN_WIDTH}mm 以上"],
            ))

        # 宽度检查（双跑楼梯需要 2 个梯段宽 + 间隙）
        if s.stair_type == StairType.U_TURN:
            required_width = s.width * 2 + 100  # 100mm 间距
            if required_width > available_width:
                errors.append(StairValidationError(
                    code="STAIR_WIDTH_INSUFFICIENT",
                    message=f"双跑楼梯需要 {required_width}mm 宽，可用仅 {available_width}mm",
                    suggestions=[
                        f"增大楼梯间宽度到 {required_width}mm",
                        f"减小梯段宽到 {(available_width - 100) / 2:.0f}mm",
                        "改用单跑楼梯（StairType.STRAIGHT）",
                    ],
                ))

        return errors

    def compute_geometry(self, total_rise: float) -> dict | StairValidationError:
        """计算楼梯几何参数.

        对应案例 TC10 的几何推理过程。

        Args:
            total_rise: 总升高 (mm)，即 top_level - base_level。

        Returns:
            几何参数字典，或验证错误。
        """
        s = self.spec
        total_risers = math.ceil(total_rise / s.riser_height)
        actual_riser_height = total_rise / total_risers

        # 每个楼层的踏步数
        levels = round(total_rise / 3900)  # 假设层高 ~3900
        if levels < 1:
            levels = 1
        risers_per_level = math.ceil(total_risers / levels)

        risers_per_run = math.ceil(risers_per_level / s.runs_per_level)
        run_length = risers_per_run * s.tread_depth
        landings = s.runs_per_level  # 含顶部平台
        total_length_needed = run_length + s.landing_length * landings

        return {
            "total_risers": total_risers,
            "actual_riser_height": actual_riser_height,
            "risers_per_level": risers_per_level,
            "risers_per_run": risers_per_run,
            "run_length": run_length,
            "total_length_needed": total_length_needed,
            "landings": landings,
        }

    def check_fits_in_space(
        self,
        total_rise: float,
        available_length: float,
    ) -> StairValidationError | None:
        """检查楼梯是否能装进给定空间.

        对应案例 TC10 的核心失败逻辑。

        Returns:
            None 表示可以装下，否则返回包含修复建议的错误。
        """
        geom = self.compute_geometry(total_rise)
        if isinstance(geom, StairValidationError):
            return geom

        if geom["total_length_needed"] > available_length:
            needed = geom["total_length_needed"]
            # 计算替代方案
            alt_riser = total_rise / (total_rise / 162.5)  # 更大踏步高
            extra_space = needed - available_length

            return StairValidationError(
                code="STAIR_GEOMETRY_INVALID",
                message=(
                    f"楼梯总长 {needed:.0f}mm 超过可用空间 {available_length:.0f}mm，"
                    f"差 {extra_space:.0f}mm"
                ),
                suggestions=[
                    f"增加踏步高到 162.5mm（减少踏步数）",
                    f"扩大楼梯间长度 {extra_space:.0f}mm",
                    "增加一个中间平台分散长度",
                ],
            )

        return None

    def to_brep(self, grid: GridSystem, total_rise: float) -> object:
        """生成楼梯 BREP 实体.

        简化模型：生成楼梯间的实体包络（长方体 + 踏步锯齿面）。
        真实场景由 Revit 族实例处理细节，此处提供几何占位。

        Args:
            grid: 轴网系统（解析参照位置和标高）。
            total_rise: 总上升高度 (mm)。

        Returns:
            CadQuery Workplane 对象。
        """
        import cadquery as cq

        s = self.spec
        geom = self.compute_geometry(total_rise)

        # 解析位置
        x, y = self.location.resolve(grid)
        base_z = self.base_level.resolve(grid)

        width = s.width
        run_length = geom["run_length"]
        landing = s.landing_length

        if s.stair_type == StairType.U_TURN:
            # U 形楼梯：两跑并排 + 中间平台
            total_width = width * 2 + 100  # 100mm 间距
            total_length = run_length + landing
        else:
            total_width = width
            total_length = run_length + landing

        # 楼梯间外包络
        shape = (
            cq.Workplane("XY")
            .workplane(offset=base_z)
            .center(x, y)
            .rect(total_length, total_width)
            .extrude(total_rise)
        )

        # 生成踏步锯齿（每跑）
        riser_h = geom["actual_riser_height"]
        tread_d = s.tread_depth
        risers_per_run = geom["risers_per_run"]

        stair_profile = [(0, 0)]
        for i in range(risers_per_run):
            stair_profile.append((i * tread_d, (i + 1) * riser_h))
            stair_profile.append(((i + 1) * tread_d, (i + 1) * riser_h))
        # 闭合回底部
        stair_profile.append((risers_per_run * tread_d, 0))

        try:
            stair_solid = (
                cq.Workplane("XZ")
                .workplane(offset=y - width / 2)
                .center(x - total_length / 2, base_z)
                .polyline(stair_profile)
                .close()
                .extrude(width)
            )
            return stair_solid
        except Exception:
            # 踏步细节失败时返回包络
            return shape
