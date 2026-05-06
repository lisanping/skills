"""参照定位系统 — 基于轴网/标高的参数化定位，而非绝对坐标.

设计原则（案例 4.2）：参照驱动 > 坐标驱动。
所有几何基于轴网、标高、参照平面建立，后续修改触发参数化连锁更新。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aec_building.aec.grid import GridSystem


@dataclass(frozen=True)
class GridRef:
    """轴网交点参照.

    用轴线名称定位，而非绝对坐标。当轴网间距修改时，
    所有引用该参照的几何自动获得新坐标。

    Attributes:
        x_grid: X 方向轴线名称，如 "B"。
        y_grid: Y 方向轴线名称，如 "2"。
        offset_x: 距轴线交点的 X 偏移 (mm)。
        offset_y: 距轴线交点的 Y 偏移 (mm)。
    """

    x_grid: str
    y_grid: str
    offset_x: float = 0.0
    offset_y: float = 0.0

    def resolve(self, grid: GridSystem) -> tuple[float, float]:
        """解析为绝对坐标 (x, y)."""
        base_x, base_y = grid.grid_intersection(self.x_grid, self.y_grid)
        return (base_x + self.offset_x, base_y + self.offset_y)


@dataclass(frozen=True)
class LevelRef:
    """标高参照.

    Attributes:
        level: 标高名称，如 "F1"。
        offset: 距标高的 Z 偏移 (mm)，正值向上。
    """

    level: str
    offset: float = 0.0

    def resolve(self, grid: GridSystem) -> float:
        """解析为绝对标高 (mm)."""
        return grid.level_elevation(self.level) + self.offset


@dataclass(frozen=True)
class GridRangeRef:
    """轴网范围参照 — 用于定义矩形区域.

    由两条 X 轴线和两条 Y 轴线围合的矩形区域，
    可选内缩偏移。用于中庭开洞、防火分区等。

    Attributes:
        x_grid_start: 起始 X 轴线名。
        x_grid_end: 终止 X 轴线名。
        y_grid_start: 起始 Y 轴线名。
        y_grid_end: 终止 Y 轴线名。
        inset: 距轴线向内缩进 (mm)。
    """

    x_grid_start: str
    x_grid_end: str
    y_grid_start: str
    y_grid_end: str
    inset: float = 0.0

    def resolve(self, grid: GridSystem) -> tuple[float, float, float, float]:
        """解析为 (x_min, y_min, x_max, y_max) 矩形边界."""
        x1 = grid.x_grids[self.x_grid_start]
        x2 = grid.x_grids[self.x_grid_end]
        y1 = grid.y_grids[self.y_grid_start]
        y2 = grid.y_grids[self.y_grid_end]

        x_min, x_max = sorted([x1, x2])
        y_min, y_max = sorted([y1, y2])

        return (
            x_min + self.inset,
            y_min + self.inset,
            x_max - self.inset,
            y_max - self.inset,
        )

    def resolve_boundary(self, grid: GridSystem) -> list[tuple[float, float]]:
        """解析为闭合矩形边界点列表（逆时针）."""
        x_min, y_min, x_max, y_max = self.resolve(grid)
        return [
            (x_min, y_min),
            (x_max, y_min),
            (x_max, y_max),
            (x_min, y_max),
        ]
