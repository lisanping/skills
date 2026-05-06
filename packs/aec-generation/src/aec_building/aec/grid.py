"""建筑轴网与标高系统."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class GridSystem:
    """建筑轴网定义.

    Attributes:
        x_grids: X 方向轴线名称与坐标 (mm)，如 {"A": 0, "B": 8000, ...}。
        y_grids: Y 方向轴线名称与坐标 (mm)。
        levels: 标高名称与高程 (mm)，如 {"F1": 0, "F2": 3900, ...}。
    """

    x_grids: dict[str, float] = field(default_factory=dict)
    y_grids: dict[str, float] = field(default_factory=dict)
    levels: dict[str, float] = field(default_factory=dict)

    def add_x_grids(self, names: list[str], positions: list[float]) -> None:
        for n, p in zip(names, positions):
            self.x_grids[n] = p

    def add_y_grids(self, names: list[str], positions: list[float]) -> None:
        for n, p in zip(names, positions):
            self.y_grids[n] = p

    def add_levels(self, names: list[str], elevations: list[float]) -> None:
        for n, e in zip(names, elevations):
            self.levels[n] = e

    def grid_intersection(self, x_name: str, y_name: str) -> tuple[float, float]:
        """返回两条轴线交点坐标 (x, y)."""
        return (self.x_grids[x_name], self.y_grids[y_name])

    def level_elevation(self, name: str) -> float:
        return self.levels[name]
