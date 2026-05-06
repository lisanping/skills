"""基础几何图元：点、线、面、体的构造工具."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Point3D:
    """三维空间中的点."""

    x: float
    y: float
    z: float = 0.0

    def to_tuple(self) -> tuple[float, float, float]:
        return (self.x, self.y, self.z)

    def __add__(self, other: Point3D) -> Point3D:
        return Point3D(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other: Point3D) -> Point3D:
        return Point3D(self.x - other.x, self.y - other.y, self.z - other.z)

    def distance_to(self, other: Point3D) -> float:
        return float(np.sqrt(
            (self.x - other.x) ** 2
            + (self.y - other.y) ** 2
            + (self.z - other.z) ** 2
        ))


@dataclass(frozen=True)
class BBox3D:
    """三维包围盒."""

    min_pt: Point3D
    max_pt: Point3D

    @property
    def size_x(self) -> float:
        return self.max_pt.x - self.min_pt.x

    @property
    def size_y(self) -> float:
        return self.max_pt.y - self.min_pt.y

    @property
    def size_z(self) -> float:
        return self.max_pt.z - self.min_pt.z

    @property
    def volume(self) -> float:
        return self.size_x * self.size_y * self.size_z
