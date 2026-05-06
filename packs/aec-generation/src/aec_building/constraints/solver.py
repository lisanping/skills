"""约束求解器 — 从约束集推导几何参数.

对应案例 Tool Call 2 中 Agent 的几何推理过程：
从面积约束 + 柱距约束 + 形状约束，求解平面尺寸。

支持的平面形状:
  - L / rectangle: 现代办公建筑
  - polygon: 正多边形 (八角塔、六角亭等)
  - circular: 圆形 (圆形大厅、穹顶)
  - courtyard: 院落式 (四合院、宫殿群)
  - custom: 用户提供任意边界点
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from aec_building.constraints.schema import ConstraintSet, ConstraintType


@dataclass
class LShapeSolution:
    """L 形平面尺寸求解结果."""

    total_x: float       # 外包矩形 X 方向总长 (mm)
    total_y: float       # 外包矩形 Y 方向总长 (mm)
    cutout_x: float      # 切除矩形 X 方向尺寸 (mm)
    cutout_y: float       # 切除矩形 Y 方向尺寸 (mm)
    actual_area: float   # 实际面积 (m²)
    x_spans: list[float] = field(default_factory=list)  # X 方向各跨距 (mm)
    y_spans: list[float] = field(default_factory=list)  # Y 方向各跨距 (mm)
    warnings: list[str] = field(default_factory=list)


@dataclass
class DesignSolution:
    """完整设计方案求解结果.

    包含轴网、标高、楼板边界、核心筒/中庭位置推荐值，
    可直接传给 create_project / create_floors 等 MCP 工具。
    """

    # 轴网
    x_grid_names: list[str] = field(default_factory=list)
    x_grid_positions: list[float] = field(default_factory=list)
    y_grid_names: list[str] = field(default_factory=list)
    y_grid_positions: list[float] = field(default_factory=list)

    # 标高
    level_names: list[str] = field(default_factory=list)
    level_elevations: list[float] = field(default_factory=list)

    # 楼板
    floor_boundary: list[tuple[float, float]] = field(default_factory=list)
    actual_area: float = 0.0

    # 功能分区推荐
    core_zone: dict = field(default_factory=dict)     # {x_range, y_range}
    atrium_zone: dict = field(default_factory=dict)   # {x_range, y_range}
    entrance_wall: dict = field(default_factory=dict)  # {start, end, direction}

    # 柱跳过区
    column_skip_x: list[str] = field(default_factory=list)
    column_skip_y: list[str] = field(default_factory=list)

    # 自定义柱位 (非矩形柱网时使用)
    column_positions: list[tuple[float, float]] = field(default_factory=list)

    # 建筑风格元信息
    building_style: str = ""  # "modern_office" / "traditional" / "heritage" / ...

    # 元信息
    warnings: list[str] = field(default_factory=list)


def solve_design(
    floors: int = 3,
    area_per_floor: float = 800.0,
    shape: str = "L",
    max_span: float = 9.0,
    floor_height: float = 3900.0,
    cutout_corner: str = "NE",
    has_atrium: bool = False,
    core_position: str = "north",
    entrance_direction: str = "south",
    # ── 新增: 多风格支持 ──
    polygon_sides: int = 0,
    custom_boundary: list[tuple[float, float]] | None = None,
    building_style: str = "",
    center_x: float = 0.0,
    center_y: float = 0.0,
) -> DesignSolution:
    """从结构化约束求解完整设计方案.

    将 Agent 提取的约束参数转化为可直接传给 MCP 工具的几何数据。

    Args:
        floors: 层数。
        area_per_floor: 每层目标面积 (m²)。
        shape: 平面形状:
            - "L": L 形 (需 cutout_corner)
            - "rectangle": 矩形
            - "polygon": 正多边形 (需 polygon_sides)
            - "circular": 圆形 (用 polygon_sides=36 近似)
            - "courtyard": 院落式矩形 (外包矩形减去中央庭院)
            - "custom": 自定义边界 (需 custom_boundary)
        max_span: 最大柱距 (m)。
        floor_height: 层高 (mm)。
        cutout_corner: L 形切除角 ("NE"/"NW"/"SE"/"SW")。
        has_atrium: 是否需要中庭。
        core_position: 核心筒位置 ("north"/"south"/"east"/"west")。
        entrance_direction: 主入口朝向。
        polygon_sides: 正多边形边数 (shape="polygon" 时使用, 3~36)。
        custom_boundary: 自定义楼板边界点 (shape="custom" 时使用)。
        building_style: 建筑风格标签 (可选, 用于元信息)。
        center_x: 多边形/圆形平面中心 X (mm)。
        center_y: 多边形/圆形平面中心 Y (mm)。

    Returns:
        DesignSolution 包含所有可直接使用的几何参数。
    """
    sol = DesignSolution()
    sol.building_style = building_style

    if shape == "polygon" or shape == "circular":
        sol = _solve_polygon_design(
            sol, floors, area_per_floor, max_span, floor_height,
            polygon_sides if shape == "polygon" else 36,
            center_x, center_y, entrance_direction,
        )
    elif shape == "courtyard":
        sol = _solve_courtyard_design(
            sol, floors, area_per_floor, max_span, floor_height,
            entrance_direction, core_position,
        )
    elif shape == "custom" and custom_boundary:
        sol = _solve_custom_design(
            sol, floors, area_per_floor, floor_height,
            custom_boundary, entrance_direction,
        )
    elif shape == "L":
        l_sol = solve_l_shape_dimensions(
            target_area=area_per_floor,
            max_span=max_span,
            area_tolerance=0.10,
            cutout_corner=cutout_corner,
        )
        sol.warnings.extend(l_sol.warnings)
        sol.actual_area = l_sol.actual_area

        # 构造轴网
        x_positions = [0.0]
        for s in l_sol.x_spans:
            x_positions.append(x_positions[-1] + s)
        y_positions = [0.0]
        for s in l_sol.y_spans:
            y_positions.append(y_positions[-1] + s)

        n_x = len(x_positions)
        n_y = len(y_positions)
        sol.x_grid_names = [chr(ord("A") + i) for i in range(n_x)]
        sol.x_grid_positions = x_positions
        sol.y_grid_names = [str(i + 1) for i in range(n_y)]
        sol.y_grid_positions = y_positions

        # 构造 L 形楼板边界 (6 个顶点)
        total_x = l_sol.total_x
        total_y = l_sol.total_y
        cutout_x = l_sol.cutout_x
        cutout_y = l_sol.cutout_y

        if cutout_corner == "NE":
            sol.floor_boundary = [
                (0, 0),
                (total_x, 0),
                (total_x, total_y - cutout_y),
                (total_x - cutout_x, total_y - cutout_y),
                (total_x - cutout_x, total_y),
                (0, total_y),
            ]
            # 柱跳过区: 切除角对应的轴线
            cutout_x_start = total_x - cutout_x
            cutout_y_start = total_y - cutout_y
            sol.column_skip_x = [
                sol.x_grid_names[i]
                for i, p in enumerate(x_positions)
                if p > cutout_x_start - 1  # 包含边缘轴线
            ]
            sol.column_skip_y = [
                sol.y_grid_names[i]
                for i, p in enumerate(y_positions)
                if p > cutout_y_start - 1
            ]
        elif cutout_corner == "NW":
            sol.floor_boundary = [
                (0, 0),
                (total_x, 0),
                (total_x, total_y),
                (cutout_x, total_y),
                (cutout_x, total_y - cutout_y),
                (0, total_y - cutout_y),
            ]
            sol.column_skip_x = [
                sol.x_grid_names[i]
                for i, p in enumerate(x_positions)
                if p < cutout_x + 1
            ]
            sol.column_skip_y = [
                sol.y_grid_names[i]
                for i, p in enumerate(y_positions)
                if p > (total_y - cutout_y) - 1
            ]
        elif cutout_corner == "SE":
            sol.floor_boundary = [
                (0, 0),
                (total_x - cutout_x, 0),
                (total_x - cutout_x, cutout_y),
                (total_x, cutout_y),
                (total_x, total_y),
                (0, total_y),
            ]
            sol.column_skip_x = [
                sol.x_grid_names[i]
                for i, p in enumerate(x_positions)
                if p > (total_x - cutout_x) - 1
            ]
            sol.column_skip_y = [
                sol.y_grid_names[i]
                for i, p in enumerate(y_positions)
                if p < cutout_y + 1
            ]
        else:  # SW
            sol.floor_boundary = [
                (cutout_x, 0),
                (total_x, 0),
                (total_x, total_y),
                (0, total_y),
                (0, cutout_y),
                (cutout_x, cutout_y),
            ]
            sol.column_skip_x = [
                sol.x_grid_names[i]
                for i, p in enumerate(x_positions)
                if p < cutout_x + 1
            ]
            sol.column_skip_y = [
                sol.y_grid_names[i]
                for i, p in enumerate(y_positions)
                if p < cutout_y + 1
            ]

    else:
        # 矩形平面: 简单求解
        area_mm2 = area_per_floor * 1e6
        max_span_mm = max_span * 1000

        # 尝试黄金比例 ~1.5:1
        ratio = 1.5
        side_y = math.sqrt(area_mm2 / ratio)
        side_x = area_mm2 / side_y

        nx = max(2, math.ceil(side_x / max_span_mm))
        ny = max(2, math.ceil(side_y / max_span_mm))
        span_x = math.ceil(side_x / nx / 1000) * 1000  # 取整到米
        span_y = math.ceil(side_y / ny / 1000) * 1000

        total_x = span_x * nx
        total_y = span_y * ny
        sol.actual_area = (total_x * total_y) / 1e6

        x_positions = [span_x * i for i in range(nx + 1)]
        y_positions = [span_y * i for i in range(ny + 1)]

        sol.x_grid_names = [chr(ord("A") + i) for i in range(nx + 1)]
        sol.x_grid_positions = x_positions
        sol.y_grid_names = [str(i + 1) for i in range(ny + 1)]
        sol.y_grid_positions = y_positions

        sol.floor_boundary = [
            (0, 0), (total_x, 0), (total_x, total_y), (0, total_y),
        ]

    # 标高
    sol.level_names = [f"F{i + 1}" for i in range(floors)] + ["Roof"]
    sol.level_elevations = [floor_height * i for i in range(floors)] + [floor_height * floors]

    # 核心筒位置推荐
    sol.core_zone = _recommend_core_zone(
        sol.x_grid_names, sol.x_grid_positions,
        sol.y_grid_names, sol.y_grid_positions,
        core_position,
    )

    # 中庭位置推荐
    if has_atrium:
        sol.atrium_zone = _recommend_atrium_zone(
            sol.x_grid_names, sol.x_grid_positions,
            sol.y_grid_names, sol.y_grid_positions,
            shape, cutout_corner,
        )

    # 入口墙推荐
    sol.entrance_wall = _recommend_entrance(
        sol.x_grid_positions, sol.y_grid_positions,
        entrance_direction,
    )

    # 面积偏差警告
    area_error = abs(sol.actual_area - area_per_floor) / area_per_floor
    if area_error > 0.05:
        sol.warnings.append(
            f"面积 {sol.actual_area:.1f} m² 偏差 {area_error * 100:+.1f}%"
        )

    return sol


# ── 新增: 多边形/圆形平面求解 ──

def _solve_polygon_design(
    sol: DesignSolution,
    floors: int,
    area_per_floor: float,
    max_span: float,
    floor_height: float,
    sides: int,
    center_x: float,
    center_y: float,
    entrance_direction: str,
) -> DesignSolution:
    """求解正多边形/圆形平面设计方案.

    从目标面积反算外接圆半径，生成多边形边界和环形柱位。
    """
    from aec_building.utils.geometry import regular_polygon_points, ring_positions

    sides = max(3, min(sides, 64))
    area_mm2 = area_per_floor * 1e6

    # 正 n 边形面积 = (n/2) * r² * sin(2π/n)
    radius = math.sqrt(area_mm2 / (sides / 2 * math.sin(2 * math.pi / sides)))
    sol.actual_area = (sides / 2 * radius ** 2 * math.sin(2 * math.pi / sides)) / 1e6

    # 入口朝向决定起始角度
    start_angle_map = {
        "south": 270 - 180 / sides,
        "north": 90 - 180 / sides,
        "east": 0 - 180 / sides,
        "west": 180 - 180 / sides,
    }
    start_angle = start_angle_map.get(entrance_direction, 270 - 180 / sides)

    # 楼板边界
    sol.floor_boundary = regular_polygon_points(center_x, center_y, radius, n=sides, start_angle=start_angle)

    # 轴网: 用外包矩形生成
    margin = radius * 1.1
    bbox_size = margin * 2
    max_span_mm = max_span * 1000
    n_grid = max(2, math.ceil(bbox_size / max_span_mm))
    grid_spacing = math.ceil(bbox_size / n_grid / 1000) * 1000

    x0 = center_x - grid_spacing * n_grid / 2
    y0 = center_y - grid_spacing * n_grid / 2
    sol.x_grid_names = [chr(ord("A") + i) for i in range(n_grid + 1)]
    sol.x_grid_positions = [x0 + grid_spacing * i for i in range(n_grid + 1)]
    sol.y_grid_names = [str(i + 1) for i in range(n_grid + 1)]
    sol.y_grid_positions = [y0 + grid_spacing * i for i in range(n_grid + 1)]

    # 标高
    sol.level_names = [f"F{i + 1}" for i in range(floors)] + ["Roof"]
    sol.level_elevations = [floor_height * i for i in range(floors)] + [floor_height * floors]

    # 柱位: 环形分布 (非矩形柱网)
    n_cols_outer = sides * 3  # 外圈
    n_cols_inner = sides      # 内圈
    outer_cols = ring_positions(center_x, center_y, radius * 0.85, n=n_cols_outer)
    inner_cols = ring_positions(center_x, center_y, radius * 0.5, n=n_cols_inner)
    sol.column_positions = outer_cols + inner_cols

    sol.entrance_wall = _recommend_entrance(
        sol.x_grid_positions, sol.y_grid_positions, entrance_direction,
    )

    return sol


def _solve_courtyard_design(
    sol: DesignSolution,
    floors: int,
    area_per_floor: float,
    max_span: float,
    floor_height: float,
    entrance_direction: str,
    core_position: str,
) -> DesignSolution:
    """求解院落式平面设计方案.

    外包矩形减去中央庭院，形成回字形或 U 字形布局。
    适用于四合院、宫殿围合、博物馆等。
    """
    area_mm2 = area_per_floor * 1e6
    max_span_mm = max_span * 1000

    # 院落式: 总面积 ≈ 外包面积 × 0.6 (庭院占 40%)
    outer_area = area_mm2 / 0.6
    ratio = 1.3
    outer_y = math.sqrt(outer_area / ratio)
    outer_x = outer_area / outer_y

    # 取整到柱距
    nx = max(3, math.ceil(outer_x / max_span_mm))
    ny = max(3, math.ceil(outer_y / max_span_mm))
    span_x = math.ceil(outer_x / nx / 1000) * 1000
    span_y = math.ceil(outer_y / ny / 1000) * 1000

    total_x = span_x * nx
    total_y = span_y * ny

    # 庭院: 内缩 1~2 跨
    court_margin_x = max(1, nx // 4)
    court_margin_y = max(1, ny // 4)
    court_x0 = span_x * court_margin_x
    court_y0 = span_y * court_margin_y
    court_x1 = total_x - span_x * court_margin_x
    court_y1 = total_y - span_y * court_margin_y

    inner_area = (court_x1 - court_x0) * (court_y1 - court_y0)
    sol.actual_area = (total_x * total_y - inner_area) / 1e6

    # 回字形边界 (8 点)
    sol.floor_boundary = [
        (0, 0), (total_x, 0), (total_x, total_y), (0, total_y),  # 外圈
        (0, court_y0),  # 回到内圈入口
        (court_x0, court_y0), (court_x0, court_y1),
        (court_x1, court_y1), (court_x1, court_y0),
        (0, court_y0),  # 回到外圈
    ]
    # 注: 回字形楼板需要特殊处理(外圈-内圈)，这里提供外圈和庭院区域信息
    # Agent 应将外圈作为楼板，庭院作为 opening

    sol.x_grid_names = [chr(ord("A") + i) for i in range(nx + 1)]
    sol.x_grid_positions = [span_x * i for i in range(nx + 1)]
    sol.y_grid_names = [str(i + 1) for i in range(ny + 1)]
    sol.y_grid_positions = [span_y * i for i in range(ny + 1)]

    sol.level_names = [f"F{i + 1}" for i in range(floors)] + ["Roof"]
    sol.level_elevations = [floor_height * i for i in range(floors)] + [floor_height * floors]

    # 庭院区域
    sol.atrium_zone = {
        "x_range": [sol.x_grid_names[court_margin_x],
                     sol.x_grid_names[nx - court_margin_x]],
        "y_range": [sol.y_grid_names[court_margin_y],
                     sol.y_grid_names[ny - court_margin_y]],
    }

    sol.core_zone = _recommend_core_zone(
        sol.x_grid_names, sol.x_grid_positions,
        sol.y_grid_names, sol.y_grid_positions,
        core_position,
    )
    sol.entrance_wall = _recommend_entrance(
        sol.x_grid_positions, sol.y_grid_positions, entrance_direction,
    )

    return sol


def _solve_custom_design(
    sol: DesignSolution,
    floors: int,
    area_per_floor: float,
    floor_height: float,
    custom_boundary: list[tuple[float, float]],
    entrance_direction: str,
) -> DesignSolution:
    """求解自定义边界平面设计方案.

    用户提供任意多边形边界，系统计算外包矩形轴网。
    """
    from aec_building.utils.geometry import polygon_area

    sol.floor_boundary = custom_boundary
    sol.actual_area = polygon_area(custom_boundary) / 1e6

    # 外包矩形轴网
    xs = [p[0] for p in custom_boundary]
    ys = [p[1] for p in custom_boundary]
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)

    # 自动生成轴网
    span = 9000.0  # 默认 9m 跨距
    nx = max(2, math.ceil((x_max - x_min) / span))
    ny = max(2, math.ceil((y_max - y_min) / span))
    actual_span_x = (x_max - x_min) / nx
    actual_span_y = (y_max - y_min) / ny

    sol.x_grid_names = [chr(ord("A") + i) for i in range(nx + 1)]
    sol.x_grid_positions = [x_min + actual_span_x * i for i in range(nx + 1)]
    sol.y_grid_names = [str(i + 1) for i in range(ny + 1)]
    sol.y_grid_positions = [y_min + actual_span_y * i for i in range(ny + 1)]

    sol.level_names = [f"F{i + 1}" for i in range(floors)] + ["Roof"]
    sol.level_elevations = [floor_height * i for i in range(floors)] + [floor_height * floors]

    sol.entrance_wall = _recommend_entrance(
        sol.x_grid_positions, sol.y_grid_positions, entrance_direction,
    )

    if area_per_floor > 0:
        area_error = abs(sol.actual_area - area_per_floor) / area_per_floor
        if area_error > 0.05:
            sol.warnings.append(
                f"自定义边界面积 {sol.actual_area:.1f} m² 与目标 {area_per_floor:.1f} m² "
                f"偏差 {area_error * 100:+.1f}%"
            )

    return sol


def _recommend_core_zone(
    x_names: list[str], x_pos: list[float],
    y_names: list[str], y_pos: list[float],
    position: str,
) -> dict:
    """推荐核心筒占用的轴网区间."""
    # 核心筒一般占 1-2 跨
    if position == "north":
        return {
            "x_range": [x_names[0], x_names[min(1, len(x_names) - 1)]],
            "y_range": [y_names[-2] if len(y_names) > 1 else y_names[0], y_names[-1]],
        }
    elif position == "south":
        return {
            "x_range": [x_names[0], x_names[min(1, len(x_names) - 1)]],
            "y_range": [y_names[0], y_names[min(1, len(y_names) - 1)]],
        }
    elif position == "east":
        return {
            "x_range": [x_names[-2] if len(x_names) > 1 else x_names[0], x_names[-1]],
            "y_range": [y_names[0], y_names[min(1, len(y_names) - 1)]],
        }
    else:  # west
        return {
            "x_range": [x_names[0], x_names[min(1, len(x_names) - 1)]],
            "y_range": [y_names[0], y_names[min(1, len(y_names) - 1)]],
        }


def _recommend_atrium_zone(
    x_names: list[str], x_pos: list[float],
    y_names: list[str], y_pos: list[float],
    shape: str, cutout_corner: str,
) -> dict:
    """推荐中庭位置 — 在 L 形拐角处或建筑中心."""
    if shape == "L":
        # L 形建筑中庭放在拐角附近
        mid_x = len(x_names) // 2
        mid_y = len(y_names) // 2
        return {
            "x_range": [x_names[max(0, mid_x - 1)], x_names[min(mid_x, len(x_names) - 1)]],
            "y_range": [y_names[max(0, mid_y - 1)], y_names[min(mid_y, len(y_names) - 1)]],
        }
    else:
        # 矩形建筑中庭放在中心
        mid_x = len(x_names) // 2
        mid_y = len(y_names) // 2
        return {
            "x_range": [x_names[max(0, mid_x - 1)], x_names[min(mid_x, len(x_names) - 1)]],
            "y_range": [y_names[max(0, mid_y - 1)], y_names[min(mid_y, len(y_names) - 1)]],
        }


def _recommend_entrance(
    x_pos: list[float], y_pos: list[float],
    direction: str,
) -> dict:
    """推荐入口幕墙位置."""
    if direction == "south":
        return {"start": [x_pos[0], y_pos[0]], "end": [x_pos[-1], y_pos[0]], "direction": "south"}
    elif direction == "north":
        return {"start": [x_pos[0], y_pos[-1]], "end": [x_pos[-1], y_pos[-1]], "direction": "north"}
    elif direction == "east":
        return {"start": [x_pos[-1], y_pos[0]], "end": [x_pos[-1], y_pos[-1]], "direction": "east"}
    else:  # west
        return {"start": [x_pos[0], y_pos[0]], "end": [x_pos[0], y_pos[-1]], "direction": "west"}


def solve_l_shape_dimensions(
    target_area: float,
    max_span: float,
    area_tolerance: float = 0.05,
    cutout_corner: str = "NE",
) -> LShapeSolution:
    """求解 L 形平面尺寸.

    对应案例 Tool Call 2 中的几何推理：
    ```
    32×20 + 32×20 - 20×20 = 640 + 640 - 400 = 880 m² ≈ 800 ± 5% ✓
    ```

    Args:
        target_area: 目标面积 (m²)。
        max_span: 最大柱距 (m)。
        area_tolerance: 面积容差（默认 5%）。
        cutout_corner: 切除角位置。

    Returns:
        L 形平面尺寸解。
    """
    max_span_mm = max_span * 1000
    target_area_mm2 = target_area * 1e6

    # 搜索策略：从合理比例出发，逐步调整
    # L 形 = 大矩形 - 切除矩形
    # 约束：所有边长必须是柱距整数倍

    best_solution = None
    best_error = float("inf")

    # 尝试不同的整体尺寸组合
    for nx in range(3, 8):  # X 方向跨数
        for ny in range(2, 6):  # Y 方向跨数
            for sx in _feasible_spans(max_span_mm, nx):
                for sy in _feasible_spans(max_span_mm, ny):
                    total_x = sum(sx)
                    total_y = sum(sy)

                    # 切除部分：尝试 L 形的不同切口比例
                    for cx_spans in range(1, nx):
                        for cy_spans in range(1, ny):
                            cutout_x = sum(sx[nx - cx_spans:])
                            cutout_y = sum(sy[ny - cy_spans:])

                            area = total_x * total_y - cutout_x * cutout_y
                            area_m2 = area / 1e6
                            error = abs(area_m2 - target_area) / target_area

                            if error < best_error and error <= area_tolerance:
                                best_error = error
                                best_solution = LShapeSolution(
                                    total_x=total_x,
                                    total_y=total_y,
                                    cutout_x=cutout_x,
                                    cutout_y=cutout_y,
                                    actual_area=area_m2,
                                    x_spans=list(sx),
                                    y_spans=list(sy),
                                )

    if best_solution is None:
        # 回退：使用近似解
        side = math.sqrt(target_area_mm2 * 1.3)  # L 形比矩形大 ~30%
        n_spans = max(3, math.ceil(side / max_span_mm))
        span = side / n_spans
        total_x = span * (n_spans + 1)
        total_y = span * n_spans
        cutout_x = span * max(1, n_spans // 2)
        cutout_y = span * max(1, (n_spans - 1) // 2)

        actual_area = (total_x * total_y - cutout_x * cutout_y) / 1e6
        best_solution = LShapeSolution(
            total_x=total_x,
            total_y=total_y,
            cutout_x=cutout_x,
            cutout_y=cutout_y,
            actual_area=actual_area,
            x_spans=[span] * (n_spans + 1),
            y_spans=[span] * n_spans,
            warnings=["使用近似解，未找到精确整跨组合"],
        )

    return best_solution


def _feasible_spans(max_span: float, count: int) -> list[tuple[float, ...]]:
    """生成满足柱距约束的跨距组合.

    简化策略：使用 6m、7m、8m 三种常用跨距。
    """
    common_spans = [6000.0, 7000.0, 8000.0]
    valid = [s for s in common_spans if s <= max_span]

    if not valid:
        return []

    # 生成均匀跨距组合
    results = []
    for s in valid:
        results.append(tuple([s] * count))

    # 混合跨距（首尾不同）
    if len(valid) >= 2:
        for s1 in valid:
            for s2 in valid:
                if s1 != s2 and count >= 2:
                    combo = [s1] + [s2] * (count - 2) + [s1] if count > 2 else [s1, s2]
                    results.append(tuple(combo))

    return results


def validate_constraints(
    constraints: ConstraintSet,
    building_summary: dict,
) -> list[dict]:
    """验证建筑是否满足约束集.

    对每条约束检查是否满足，返回结构化结果。

    Args:
        constraints: 约束集合。
        building_summary: 建筑状态摘要 (Building.summary())。

    Returns:
        约束验证结果列表，每项包含 constraint, expected, actual, passed, note。
    """
    results = []

    for c in constraints.constraints:
        result = {"constraint": c.name, "type": c.constraint_type.value,
                  "expected": c.value, "source": c.source.value}

        if c.constraint_type == ConstraintType.HEIGHT and c.name == "层数":
            actual = building_summary.get("slab_count", 0)
            passed = actual == c.value
            result.update({"actual": actual, "passed": passed})

        elif c.constraint_type == ConstraintType.AREA and c.name == "每层面积":
            actual = building_summary.get("area_per_floor", 0)
            if actual > 0 and isinstance(c.value, (int, float)):
                passed = c.check_numeric(actual)
                result.update({
                    "actual": actual,
                    "passed": passed,
                    "note": f"偏差 {(actual - c.value) / c.value * 100:+.1f}%" if not passed else "",
                })
            else:
                result.update({"actual": actual, "passed": None, "note": "待验证"})

        elif c.constraint_type == ConstraintType.SHAPE:
            # 形状由楼板边界隐含，无法直接从 summary 验证
            result.update({"actual": "见楼板边界", "passed": None, "note": "需视觉确认"})

        elif c.constraint_type == ConstraintType.SPAN:
            # 柱距由轴网间距决定
            result.update({"actual": "见轴网间距", "passed": None, "note": "需检查轴网"})

        elif c.constraint_type == ConstraintType.FUNCTION and c.value == "atrium_required":
            has_atrium = building_summary.get("opening_count", 0) > 0
            result.update({"actual": has_atrium, "passed": has_atrium})

        elif c.constraint_type == ConstraintType.CODE and c.name == "最少疏散楼梯数":
            actual = building_summary.get("staircase_count", 0)
            passed = actual >= c.value if isinstance(c.value, (int, float)) else None
            result.update({"actual": actual, "passed": passed})

        elif c.constraint_type == ConstraintType.CODE and c.name == "防火分区":
            area = building_summary.get("area_per_floor", 0)
            passed = area < 2500 if area > 0 else None
            result.update({"actual": f"{area} m²", "passed": passed})

        elif c.constraint_type == ConstraintType.HEIGHT and c.name == "建筑总高":
            levels = building_summary.get("levels", [])
            if levels:
                # summary 只有名称，无法直接计算高度
                result.update({"actual": f"{len(levels)} 个标高", "passed": None, "note": "需检查标高"})
            else:
                result.update({"actual": 0, "passed": None})

        else:
            result.update({"actual": None, "passed": None, "note": "无法自动验证"})

        results.append(result)

    return results
