"""Building 状态管理 — 快照、恢复、差异比较.

对应案例 §7.1（上下文管理）和 §7.2（状态 diff/branch/rollback）：
- snapshot(): 将 Building 完整状态序列化为可传输的 dict
- restore(): 从 dict 重建 Building 实例
- diff(): 计算两个快照之间的变更集
- branch/rollback: 基于快照链的版本管理

设计原则：
- 序列化不依赖 pickle（安全 + 可传输）
- 快照为纯 dict，可 JSON 序列化
- diff 输出可被 Agent 直接阅读（人/机双可读）
"""

from __future__ import annotations

import copy
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Snapshot:
    """Building 状态快照.

    Attributes:
        version: 快照版本号（自增）。
        timestamp: 创建时间戳。
        name: 快照名称（如 "after_columns"）。
        state: Building 完整状态的 dict 表示。
        parent_version: 父快照版本号（用于分支追溯）。
    """

    version: int
    timestamp: float
    name: str
    state: dict[str, Any]
    parent_version: int | None = None

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, data: str) -> Snapshot:
        d = json.loads(data)
        return cls(**d)


@dataclass
class StateDiff:
    """两个快照之间的差异.

    Agent 可直接阅读此输出来理解"上次之后发生了什么"。
    """

    from_version: int
    to_version: int
    added_elements: list[str] = field(default_factory=list)
    removed_elements: list[str] = field(default_factory=list)
    modified_elements: list[dict[str, Any]] = field(default_factory=list)
    grid_changes: list[str] = field(default_factory=list)
    summary_changes: dict[str, Any] = field(default_factory=dict)

    def is_empty(self) -> bool:
        return (
            not self.added_elements
            and not self.removed_elements
            and not self.modified_elements
            and not self.grid_changes
        )

    def to_text(self) -> str:
        """生成人/机双可读的差异文本."""
        lines = [f"Diff: v{self.from_version} → v{self.to_version}"]
        if self.added_elements:
            lines.append(f"  Added: {', '.join(self.added_elements)}")
        if self.removed_elements:
            lines.append(f"  Removed: {', '.join(self.removed_elements)}")
        for m in self.modified_elements:
            lines.append(f"  Modified {m['id']}: {m.get('changes', {})}")
        if self.grid_changes:
            lines.append(f"  Grid: {', '.join(self.grid_changes)}")
        if self.summary_changes:
            lines.append(f"  Summary delta: {self.summary_changes}")
        if self.is_empty():
            lines.append("  (no changes)")
        return "\n".join(lines)


class StateManager:
    """Building 状态管理器 — 快照链 + 分支 + 回滚.

    每个 StateManager 绑定一个 Building 实例。
    快照链按版本号顺序排列，支持：
    - take_snapshot(): 保存当前状态
    - rollback(version): 恢复到指定版本
    - diff(v1, v2): 比较两个版本
    - save/load: 持久化到文件
    """

    def __init__(self) -> None:
        self._snapshots: dict[int, Snapshot] = {}
        self._next_version: int = 1

    @property
    def versions(self) -> list[int]:
        return sorted(self._snapshots.keys())

    @property
    def latest_version(self) -> int | None:
        return max(self._snapshots.keys()) if self._snapshots else None

    def take_snapshot(
        self,
        building: Any,  # Building（避免循环导入）
        name: str = "",
    ) -> Snapshot:
        """保存 Building 当前状态为快照."""
        state = serialize_building(building)
        parent = self.latest_version

        snap = Snapshot(
            version=self._next_version,
            timestamp=time.time(),
            name=name or f"snapshot_v{self._next_version}",
            state=state,
            parent_version=parent,
        )
        self._snapshots[snap.version] = snap
        self._next_version += 1
        return snap

    def get_snapshot(self, version: int) -> Snapshot:
        if version not in self._snapshots:
            raise KeyError(f"Snapshot version {version} not found")
        return self._snapshots[version]

    def rollback(self, version: int) -> Any:
        """从快照恢复 Building 实例.

        Returns:
            新的 Building 实例（不修改原实例）。
        """
        snap = self.get_snapshot(version)
        return deserialize_building(snap.state)

    def diff(self, from_version: int, to_version: int) -> StateDiff:
        """计算两个版本之间的差异."""
        snap_a = self.get_snapshot(from_version)
        snap_b = self.get_snapshot(to_version)
        return compute_diff(snap_a.state, snap_b.state, from_version, to_version)

    def save_to_file(self, filepath: str | Path) -> None:
        """将所有快照持久化到 JSON 文件."""
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "next_version": self._next_version,
            "snapshots": {
                str(v): asdict(s) for v, s in self._snapshots.items()
            },
        }
        filepath.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    def load_from_file(self, filepath: str | Path) -> None:
        """从文件加载快照链."""
        filepath = Path(filepath)
        data = json.loads(filepath.read_text())
        self._next_version = data["next_version"]
        self._snapshots = {
            int(v): Snapshot(**s)
            for v, s in data["snapshots"].items()
        }


