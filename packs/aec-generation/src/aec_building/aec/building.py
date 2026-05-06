"""建筑聚合模型 — 管理完整建筑的所有构件及其参数化依赖.

对应案例 Tool Call 11 展示的连锁修改机制：修改核心筒边界后，
相关墙体自动延长、中庭洞口自动更新。

设计原则：
- 维护轻量依赖图，修改触发连锁重算
- 所有构件通过 ID 索引，支持增删改查
- 状态摘要用于 Agent 上下文压缩（案例第七节）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from aec_building.aec.elements import Beam, Column, CurtainWall, CurvedRoof, Door, FloorSlab, Railing, RoundColumn, Wall, Window
from aec_building.aec.grid import GridSystem
from aec_building.aec.staircase import Staircase
from aec_building.core.references import GridRangeRef, LevelRef

_POINT_TOLERANCE = 1.0  # mm


def _points_close(
    a: tuple[float, float],
    b: tuple[float, float] | list[float],
) -> bool:
    """两个 2D 点是否在容差内相等."""
    return abs(a[0] - b[0]) <= _POINT_TOLERANCE and abs(a[1] - b[1]) <= _POINT_TOLERANCE


@dataclass
class BuildingElement:
    """建筑构件包装器 — 将元素与其 ID、依赖关系绑定."""

    id: str
    element: Column | Wall | FloorSlab
    depends_on: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Opening:
    """楼板开洞定义 — 参照驱动的中庭/电梯井开洞.

    对应案例 Tool Call 6：用轴网参照定义开洞边界，
    而非绝对坐标，确保参数化可维护性。
    """

    id: str
    ref: GridRangeRef
    target_slabs: list[str]  # 关联的楼板 ID 列表
    connect_to_roof: bool = False


@dataclass
class Building:
    """建筑模型聚合体.

    管理轴网、标高、所有构件及其依赖关系。
    提供批量操作和状态摘要能力。
    """

    name: str
    grid: GridSystem
    _elements: dict[str, BuildingElement] = field(default_factory=dict)
    _openings: dict[str, Opening] = field(default_factory=dict)
    _staircases: dict[str, Staircase] = field(default_factory=dict)
    _id_counter: int = field(default=0)

    def _next_id(self, prefix: str) -> str:
        self._id_counter += 1
        return f"{prefix}_{self._id_counter:04d}"

    # ── 楼板操作 ──

    def add_slab(self, slab: FloorSlab, depends_on: list[str] | None = None) -> str:
        """添加楼板，返回元素 ID."""
        eid = self._next_id("slab")
        self._elements[eid] = BuildingElement(
            id=eid,
            element=slab,
            depends_on=depends_on or [],
        )
        return eid

    def add_slabs_for_levels(
        self,
        boundary_points: list[tuple[float, float]],
        levels: list[str],
        thickness: float = 150.0,
    ) -> list[str]:
        """在多个标高上创建相同轮廓的楼板.

        对应案例 Tool Call 4+5：创建楼板 → 复制到其他层。

        Returns:
            楼板 ID 列表。
        """
        ids = []
        for level in levels:
            slab = FloorSlab(
                level=level,
                boundary_points=boundary_points,
                thickness=thickness,
            )
            ids.append(self.add_slab(slab))
        return ids

    # ── 柱子操作 ──

    def add_column(self, column: Column, depends_on: list[str] | None = None) -> str:
        eid = self._next_id("col")
        self._elements[eid] = BuildingElement(
            id=eid,
            element=column,
            depends_on=depends_on or [],
        )
        return eid

    def place_columns_on_grid(
        self,
        base_level: str,
        top_level: str,
        skip_x: set[str] | None = None,
        skip_y: set[str] | None = None,
        section_width: float = 305.0,
        section_depth: float = 305.0,
    ) -> list[str]:
        """在轴网交点批量放置柱子，跳过指定区域.

        对应案例 Tool Call 7（案例 4.1 粗粒度原则）：
        一次调用放置所有柱子，循环在此方法内部。

        Args:
            base_level: 柱底标高名。
            top_level: 柱顶标高名。
            skip_x: 要跳过的 X 轴线集合。
            skip_y: 要跳过的 Y 轴线集合。

        Returns:
            柱子 ID 列表。
        """
        skip_x = skip_x or set()
        skip_y = skip_y or set()
        ids = []

        for xn, xv in self.grid.x_grids.items():
            for yn, yv in self.grid.y_grids.items():
                if xn in skip_x and yn in skip_y:
                    continue
                col = Column(
                    x=xv, y=yv,
                    base_level=base_level,
                    top_level=top_level,
                    section_width=section_width,
                    section_depth=section_depth,
                )
                ids.append(self.add_column(col))

        return ids

    # ── 墙体操作 ──

    def add_wall(self, wall: Wall, depends_on: list[str] | None = None) -> str:
        eid = self._next_id("wall")
        self._elements[eid] = BuildingElement(
            id=eid,
            element=wall,
            depends_on=depends_on or [],
        )
        return eid

    # ── 梁操作 ──

    def add_beam(self, beam: Beam, depends_on: list[str] | None = None) -> str:
        """添加结构梁，返回元素 ID."""
        eid = self._next_id("beam")
        self._elements[eid] = BuildingElement(
            id=eid, element=beam, depends_on=depends_on or [],
        )
        return eid

    @property
    def beams(self) -> list[BuildingElement]:
        return self.get_elements_by_type(Beam)

    def auto_place_beams(
        self,
        level: str,
        beam_width: float = 300.0,
        beam_height: float = 600.0,
    ) -> list[str]:
        """在轴网交点间自动放置梁（沿 X 和 Y 方向）.

        粗粒度操作：一次 tool call 放置所有梁。

        Args:
            level: 梁所属标高。
            beam_width: 截面宽 (mm)。
            beam_height: 截面高 (mm)。

        Returns:
            梁 ID 列表。
        """
        beam_ids = []
        x_names = list(self.grid.x_grids.keys())
        y_names = list(self.grid.y_grids.keys())

        # X 方向梁（沿每条 Y 轴线，连接相邻 X 轴线交点）
        for y_name in y_names:
            for i in range(len(x_names) - 1):
                x1 = self.grid.x_grids[x_names[i]]
                x2 = self.grid.x_grids[x_names[i + 1]]
                y = self.grid.y_grids[y_name]
                beam = Beam(
                    start=(x1, y), end=(x2, y),
                    level=level, width=beam_width, height=beam_height,
                )
                beam_ids.append(self.add_beam(beam))

        # Y 方向梁（沿每条 X 轴线，连接相邻 Y 轴线交点）
        for x_name in x_names:
            for j in range(len(y_names) - 1):
                x = self.grid.x_grids[x_name]
                y1 = self.grid.y_grids[y_names[j]]
                y2 = self.grid.y_grids[y_names[j + 1]]
                beam = Beam(
                    start=(x, y1), end=(x, y2),
                    level=level, width=beam_width, height=beam_height,
                )
                beam_ids.append(self.add_beam(beam))

        return beam_ids

    # ── 幕墙操作 ──

    def add_curtain_wall(self, cw: CurtainWall, depends_on: list[str] | None = None) -> str:
        """添加幕墙，返回元素 ID. 对应案例 TC 13."""
        eid = self._next_id("curtain")
        self._elements[eid] = BuildingElement(
            id=eid, element=cw, depends_on=depends_on or [],
        )
        return eid

    @property
    def curtain_walls(self) -> list[BuildingElement]:
        return self.get_elements_by_type(CurtainWall)

    # ── 门窗操作 ──

    def add_door(self, door: Door, depends_on: list[str] | None = None) -> str:
        """添加门，返回元素 ID. 对应案例 TC 15."""
        eid = self._next_id("door")
        self._elements[eid] = BuildingElement(
            id=eid, element=door, depends_on=depends_on or [door.host_wall_id],
        )
        return eid

    def add_window(self, window: Window, depends_on: list[str] | None = None) -> str:
        """添加窗户."""
        eid = self._next_id("win")
        self._elements[eid] = BuildingElement(
            id=eid, element=window, depends_on=depends_on or [window.host_wall_id],
        )
        return eid

    # ── LOD 300: 圆柱、曲面屋顶、栏杆 ──

    def add_round_column(self, column: RoundColumn, depends_on: list[str] | None = None) -> str:
        """添加圆柱，返回元素 ID."""
        eid = self._next_id("rcol")
        self._elements[eid] = BuildingElement(
            id=eid, element=column, depends_on=depends_on or [],
        )
        return eid

    @property
    def round_columns(self) -> list[BuildingElement]:
        return self.get_elements_by_type(RoundColumn)

    def add_curved_roof(self, roof: CurvedRoof, depends_on: list[str] | None = None) -> str:
        """添加曲面屋顶，返回元素 ID."""
        eid = self._next_id("roof")
        self._elements[eid] = BuildingElement(
            id=eid, element=roof, depends_on=depends_on or [],
        )
        return eid

    @property
    def curved_roofs(self) -> list[BuildingElement]:
        return self.get_elements_by_type(CurvedRoof)

    def add_railing(self, railing: Railing, depends_on: list[str] | None = None) -> str:
        """添加栏杆，返回元素 ID."""
        eid = self._next_id("rail")
        self._elements[eid] = BuildingElement(
            id=eid, element=railing, depends_on=depends_on or [],
        )
        return eid

    @property
    def railings(self) -> list[BuildingElement]:
        return self.get_elements_by_type(Railing)

    def auto_place_doors(
        self,
        door_spacing: float = 4000.0,
        door_width: float = 900.0,
        door_height: float = 2100.0,
    ) -> list[str]:
        """在所有内墙上按间距自动放置门. 对应案例 TC 15.

        Args:
            door_spacing: 门间距 (mm)。
            door_width: 门宽 (mm)。
            door_height: 门高 (mm)。

        Returns:
            门 ID 列表。
        """
        import math
        door_ids = []
        for be in self.walls:
            wall = be.element
            if wall.wall_type.value in ("interior", "fire"):
                sx, sy = wall.start
                ex, ey = wall.end
                length = math.sqrt((ex - sx) ** 2 + (ey - sy) ** 2)
                num_doors = max(1, int(length / door_spacing))
                for i in range(num_doors):
                    pos = (i + 0.5) / num_doors
                    door = Door(
                        host_wall_id=be.id,
                        position=pos,
                        width=door_width,
                        height=door_height,
                    )
                    door_ids.append(self.add_door(door, depends_on=[be.id]))
        return door_ids

    # ── 楼梯操作 ──

    def add_staircase(self, staircase: Staircase) -> str:
        """添加楼梯构件，返回楼梯 ID."""
        sid = self._next_id("stair")
        self._staircases[sid] = staircase
        return sid

    @property
    def staircases(self) -> list[tuple[str, Staircase]]:
        return list(self._staircases.items())

    # ── 开洞操作 ──

    def add_opening(
        self,
        ref: GridRangeRef,
        target_slab_ids: list[str],
        connect_to_roof: bool = False,
    ) -> str:
        """添加基于轴网参照的开洞.

        对应案例 Tool Call 6：中庭开洞使用轴网参照而非坐标。
        """
        oid = self._next_id("opening")
        self._openings[oid] = Opening(
            id=oid,
            ref=ref,
            target_slabs=target_slab_ids,
            connect_to_roof=connect_to_roof,
        )
        return oid

    # ── 修改操作 ──

    def modify_element(self, element_id: str, **changes: Any) -> list[str]:
        """修改构件参数，返回受影响的依赖构件 ID 列表.

        对应案例 Tool Call 9/11：修改核心筒墙参数，
        触发参数化连锁更新。

        Args:
            element_id: 要修改的构件 ID。
            **changes: 要修改的属性名-值对。

        Returns:
            受影响的构件 ID 列表（含自身）。
        """
        if element_id not in self._elements:
            raise KeyError(f"Element {element_id} not found")

        elem = self._elements[element_id]
        old_values = {}
        for attr, value in changes.items():
            if hasattr(elem.element, attr):
                old_values[attr] = getattr(elem.element, attr)
                setattr(elem.element, attr, value)

        # 查找所有依赖此构件的元素
        affected = [element_id]
        for eid, be in self._elements.items():
            if element_id in be.depends_on and eid != element_id:
                affected.append(eid)

        # 参数化联动：墙端点变更时自动延长相交墙
        if isinstance(elem.element, Wall):
            cascade = self._propagate_wall_changes(element_id, old_values, changes)
            affected.extend(cascade)

        return affected

    def _propagate_wall_changes(
        self,
        wall_id: str,
        old_values: dict,
        new_values: dict,
    ) -> list[str]:
        """墙体修改的参数化联动.

        对应案例 TC11：核心筒南墙南移 → 东墙/西墙自动延长。

        规则：
        - 当墙的 start 或 end 改变时，检查其他墙是否与旧端点相交
        - 如果相交墙的某端点恰好落在旧端点上，更新到新端点
        """
        cascaded = []
        modified_wall = self._elements[wall_id].element

        for attr in ("start", "end"):
            if attr not in new_values or attr not in old_values:
                continue

            old_pt = old_values[attr]
            new_pt = new_values[attr]
            if not isinstance(old_pt, (tuple, list)) or not isinstance(new_pt, (tuple, list)):
                continue
            if tuple(old_pt) == tuple(new_pt):
                continue

            # 查找其他墙中端点与 old_pt 匹配的
            for eid, be in self._elements.items():
                if eid == wall_id or not isinstance(be.element, Wall):
                    continue

                other = be.element
                updated = False

                if _points_close(other.start, old_pt):
                    other.start = tuple(new_pt)
                    updated = True
                if _points_close(other.end, old_pt):
                    other.end = tuple(new_pt)
                    updated = True

                if updated and eid not in cascaded:
                    cascaded.append(eid)

        return cascaded

    # ── 查询操作 ──

    def get_element(self, element_id: str) -> BuildingElement:
        return self._elements[element_id]

    def get_elements_by_type(self, element_type: type) -> list[BuildingElement]:
        return [
            be for be in self._elements.values()
            if isinstance(be.element, element_type)
        ]

    @property
    def columns(self) -> list[BuildingElement]:
        return self.get_elements_by_type(Column)

    @property
    def walls(self) -> list[BuildingElement]:
        return self.get_elements_by_type(Wall)

    @property
    def slabs(self) -> list[BuildingElement]:
        return self.get_elements_by_type(FloorSlab)

    @property
    def openings(self) -> list[Opening]:
        return list(self._openings.values())

    # ── 状态摘要（用于 Agent 上下文压缩）──

    def summary(self) -> dict[str, Any]:
        """生成建筑状态摘要.

        对应案例第七节讨论的上下文管理问题：
        返回摘要而非完整几何，节省 Agent 上下文 token。
        """
        slab_levels = [be.element.level for be in self.slabs]
        col_count = len(self.columns)
        wall_count = len(self.walls)

        # 动态计算每层面积
        area_per_floor = 0.0
        if self.slabs:
            from aec_building.aec.element_factory import _polygon_area
            area_per_floor = round(_polygon_area(self.slabs[0].element.boundary_points), 1)

        return {
            "name": self.name,
            "grid_x": list(self.grid.x_grids.keys()),
            "grid_y": list(self.grid.y_grids.keys()),
            "levels": list(self.grid.levels.keys()),
            "slab_count": len(self.slabs),
            "slab_levels": slab_levels,
            "area_per_floor": area_per_floor,
            "column_count": col_count,
            "beam_count": len(self.beams),
            "wall_count": wall_count,
            "curtain_wall_count": len(self.curtain_walls),
            "door_count": len(self.get_elements_by_type(Door)),
            "window_count": len(self.get_elements_by_type(Window)),
            "round_column_count": len(self.round_columns),
            "curved_roof_count": len(self.curved_roofs),
            "railing_count": len(self.railings),
            "opening_count": len(self._openings),
            "staircase_count": len(self._staircases),
            "total_elements": len(self._elements) + len(self._staircases),
        }

    # ── BREP 生成（Sprint 2 核心）──

    def generate_brep(self) -> dict[str, object]:
        """将所有构件转换为 CadQuery BREP 实体并执行布尔运算.

        打通 Building(数据) → element_factory(BREP) → 可导出实体 的管线。
        需要 CadQuery 环境。

        Returns:
            字典 {element_id: CadQuery Workplane}，含所有可导出的实体。
        """
        from aec_building.aec.element_factory import (
            batch_beams_to_brep,
            batch_columns_to_brep,
            batch_railings_to_brep,
            batch_round_columns_to_brep,
            batch_walls_to_brep,
            curtain_wall_to_brep,
            curved_roof_to_brep,
            slab_to_brep,
        )
        from aec_building.core.booleans import boolean_cut, make_opening_tool

        results: dict[str, object] = {}

        # 1. 楼板
        slab_results = {}
        for be in self.slabs:
            br = slab_to_brep(be.element, self.grid)
            if br.geometry_valid and br.shape is not None:
                slab_results[be.id] = br
                results[be.id] = br.shape

        # 2. 开洞布尔减（在楼板上执行）
        for opening in self.openings:
            bounds = opening.ref.resolve(self.grid)
            x_min, y_min, x_max, y_max = bounds

            for slab_id in opening.target_slabs:
                if slab_id in results:
                    # 获取楼板标高和厚度
                    slab_be = self._elements[slab_id]
                    slab_elem = slab_be.element
                    elev = self.grid.level_elevation(slab_elem.level)

                    tool = make_opening_tool(
                        x_min=x_min, y_min=y_min,
                        x_max=x_max, y_max=y_max,
                        z_base=elev - 10,  # 穿透余量
                        z_height=slab_elem.thickness + 20,
                    )
                    results[slab_id] = boolean_cut(results[slab_id], tool)

        # 3. 柱子
        col_elements = [be.element for be in self.columns]
        if col_elements:
            col_results = batch_columns_to_brep(col_elements, self.grid)
            for br in col_results:
                if br.geometry_valid and br.shape is not None:
                    results[br.element_id] = br.shape

        # 4. 墙体
        wall_elements = [be.element for be in self.walls]
        if wall_elements:
            wall_results = batch_walls_to_brep(wall_elements, self.grid)
            for br in wall_results:
                if br.geometry_valid and br.shape is not None:
                    results[br.element_id] = br.shape

        # 5. 梁
        beam_elements = [be.element for be in self.beams]
        if beam_elements:
            beam_results = batch_beams_to_brep(beam_elements, self.grid)
            for br in beam_results:
                if br.geometry_valid and br.shape is not None:
                    results[br.element_id] = br.shape

        # 6. 幕墙
        for be in self.curtain_walls:
            try:
                br = curtain_wall_to_brep(be.element, self.grid)
                if br.geometry_valid and br.shape is not None:
                    results[be.id] = br.shape
            except Exception:
                pass

        # 7. 圆柱 (LOD 300)
        rcol_elements = [be.element for be in self.round_columns]
        if rcol_elements:
            rcol_results = batch_round_columns_to_brep(rcol_elements, self.grid)
            for br in rcol_results:
                if br.geometry_valid and br.shape is not None:
                    results[br.element_id] = br.shape

        # 8. 曲面屋顶 (LOD 300)
        for be in self.curved_roofs:
            try:
                br = curved_roof_to_brep(be.element, self.grid)
                if br.geometry_valid and br.shape is not None:
                    results[be.id] = br.shape
            except Exception:
                pass

        # 9. 栏杆 (LOD 300)
        rail_elements = [be.element for be in self.railings]
        if rail_elements:
            rail_results = batch_railings_to_brep(rail_elements, self.grid)
            for br in rail_results:
                if br.geometry_valid and br.shape is not None:
                    results[br.element_id] = br.shape

        # 10. 楼梯
        for stair_id, staircase in self.staircases:
            try:
                base_z = staircase.base_level.resolve(self.grid)
                top_z = staircase.top_level.resolve(self.grid)
                total_rise = top_z - base_z
                shape = staircase.to_brep(self.grid, total_rise)
                if shape is not None:
                    results[stair_id] = shape
            except Exception:
                pass  # 楼梯 BREP 失败不阻塞其他构件

        return results

    def export_to_step(self, output_path: str) -> str:
        """生成 BREP 并导出为 STEP 文件.

        端到端快捷方法：generate_brep() → 组装 → export。

        Args:
            output_path: 输出文件路径。

        Returns:
            写入的文件路径。
        """
        import cadquery as cq

        from aec_building.export.step_export import export_to_step

        brep_shapes = self.generate_brep()
        if not brep_shapes:
            raise RuntimeError("No BREP shapes generated")

        # 用 CadQuery Assembly 组装所有构件
        assembly = cq.Assembly()
        for eid, shape in brep_shapes.items():
            assembly.add(shape, name=eid)

        # 导出整个 Assembly
        from pathlib import Path
        filepath = Path(output_path)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        assembly.save(str(filepath), "STEP")
        return str(filepath)

    # ── 状态管理（Sprint 4）──

    def snapshot(self) -> dict[str, Any]:
        """将当前状态序列化为可传输的 dict.

        用于 Agent 上下文保存、回滚、多 Agent 状态同步。
        """
        from aec_building.aec.state import serialize_building
        return serialize_building(self)

    @classmethod
    def restore(cls, state: dict[str, Any]) -> Building:
        """从 dict 重建 Building 实例.

        Args:
            state: snapshot() 返回的 dict。

        Returns:
            新的 Building 实例。
        """
        from aec_building.aec.state import deserialize_building
        return deserialize_building(state)

    def diff_from(self, other_state: dict[str, Any]) -> Any:
        """计算当前状态与另一个状态的差异.

        Args:
            other_state: 另一个 Building 的 snapshot。

        Returns:
            StateDiff 对象。
        """
        from aec_building.aec.state import compute_diff
        return compute_diff(other_state, self.snapshot())