# ── 序列化/反序列化 ──

def serialize_building(building: Any) -> dict[str, Any]:
    """将 Building 完整状态序列化为 dict.

    处理嵌套的 dataclass、Enum、tuple 等类型。
    """
    from aec_building.aec.building import Building

    state: dict[str, Any] = {
        "name": building.name,
        "grid": {
            "x_grids": dict(building.grid.x_grids),
            "y_grids": dict(building.grid.y_grids),
            "levels": dict(building.grid.levels),
        },
        "id_counter": building._id_counter,
        "elements": {},
        "openings": {},
        "staircases": {},
    }

    # 序列化构件
    for eid, be in building._elements.items():
        elem = be.element
        elem_data = _serialize_element(elem)
        state["elements"][eid] = {
            "id": be.id,
            "type": type(elem).__name__,
            "data": elem_data,
            "depends_on": list(be.depends_on),
            "metadata": dict(be.metadata),
        }

    # 序列化开洞
    for oid, opening in building._openings.items():
        state["openings"][oid] = {
            "id": opening.id,
            "ref": {
                "x_grid_start": opening.ref.x_grid_start,
                "x_grid_end": opening.ref.x_grid_end,
                "y_grid_start": opening.ref.y_grid_start,
                "y_grid_end": opening.ref.y_grid_end,
                "inset": opening.ref.inset,
            },
            "target_slabs": list(opening.target_slabs),
            "connect_to_roof": opening.connect_to_roof,
        }

    # 序列化楼梯
    for sid, stair in building._staircases.items():
        state["staircases"][sid] = {
            "location": {
                "x_grid": stair.location.x_grid,
                "y_grid": stair.location.y_grid,
                "offset_x": stair.location.offset_x,
                "offset_y": stair.location.offset_y,
            },
            "base_level": {
                "level": stair.base_level.level,
                "offset": stair.base_level.offset,
            },
            "top_level": {
                "level": stair.top_level.level,
                "offset": stair.top_level.offset,
            },
            "spec": {
                "riser_height": stair.spec.riser_height,
                "tread_depth": stair.spec.tread_depth,
                "width": stair.spec.width,
                "landing_length": stair.spec.landing_length,
                "runs_per_level": stair.spec.runs_per_level,
                "stair_type": stair.spec.stair_type.value,
            },
        }

    return state


def _serialize_element(elem: Any) -> dict[str, Any]:
    """将单个构件序列化."""
    from aec_building.aec.elements import (
        Beam, Column, CurtainWall, CurvedRoof, Door, FloorSlab, Railing, RoundColumn, Wall, Window,
    )

    if isinstance(elem, Beam):
        return {
            "start": list(elem.start), "end": list(elem.end),
            "level": elem.level,
            "width": elem.width, "height": elem.height,
            "material": elem.material.value,
        }
    if isinstance(elem, RoundColumn):
        return {
            "x": elem.x, "y": elem.y,
            "base_level": elem.base_level, "top_level": elem.top_level,
            "diameter": elem.diameter,
            "material": elem.material.value,
        }
    if isinstance(elem, Column):
        return {
            "x": elem.x, "y": elem.y,
            "base_level": elem.base_level, "top_level": elem.top_level,
            "section_width": elem.section_width,
            "section_depth": elem.section_depth,
            "section_thickness": elem.section_thickness,
            "material": elem.material.value,
        }
    if isinstance(elem, Wall):
        return {
            "start": list(elem.start), "end": list(elem.end),
            "base_level": elem.base_level, "top_level": elem.top_level,
            "thickness": elem.thickness,
            "wall_type": elem.wall_type.value,
        }
    if isinstance(elem, FloorSlab):
        return {
            "level": elem.level,
            "boundary_points": [list(p) for p in elem.boundary_points],
            "thickness": elem.thickness,
            "structural": elem.structural,
        }
    if isinstance(elem, CurtainWall):
        return {
            "start": list(elem.start), "end": list(elem.end),
            "base_level": elem.base_level, "top_level": elem.top_level,
            "panel_width": elem.panel_width,
            "panel_height": elem.panel_height,
            "mullion_width": elem.mullion_width,
            "mullion_depth": elem.mullion_depth,
        }
    if isinstance(elem, Door):
        return {
            "host_wall_id": elem.host_wall_id,
            "position": elem.position,
            "width": elem.width, "height": elem.height,
            "door_type": elem.door_type,
        }
    if isinstance(elem, Window):
        return {
            "host_wall_id": elem.host_wall_id,
            "position": elem.position,
            "width": elem.width, "height": elem.height,
            "sill_height": elem.sill_height,
        }
    if isinstance(elem, CurvedRoof):
        return {
            "base_level": elem.base_level,
            "boundary_points": [list(p) for p in elem.boundary_points],
            "ridge_height": elem.ridge_height,
            "roof_type": elem.roof_type.value,
            "overhang": elem.overhang,
            "eave_rise": elem.eave_rise,
            "thickness": elem.thickness,
        }
    if isinstance(elem, Railing):
        return {
            "path_points": [list(p) for p in elem.path_points],
            "level": elem.level,
            "height": elem.height,
            "post_spacing": elem.post_spacing,
            "post_width": elem.post_width,
            "post_depth": elem.post_depth,
            "rail_width": elem.rail_width,
            "rail_height": elem.rail_height,
            "bottom_rail": elem.bottom_rail,
            "bottom_rail_height": elem.bottom_rail_height,
            "material": elem.material.value,
        }
    # fallback
    return {"__unknown__": str(type(elem))}


def deserialize_building(state: dict[str, Any]) -> Any:
    """从 dict 重建 Building 实例."""
    from aec_building.aec.building import Building, BuildingElement, Opening
    from aec_building.aec.elements import (
        Beam, Column, CurtainWall, CurvedRoof, Door, FloorSlab,
        Railing, RoofType, RoundColumn, StructuralMaterial, Wall, WallType, Window,
    )
    from aec_building.aec.grid import GridSystem
    from aec_building.aec.staircase import Staircase, StairSpec, StairType
    from aec_building.core.references import GridRangeRef, GridRef, LevelRef

    # 重建轴网
    grid = GridSystem()
    grid.add_x_grids(
        list(state["grid"]["x_grids"].keys()),
        list(state["grid"]["x_grids"].values()),
    )
    grid.add_y_grids(
        list(state["grid"]["y_grids"].keys()),
        list(state["grid"]["y_grids"].values()),
    )
    grid.add_levels(
        list(state["grid"]["levels"].keys()),
        list(state["grid"]["levels"].values()),
    )

    building = Building(name=state["name"], grid=grid)
    building._id_counter = state["id_counter"]

    # 重建构件
    type_map = {
        "Beam": lambda d: Beam(
            start=tuple(d["start"]), end=tuple(d["end"]),
            level=d["level"],
            width=d.get("width", 300.0),
            height=d.get("height", 600.0),
            material=StructuralMaterial(d.get("material", "steel")),
        ),
        "Column": lambda d: Column(
            x=d["x"], y=d["y"],
            base_level=d["base_level"], top_level=d["top_level"],
            section_width=d.get("section_width", 305.0),
            section_depth=d.get("section_depth", 305.0),
            section_thickness=d.get("section_thickness", 12.0),
            material=StructuralMaterial(d.get("material", "steel")),
        ),
        "Wall": lambda d: Wall(
            start=tuple(d["start"]), end=tuple(d["end"]),
            base_level=d["base_level"], top_level=d["top_level"],
            thickness=d.get("thickness", 200.0),
            wall_type=WallType(d.get("wall_type", "interior")),
        ),
        "FloorSlab": lambda d: FloorSlab(
            level=d["level"],
            boundary_points=[tuple(p) for p in d["boundary_points"]],
            thickness=d.get("thickness", 150.0),
            structural=d.get("structural", True),
        ),
        "CurtainWall": lambda d: CurtainWall(
            start=tuple(d["start"]), end=tuple(d["end"]),
            base_level=d["base_level"], top_level=d["top_level"],
            panel_width=d.get("panel_width", 1500.0),
            panel_height=d.get("panel_height", 3000.0),
            mullion_width=d.get("mullion_width", 60.0),
            mullion_depth=d.get("mullion_depth", 120.0),
        ),
        "Door": lambda d: Door(
            host_wall_id=d["host_wall_id"],
            position=d["position"],
            width=d.get("width", 900.0),
            height=d.get("height", 2100.0),
            door_type=d.get("door_type", "single"),
        ),
        "Window": lambda d: Window(
            host_wall_id=d["host_wall_id"],
            position=d["position"],
            width=d.get("width", 1500.0),
            height=d.get("height", 1800.0),
            sill_height=d.get("sill_height", 900.0),
        ),
        "RoundColumn": lambda d: RoundColumn(
            x=d["x"], y=d["y"],
            base_level=d["base_level"], top_level=d["top_level"],
            diameter=d.get("diameter", 400.0),
            material=StructuralMaterial(d.get("material", "wood")),
        ),
        "CurvedRoof": lambda d: CurvedRoof(
            base_level=d["base_level"],
            boundary_points=[tuple(p) for p in d["boundary_points"]],
            ridge_height=d.get("ridge_height", 3000.0),
            roof_type=RoofType(d.get("roof_type", "hip")),
            overhang=d.get("overhang", 1500.0),
            eave_rise=d.get("eave_rise", 0.0),
            thickness=d.get("thickness", 200.0),
        ),
        "Railing": lambda d: Railing(
            path_points=[tuple(p) for p in d["path_points"]],
            level=d["level"],
            height=d.get("height", 1100.0),
            post_spacing=d.get("post_spacing", 1500.0),
            post_width=d.get("post_width", 80.0),
            post_depth=d.get("post_depth", 80.0),
            rail_width=d.get("rail_width", 60.0),
            rail_height=d.get("rail_height", 60.0),
            bottom_rail=d.get("bottom_rail", True),
            bottom_rail_height=d.get("bottom_rail_height", 150.0),
            material=StructuralMaterial(d.get("material", "wood")),
        ),
    }

    for eid, edata in state["elements"].items():
        etype = edata["type"]
        factory = type_map.get(etype)
        if factory is None:
            continue
        elem = factory(edata["data"])
        building._elements[eid] = BuildingElement(
            id=edata["id"],
            element=elem,
            depends_on=edata.get("depends_on", []),
            metadata=edata.get("metadata", {}),
        )

    # 重建开洞
    for oid, odata in state["openings"].items():
        ref = GridRangeRef(
            x_grid_start=odata["ref"]["x_grid_start"],
            x_grid_end=odata["ref"]["x_grid_end"],
            y_grid_start=odata["ref"]["y_grid_start"],
            y_grid_end=odata["ref"]["y_grid_end"],
            inset=odata["ref"].get("inset", 0),
        )
        building._openings[oid] = Opening(
            id=odata["id"],
            ref=ref,
            target_slabs=odata["target_slabs"],
            connect_to_roof=odata.get("connect_to_roof", False),
        )

    # 重建楼梯
    for sid, sdata in state["staircases"].items():
        building._staircases[sid] = Staircase(
            location=GridRef(
                x_grid=sdata["location"]["x_grid"],
                y_grid=sdata["location"]["y_grid"],
                offset_x=sdata["location"].get("offset_x", 0),
                offset_y=sdata["location"].get("offset_y", 0),
            ),
            base_level=LevelRef(
                level=sdata["base_level"]["level"],
                offset=sdata["base_level"].get("offset", 0),
            ),
            top_level=LevelRef(
                level=sdata["top_level"]["level"],
                offset=sdata["top_level"].get("offset", 0),
            ),
            spec=StairSpec(
                riser_height=sdata["spec"].get("riser_height", 150.0),
                tread_depth=sdata["spec"].get("tread_depth", 280.0),
                width=sdata["spec"].get("width", 1200.0),
                landing_length=sdata["spec"].get("landing_length", 1200.0),
                runs_per_level=sdata["spec"].get("runs_per_level", 2),
                stair_type=StairType(sdata["spec"].get("stair_type", "u_turn")),
            ),
        )

    return building


# ── 差异计算 ──

def compute_diff(
    state_a: dict[str, Any],
    state_b: dict[str, Any],
    from_version: int = 0,
    to_version: int = 0,
) -> StateDiff:
    """计算两个 Building 状态之间的差异."""
    diff = StateDiff(from_version=from_version, to_version=to_version)

    # 构件增删
    keys_a = set(state_a.get("elements", {}).keys())
    keys_b = set(state_b.get("elements", {}).keys())
    diff.added_elements = sorted(keys_b - keys_a)
    diff.removed_elements = sorted(keys_a - keys_b)

    # 开洞增删
    open_a = set(state_a.get("openings", {}).keys())
    open_b = set(state_b.get("openings", {}).keys())
    diff.added_elements.extend(sorted(open_b - open_a))
    diff.removed_elements.extend(sorted(open_a - open_b))

    # 楼梯增删
    stair_a = set(state_a.get("staircases", {}).keys())
    stair_b = set(state_b.get("staircases", {}).keys())
    diff.added_elements.extend(sorted(stair_b - stair_a))
    diff.removed_elements.extend(sorted(stair_a - stair_b))

    # 构件修改
    common = keys_a & keys_b
    for eid in sorted(common):
        ea = state_a["elements"][eid]
        eb = state_b["elements"][eid]
        if ea["data"] != eb["data"]:
            changes = {}
            for key in set(ea["data"].keys()) | set(eb["data"].keys()):
                va = ea["data"].get(key)
                vb = eb["data"].get(key)
                if va != vb:
                    changes[key] = {"from": va, "to": vb}
            if changes:
                diff.modified_elements.append({"id": eid, "changes": changes})

    # 轴网变更
    ga = state_a.get("grid", {})
    gb = state_b.get("grid", {})
    for axis in ("x_grids", "y_grids", "levels"):
        if ga.get(axis) != gb.get(axis):
            diff.grid_changes.append(f"{axis} changed")

    # 摘要数量变化
    count_keys = ["name"]
    for key in ("elements", "openings", "staircases"):
        ca = len(state_a.get(key, {}))
        cb = len(state_b.get(key, {}))
        if ca != cb:
            diff.summary_changes[key] = {"from": ca, "to": cb}

    return diff
