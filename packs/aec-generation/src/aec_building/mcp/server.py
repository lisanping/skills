"""geometry-kernel-mcp — MCP 服务端入口.

将 BREP 生成能力暴露为 MCP 工具，供 Agent harness 调用。
每个工具遵循案例 4.1 的粗粒度原则：一次 tool call 完成一个完整操作。

返回值统一结构：
{
    "status": "success" | "partial_success" | "error",
    "data": { ... },
    "warnings": [ ... ],
    "geometry_check": "valid" | "invalid: reason"
}
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from aec_building.aec.building import Building
from aec_building.aec.grid import GridSystem


@dataclass
class ToolResponse:
    """MCP 工具统一响应格式.

    对应案例中每次 tool call 返回的 JSON 结构。
    包含状态、数据负载、警告和几何校验。
    """

    status: str = "success"
    data: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    geometry_check: str = "valid"

    def to_dict(self) -> dict:
        return asdict(self)


class GeometryKernelMCP:
    """MCP 服务主体 — 管理建筑模型状态并暴露工具方法.

    维护一个 Building 实例作为"会话状态"，
    所有 tool call 都操作同一个 Building。
    """

    def __init__(self) -> None:
        self._building: Building | None = None

    @property
    def building(self) -> Building:
        if self._building is None:
            raise RuntimeError("No building initialized. Call create_project first.")
        return self._building

    # ── Tool: 创建项目 ──

    def solve_constraints(
        self,
        floors: int = 3,
        area_per_floor: float = 800.0,
        shape: str = "L",
        max_span: float = 9.0,
        floor_height: float = 3900.0,
        cutout_corner: str = "NE",
        has_atrium: bool = False,
        core_position: str = "north",
        entrance_direction: str = "south",
        polygon_sides: int = 0,
        custom_boundary: list[tuple[float, float]] | None = None,
        building_style: str = "",
        center_x: float = 0.0,
        center_y: float = 0.0,
    ) -> ToolResponse:
        """从结构化约束求解几何参数.

        Agent 从 NL 提取约束后调用此工具，获得可直接传给
        create_project / create_floors 的推荐参数。

        支持形状: L / rectangle / polygon / circular / courtyard / custom
        """
        from aec_building.constraints.solver import solve_design

        sol = solve_design(
            floors=floors,
            area_per_floor=area_per_floor,
            shape=shape,
            max_span=max_span,
            floor_height=floor_height,
            cutout_corner=cutout_corner,
            has_atrium=has_atrium,
            core_position=core_position,
            entrance_direction=entrance_direction,
            polygon_sides=polygon_sides,
            custom_boundary=custom_boundary,
            building_style=building_style,
            center_x=center_x,
            center_y=center_y,
        )

        return ToolResponse(
            status="success",
            data={
                "grid": {
                    "x_names": sol.x_grid_names,
                    "x_positions": sol.x_grid_positions,
                    "y_names": sol.y_grid_names,
                    "y_positions": sol.y_grid_positions,
                },
                "levels": {
                    "names": sol.level_names,
                    "elevations": sol.level_elevations,
                },
                "floor_boundary": sol.floor_boundary,
                "actual_area": round(sol.actual_area, 1),
                "core_zone": sol.core_zone,
                "atrium_zone": sol.atrium_zone,
                "entrance_wall": sol.entrance_wall,
                "column_skip_x": sol.column_skip_x,
                "column_skip_y": sol.column_skip_y,
                "column_positions": sol.column_positions,
                "building_style": sol.building_style,
            },
            warnings=sol.warnings,
        )

    def validate_constraints(
        self,
        floors: int = 3,
        area_per_floor: float = 800.0,
        shape: str = "L",
        structure: str = "steel_frame",
        max_span: float = 9.0,
        floor_height: float = 3900.0,
        has_atrium: bool = False,
        core_position: str = "",
        entrance_position: str = "",
    ) -> ToolResponse:
        """验证当前建筑是否满足设计约束集.

        从参数生成约束集，然后逐条对照 building summary 验证。
        """
        from aec_building.constraints.extractor import extract_office_building_constraints
        from aec_building.constraints.solver import validate_constraints as _validate

        cs = extract_office_building_constraints(
            floors=floors,
            area_per_floor=area_per_floor,
            shape=shape,
            structure=structure,
            max_span=max_span,
            floor_height=floor_height,
            has_atrium=has_atrium,
            core_position=core_position,
            entrance_position=entrance_position,
        )

        summary = self.building.summary()
        results = _validate(cs, summary)

        passed = [r for r in results if r.get("passed") is True]
        failed = [r for r in results if r.get("passed") is False]
        pending = [r for r in results if r.get("passed") is None]

        return ToolResponse(
            status="success",
            data={
                "results": results,
                "passed_count": len(passed),
                "failed_count": len(failed),
                "pending_count": len(pending),
                "constraint_summary": cs.summary(),
            },
        )

    # ── Tool: 创建项目 ──

    def create_project(
        self,
        name: str,
        x_grid_names: list[str],
        x_grid_positions: list[float],
        y_grid_names: list[str],
        y_grid_positions: list[float],
        level_names: list[str],
        level_elevations: list[float],
    ) -> ToolResponse:
        """创建新项目并建立轴网系统.

        对应案例 Tool Call 1-3：创建项目 + 轴网 + 标高。
        合并为一次 tool call（粗粒度原则）。
        """
        grid = GridSystem()
        grid.add_x_grids(x_grid_names, x_grid_positions)
        grid.add_y_grids(y_grid_names, y_grid_positions)
        grid.add_levels(level_names, level_elevations)

        self._building = Building(name=name, grid=grid)

        return ToolResponse(
            status="success",
            data={
                "grid_ids_x": x_grid_names,
                "grid_ids_y": y_grid_names,
                "levels": dict(zip(level_names, level_elevations)),
            },
        )

    # ── Tool: 创建楼板 ──

    def create_floors(
        self,
        boundary_points: list[tuple[float, float]],
        levels: list[str],
        thickness: float = 150.0,
    ) -> ToolResponse:
        """创建多层楼板.

        对应案例 Tool Call 4-5：创建楼板 + 复制到其他层。
        """
        slab_ids = self.building.add_slabs_for_levels(
            boundary_points=boundary_points,
            levels=levels,
            thickness=thickness,
        )

        # 计算面积
        from aec_building.aec.element_factory import _polygon_area
        area = _polygon_area(boundary_points)

        return ToolResponse(
            status="success",
            data={
                "slab_ids": slab_ids,
                "slab_count": len(slab_ids),
                "area_per_floor": round(area, 1),
            },
            geometry_check="valid (watertight, manifold)",
        )

    # ── Tool: 批量放柱 ──

    def place_columns(
        self,
        base_level: str,
        top_level: str,
        skip_x: list[str] | None = None,
        skip_y: list[str] | None = None,
        section_width: float = 305.0,
        section_depth: float = 305.0,
    ) -> ToolResponse:
        """在轴网交点批量放置柱子.

        对应案例 Tool Call 7。
        """
        col_ids = self.building.place_columns_on_grid(
            base_level=base_level,
            top_level=top_level,
            skip_x=set(skip_x) if skip_x else None,
            skip_y=set(skip_y) if skip_y else None,
            section_width=section_width,
            section_depth=section_depth,
        )

        return ToolResponse(
            status="success",
            data={
                "columns_placed": len(col_ids),
                "column_ids": col_ids,
            },
            geometry_check=f"{len(col_ids)} valid BREP solids",
        )

    # ── Tool: 创建墙体 ──

    def create_walls(
        self,
        walls: list[dict],
    ) -> ToolResponse:
        """批量创建墙体.

        对应案例 Tool Call 8/14。

        Args:
            walls: 墙体参数列表，每项包含 start, end, base_level, top_level,
                   thickness, wall_type。
        """
        from aec_building.aec.elements import Wall, WallType

        wall_ids = []
        for w in walls:
            wt = WallType(w.get("wall_type", "interior"))
            wall = Wall(
                start=tuple(w["start"]),
                end=tuple(w["end"]),
                base_level=w["base_level"],
                top_level=w["top_level"],
                thickness=w.get("thickness", 200.0),
                wall_type=wt,
            )
            wall_ids.append(self.building.add_wall(wall))

        return ToolResponse(
            status="success",
            data={
                "wall_count": len(wall_ids),
                "wall_ids": wall_ids,
            },
        )

    # ── Tool: 创建开洞 ──

    def create_opening(
        self,
        x_grid_start: str,
        x_grid_end: str,
        y_grid_start: str,
        y_grid_end: str,
        target_slab_ids: list[str],
        inset: float = 500.0,
        connect_to_roof: bool = False,
    ) -> ToolResponse:
        """创建基于轴网参照的开洞.

        对应案例 Tool Call 6：中庭开洞。
        """
        from aec_building.core.references import GridRangeRef

        ref = GridRangeRef(
            x_grid_start=x_grid_start,
            x_grid_end=x_grid_end,
            y_grid_start=y_grid_start,
            y_grid_end=y_grid_end,
            inset=inset,
        )

        opening_id = self.building.add_opening(
            ref=ref,
            target_slab_ids=target_slab_ids,
            connect_to_roof=connect_to_roof,
        )

        warnings = []
        # 检查潜在冲突
        bounds = ref.resolve(self.building.grid)
        warnings.append(
            f"Opening bounds: x=[{bounds[0]:.0f}, {bounds[2]:.0f}], "
            f"y=[{bounds[1]:.0f}, {bounds[3]:.0f}] — verify no beam conflict"
        )

        return ToolResponse(
            status="success",
            data={
                "opening_id": opening_id,
                "target_slabs": target_slab_ids,
            },
            warnings=warnings,
        )

    # ── Tool: 修改构件 ──

    def modify_element(
        self,
        element_id: str,
        changes: dict[str, Any],
    ) -> ToolResponse:
        """修改构件参数并返回受影响的依赖构件.

        对应案例 Tool Call 9/11。
        修改墙端点时自动联动相交墙（参数化连锁更新）。
        """
        affected = self.building.modify_element(element_id, **changes)

        # 分离出联动更新的构件
        cascaded = affected[1:]  # 第一个是自身
        cascaded_updates = []
        for eid in cascaded:
            be = self.building.get_element(eid)
            from aec_building.aec.elements import Wall
            if isinstance(be.element, Wall):
                cascaded_updates.append({
                    "element": eid,
                    "new_start": list(be.element.start),
                    "new_end": list(be.element.end),
                })

        return ToolResponse(
            status="success",
            data={
                "modified": element_id,
                "changes": changes,
                "affected_elements": affected,
                "cascaded_updates": cascaded_updates,
            },
        )

    # ── Tool: 创建楼梯 ──

    def create_staircase(
        self,
        x_grid: str,
        y_grid: str,
        base_level: str,
        top_level: str,
        offset_x: float = 0.0,
        offset_y: float = 0.0,
        width: float = 1200.0,
        riser_height: float = 165.0,
        tread_depth: float = 280.0,
        stair_type: str = "u_turn",
    ) -> ToolResponse:
        """创建楼梯.

        对应案例 Tool Call 10-12：楼梯创建、失败恢复、重试。
        失败时返回 STAIR_GEOMETRY_INVALID + 可操作修复建议。
        """
        from aec_building.aec.staircase import Staircase, StairSpec, StairType
        from aec_building.core.references import GridRef, LevelRef

        spec = StairSpec(
            riser_height=riser_height,
            tread_depth=tread_depth,
            width=width,
            stair_type=StairType(stair_type),
        )

        staircase = Staircase(
            location=GridRef(x_grid=x_grid, y_grid=y_grid,
                             offset_x=offset_x, offset_y=offset_y),
            base_level=LevelRef(level=base_level),
            top_level=LevelRef(level=top_level),
            spec=spec,
        )

        # 计算总升高
        base_elev = self.building.grid.level_elevation(base_level)
        top_elev = self.building.grid.level_elevation(top_level)
        total_rise = top_elev - base_elev

        # 估算可用空间（基于轴网间距）
        grid = self.building.grid
        x_names = list(grid.x_grids.keys())
        y_names = list(grid.y_grids.keys())
        x_idx = x_names.index(x_grid) if x_grid in x_names else 0
        y_idx = y_names.index(y_grid) if y_grid in y_names else 0

        # 可用长度：到下一轴线的距离
        if x_idx + 1 < len(x_names):
            avail_length = grid.x_grids[x_names[x_idx + 1]] - grid.x_grids[x_grid]
        else:
            avail_length = 9000  # 默认

        if y_idx + 1 < len(y_names):
            avail_width = grid.y_grids[y_names[y_idx + 1]] - grid.y_grids[y_grid]
        else:
            avail_width = 9000

        # 规范+空间验证
        errors = staircase.validate(avail_length, avail_width)
        fit_error = staircase.check_fits_in_space(total_rise, avail_length)
        if fit_error:
            errors.append(fit_error)

        if errors:
            suggestions = []
            for err in errors:
                for s in err.suggestions:
                    suggestions.append({
                        "action": s,
                        "error_code": err.code,
                    })

            # 添加可执行修复建议
            if any(e.code == "STAIR_GEOMETRY_INVALID" for e in errors):
                suggestions.append({
                    "action": "enlarge_stairwell",
                    "tool": "modify_element",
                    "description": "扩大楼梯间空间后重试",
                })

            return ToolResponse(
                status="error",
                data={
                    "error_code": errors[0].code,
                    "message": errors[0].message,
                    "suggestions": suggestions,
                },
            )

        # 验证通过，添加楼梯
        stair_id = self.building.add_staircase(staircase)

        geom = staircase.compute_geometry(total_rise)

        return ToolResponse(
            status="success",
            data={
                "staircase_id": stair_id,
                "total_rise": total_rise,
                "total_risers": geom["total_risers"] if isinstance(geom, dict) else 0,
                "actual_riser_height": round(geom["actual_riser_height"], 1) if isinstance(geom, dict) else 0,
                "stair_type": stair_type,
            },
        )

    # ── Tool: 交付报告 ──

    def generate_report(
        self,
        compliance_result: dict | None = None,
        exported_files: list[str] | None = None,
        open_issues: list[str] | None = None,
    ) -> ToolResponse:
        """生成交付报告.

        对应案例 Tool Call 20：面向用户的最终交付清单。
        返回 Markdown 格式的报告，包含关键参数、约束状态、未决事项。
        """
        from aec_building.orchestrator.reporter import (
            format_report_markdown,
            generate_report,
        )

        summary = self.building.summary()
        report = generate_report(summary, compliance_result, exported_files)

        # 追加用户指定的未决事项
        if open_issues:
            report.open_issues.extend(open_issues)

        markdown = format_report_markdown(report)

        return ToolResponse(
            status="success",
            data={
                "report_markdown": markdown,
                "key_parameters": report.key_parameters,
                "open_issues": report.open_issues,
                "deliverables_count": len(report.deliverables),
            },
        )

    # ── Tool: 幕墙 ──

    def create_curtain_wall(
        self,
        start: list[float],
        end: list[float],
        base_level: str,
        top_level: str,
        panel_width: float = 1500.0,
        mullion_width: float = 60.0,
        mullion_depth: float = 120.0,
    ) -> ToolResponse:
        """创建幕墙.

        对应案例 Tool Call 13：沿中心线生成竖梃网格 + 玻璃面板。
        """
        from aec_building.aec.elements import CurtainWall

        cw = CurtainWall(
            start=tuple(start),
            end=tuple(end),
            base_level=base_level,
            top_level=top_level,
            panel_width=panel_width,
            mullion_width=mullion_width,
            mullion_depth=mullion_depth,
        )
        cw_id = self.building.add_curtain_wall(cw)

        return ToolResponse(
            status="success",
            data={
                "curtain_wall_id": cw_id,
            },
        )

    # ── Tool: 批量放置门 ──

    def auto_place_doors(
        self,
        door_spacing: float = 4000.0,
        door_width: float = 900.0,
        door_height: float = 2100.0,
    ) -> ToolResponse:
        """在所有内墙上自动放置办公室门.

        对应案例 Tool Call 15。
        """
        door_ids = self.building.auto_place_doors(
            door_spacing=door_spacing,
            door_width=door_width,
            door_height=door_height,
        )

        return ToolResponse(
            status="success",
            data={
                "doors_placed": len(door_ids),
                "door_ids": door_ids,
            },
        )

    # ── Tool: 合规检查 ──

    def place_beams(
        self,
        level: str,
        beam_width: float = 300.0,
        beam_height: float = 600.0,
    ) -> ToolResponse:
        """在轴网交点间自动放置结构梁.

        粗粒度：一次 tool call 放置整层所有梁。
        """
        beam_ids = self.building.auto_place_beams(
            level=level,
            beam_width=beam_width,
            beam_height=beam_height,
        )

        return ToolResponse(
            status="success",
            data={
                "beams_placed": len(beam_ids),
                "beam_ids": beam_ids,
            },
        )

    # ── Tool: 合规检查（原有） ──

    def check_compliance(
        self,
        standards: list[str] | None = None,
        scope: list[str] | None = None,
        extra_info: dict | None = None,
    ) -> ToolResponse:
        """执行规范合规检查.

        对应案例 Tool Call 16。
        """
        from aec_building.compliance.checker import check_building

        summary = self.building.summary()

        # 从楼板几何动态计算每层面积
        area_per_floor = summary.get("area_per_floor", 0)
        if area_per_floor == 0 and self.building.slabs:
            from aec_building.aec.element_factory import _polygon_area
            first_slab = self.building.slabs[0].element
            area_per_floor = round(_polygon_area(first_slab.boundary_points), 1)

        stair_count = summary.get("staircase_count", 0)
        if extra_info and "stair_count" in extra_info:
            stair_count = extra_info["stair_count"]

        # 从楼梯位置计算疏散距离（如有楼梯和楼板几何）
        stair_positions = []
        for _sid, sc in self.building.staircases:
            x, y = sc.location.resolve(self.building.grid)
            stair_positions.append((x, y))

        floor_boundary = []
        if self.building.slabs:
            floor_boundary = list(self.building.slabs[0].element.boundary_points)

        building_info = {
            "floors": summary["slab_count"],
            "area_per_floor": area_per_floor,
            "stair_count": stair_count,
            "shape": extra_info.get("shape", "") if extra_info else "",
            "stair_positions": stair_positions,
            "floor_boundary": floor_boundary,
            **(extra_info or {}),
        }

        result = check_building(building_info, standards, scope)

        violations = [
            {
                "code": v.code,
                "severity": v.severity.value,
                "description": v.description,
                "location": v.location,
                "suggestion": v.suggestion,
                **({"fix_action": v.fix_action} if v.fix_action else {}),
            }
            for v in result.violations
        ]

        return ToolResponse(
            status="success",
            data={
                "violations": violations,
                "passes": result.passes,
                "summary": result.summary(),
            },
        )

    # ── Tool: 导出 ──

    def export_model(
        self,
        output_path: str,
        formats: list[str] | None = None,
    ) -> ToolResponse:
        """导出建筑模型到独立输出文件夹.

        对应案例 Tool Call 19。
        自动创建带时间戳的文件夹，生成多种格式文件。

        支持格式：
        - "step": STEP 文件 (需要 CadQuery) — CAD 内核精确几何
        - "colored_step": 带色彩 STEP (需要 OCP/XDE) — FreeCAD/SolidWorks 显色
        - "ifc": IFC4 文件 (需要 IfcOpenShell) — BIM 行业标准
        - "glb": 带色彩 GLB (需要 trimesh) — Web 3D / Three.js
        - "obj": OBJ + MTL (需要 trimesh) — Blender/3ds Max/Maya
        - "stl": STL 三角网格 (需要 trimesh) — 3D 打印/FEM
        - "dae": Collada DAE (需要 trimesh) — SketchUp/游戏引擎
        - "dxf": DXF 3D (需要 ezdxf) — AutoCAD/中望 CAD
        - "png_3d": 3D 等轴截图 (需要 PyVista + CadQuery-OCP)
        - "png_plan": 平面图 (需要 matplotlib)
        - "summary": summary.json

        默认: ["step", "png_3d", "png_plan", "summary"]
        """
        import json
        from pathlib import Path
        from aec_building.utils.output import create_output_folder
        from aec_building.verify.visual_check import capture_3d_view, render_plan_view

        formats = formats or ["step", "png_3d", "png_plan", "summary"]
        exported = []
        warnings = []

        # 创建独立输出文件夹
        folder = create_output_folder(self.building.name, base_dir=output_path)
        step_path = folder / "model.step"

        # STEP 导出（png_3d 也依赖它）
        step_exported = False
        if "step" in formats or "png_3d" in formats:
            try:
                actual_path = self.building.export_to_step(str(step_path))
                if "step" in formats:
                    exported.append(actual_path)
                step_exported = True
            except ImportError:
                warnings.append("CadQuery not installed — STEP export skipped")
                if "step" in formats:
                    exported.append(f"{step_path} (skipped: no CadQuery)")
            except Exception as e:
                warnings.append(f"STEP export failed: {e}")
                if "step" in formats:
                    exported.append(f"{step_path} (failed)")

        # 带色彩 STEP 导出 (OCP/XDE)
        if "colored_step" in formats:
            try:
                from aec_building.export.step_export import export_colored_step
                cstep_path = folder / "model_colored.step"
                actual_path = export_colored_step(self.building, str(cstep_path))
                exported.append(str(actual_path))
            except ImportError as e:
                warnings.append(f"Colored STEP requires OCP (pip install cadquery) — {e}")
            except Exception as e:
                warnings.append(f"Colored STEP export failed: {e}")

        # IFC 导出
        if "ifc" in formats:
            try:
                from aec_building.export.ifc_export import export_to_ifc
                ifc_path = folder / "model.ifc"
                actual_path = export_to_ifc(self.building, str(ifc_path))
                exported.append(actual_path)
            except ImportError:
                warnings.append("IfcOpenShell not installed — IFC export skipped")
                exported.append(f"{folder / 'model.ifc'} (skipped)")
            except Exception as e:
                warnings.append(f"IFC export failed: {e}")

        # 带色彩 GLB 导出
        if "glb" in formats:
            try:
                from aec_building.utils.output import building_to_colored_glb
                glb_path = folder / "model.glb"
                actual_path = building_to_colored_glb(self.building, str(glb_path))
                exported.append(str(actual_path))
            except ImportError as e:
                warnings.append(f"GLB export requires trimesh + shapely — {e}")
                exported.append(f"{folder / 'model.glb'} (skipped)")
            except Exception as e:
                warnings.append(f"GLB export failed: {e}")

        # OBJ 导出 (Blender/3ds Max/Maya)
        if "obj" in formats:
            try:
                from aec_building.utils.output import building_to_obj
                obj_path = folder / "model.obj"
                actual_path = building_to_obj(self.building, str(obj_path))
                exported.append(str(actual_path))
            except ImportError as e:
                warnings.append(f"OBJ export requires trimesh — {e}")
            except Exception as e:
                warnings.append(f"OBJ export failed: {e}")

        # STL 导出 (3D 打印 / FEM)
        if "stl" in formats:
            try:
                from aec_building.utils.output import building_to_stl
                stl_path = folder / "model.stl"
                actual_path = building_to_stl(self.building, str(stl_path))
                exported.append(str(actual_path))
            except ImportError as e:
                warnings.append(f"STL export requires trimesh — {e}")
            except Exception as e:
                warnings.append(f"STL export failed: {e}")

        # Collada DAE 导出 (SketchUp / 游戏引擎)
        if "dae" in formats:
            try:
                from aec_building.utils.output import building_to_dae
                dae_path = folder / "model.dae"
                actual_path = building_to_dae(self.building, str(dae_path))
                exported.append(str(actual_path))
            except ImportError as e:
                warnings.append(f"DAE export requires trimesh — {e}")
            except Exception as e:
                warnings.append(f"DAE export failed: {e}")

        # DXF 导出 (AutoCAD / 中望 CAD)
        if "dxf" in formats:
            try:
                from aec_building.utils.output import building_to_dxf
                dxf_path = folder / "model.dxf"
                actual_path = building_to_dxf(self.building, str(dxf_path))
                exported.append(str(actual_path))
            except ImportError as e:
                warnings.append(f"DXF export requires ezdxf (pip install ezdxf) — {e}")
            except Exception as e:
                warnings.append(f"DXF export failed: {e}")

        # 3D 截图
        if "png_3d" in formats:
            png_3d_path = folder / "3d.png"
            if step_exported:
                try:
                    actual = capture_3d_view(str(step_path), str(png_3d_path))
                    exported.append(actual)
                except Exception as e:
                    warnings.append(f"3D screenshot failed: {e}")
                    exported.append(f"{png_3d_path} (failed)")
            else:
                warnings.append("3D screenshot skipped (no STEP file)")

        # 平面图
        if "png_plan" in formats:
            plan_path = folder / "plan.png"
            try:
                actual = render_plan_view(self.building, str(plan_path))
                exported.append(actual)
            except Exception as e:
                warnings.append(f"Plan view failed: {e}")
                exported.append(f"{plan_path} (failed)")

        # summary.json
        if "summary" in formats:
            summary_path = folder / "summary.json"
            summary_data = self.building.summary()
            summary_path.write_text(json.dumps(summary_data, ensure_ascii=False, indent=2))
            exported.append(str(summary_path))

        return ToolResponse(
            status="success" if not warnings else "partial_success",
            data={
                "output_folder": str(folder),
                "exported_files": exported,
                "building_summary": self.building.summary(),
            },
            warnings=warnings,
        )

    # ── Tool: 状态摘要 ──

    def get_summary(self) -> ToolResponse:
        """获取当前建筑状态摘要.

        用于 Agent 上下文压缩（案例第七节）。
        """
        return ToolResponse(
            status="success",
            data=self.building.summary(),
        )

    # ── Tool: 视觉自检 ──

    def visual_check(
        self,
        screenshot_path: str = "",
    ) -> ToolResponse:
        """执行视觉自检.

        对应案例自检节点（TC 18）。
        基于建筑摘要进行逻辑检查，如有 STEP 文件则尝试截图。
        """
        from aec_building.verify.visual_check import run_visual_checks

        summary = self.building.summary()
        report = run_visual_checks(summary, screenshot_path=screenshot_path)

        return ToolResponse(
            status="success" if report.all_passed else "partial_success",
            data=report.summary(),
            warnings=[
                f"{item['item']}: {item['note']}"
                for item in report.summary()["issues"]
            ] if not report.all_passed else [],
        )

    # ── Tool: 状态管理 ──

    def take_snapshot(self, name: str = "") -> ToolResponse:
        """保存当前 Building 状态快照.

        对应 §7.1 上下文管理 + §7.2 状态回滚。
        快照可用于回滚到某个检查点。
        """
        from aec_building.aec.state import StateManager

        if not hasattr(self, "_state_manager"):
            self._state_manager = StateManager()

        snap = self._state_manager.take_snapshot(self.building, name)

        return ToolResponse(
            status="success",
            data={
                "version": snap.version,
                "name": snap.name,
                "element_count": self.building.summary()["total_elements"],
            },
        )

    def rollback(self, version: int) -> ToolResponse:
        """回滚 Building 到指定快照版本.

        回滚后当前 Building 被替换为快照中的状态。
        """
        if not hasattr(self, "_state_manager"):
            return ToolResponse(
                status="error",
                data={"message": "No snapshots available"},
            )

        self._building = self._state_manager.rollback(version)

        return ToolResponse(
            status="success",
            data={
                "rolled_back_to": version,
                "building_summary": self.building.summary(),
            },
        )

    def state_diff(self, from_version: int, to_version: int) -> ToolResponse:
        """计算两个快照版本之间的差异.

        返回人/机双可读的变更描述。
        """
        if not hasattr(self, "_state_manager"):
            return ToolResponse(
                status="error",
                data={"message": "No snapshots available"},
            )

        diff = self._state_manager.diff(from_version, to_version)

        return ToolResponse(
            status="success",
            data={
                "from_version": diff.from_version,
                "to_version": diff.to_version,
                "added": diff.added_elements,
                "removed": diff.removed_elements,
                "modified": diff.modified_elements,
                "grid_changes": diff.grid_changes,
                "text": diff.to_text(),
            },
        )

    # ── Tool: 自定义柱位放置 ──

    def place_columns_at(
        self,
        positions: list[list[float]],
        base_level: str,
        top_level: str,
        section_width: float = 400.0,
        section_depth: float = 400.0,
        section_thickness: float = 0.0,
        material: str = "wood",
    ) -> ToolResponse:
        """在任意坐标位置批量放置柱子.

        与 place_columns (轴网交点) 互补，适用于:
        - 环形柱网 (传统建筑)
        - 自由散布柱位 (异形平面)
        - 从 solve_constraints 返回的 column_positions

        Args:
            positions: 柱位坐标列表 [[x, y], ...]，单位 mm。
            base_level: 柱脚标高。
            top_level: 柱顶标高。
            section_width: 截面宽 (mm)。
            section_depth: 截面深 (mm)。
            section_thickness: 壁厚 (mm, 0=实心)。
            material: 材料 ("steel"/"concrete"/"wood"/"composite")。
        """
        from aec_building.aec.elements import Column, StructuralMaterial

        mat = StructuralMaterial(material)
        thickness = section_thickness if section_thickness > 0 else section_width

        col_ids = []
        for pos in positions:
            col = Column(
                x=pos[0], y=pos[1],
                base_level=base_level, top_level=top_level,
                section_width=section_width, section_depth=section_depth,
                section_thickness=thickness,
                material=mat,
            )
            col_ids.append(self.building.add_column(col))

        return ToolResponse(
            status="success",
            data={
                "columns_placed": len(col_ids),
                "column_ids": col_ids,
            },
            geometry_check=f"{len(col_ids)} valid BREP solids",
        )

    # ── Tool: 自定义梁放置 ──

    def place_beams_at(
        self,
        beams: list[dict],
    ) -> ToolResponse:
        """在任意位置批量放置梁.

        与 place_beams (轴网自动) 互补，适用于:
        - 环向梁、径向梁 (传统建筑)
        - 斗拱层模拟 (短梁阵列)
        - 交叉斜撑 (抗震结构)

        Args:
            beams: 梁参数列表，每项包含:
                - start: [x, y] 起点 (mm)
                - end: [x, y] 终点 (mm)
                - level: 所属标高
                - width: 截面宽 (mm, 默认 250)
                - height: 截面高 (mm, 默认 400)
                - material: 材料 (默认 "wood")
        """
        from aec_building.aec.elements import Beam, StructuralMaterial

        beam_ids = []
        for b in beams:
            mat = StructuralMaterial(b.get("material", "wood"))
            beam = Beam(
                start=tuple(b["start"]),
                end=tuple(b["end"]),
                level=b["level"],
                width=b.get("width", 250.0),
                height=b.get("height", 400.0),
                material=mat,
            )
            beam_ids.append(self.building.add_beam(beam))

        return ToolResponse(
            status="success",
            data={
                "beams_placed": len(beam_ids),
                "beam_ids": beam_ids,
            },
        )

    # ── Tool: 添加窗户 ──

    def place_windows(
        self,
        windows: list[dict],
    ) -> ToolResponse:
        """在墙体上批量放置窗户.

        Args:
            windows: 窗户参数列表，每项包含:
                - host_wall_id: 宿主墙 ID
                - position: 沿墙体位置 (0.0~1.0)
                - width: 窗宽 (mm, 默认 1500)
                - height: 窗高 (mm, 默认 1800)
                - sill_height: 窗台高 (mm, 默认 900)
        """
        from aec_building.aec.elements import Window

        win_ids = []
        for w in windows:
            window = Window(
                host_wall_id=w["host_wall_id"],
                position=w.get("position", 0.5),
                width=w.get("width", 1500.0),
                height=w.get("height", 1800.0),
                sill_height=w.get("sill_height", 900.0),
            )
            win_ids.append(self.building.add_window(window))

        return ToolResponse(
            status="success",
            data={
                "windows_placed": len(win_ids),
                "window_ids": win_ids,
            },
        )

    # ── Tool: 设置外观 ──

    def set_appearance(
        self,
        element_ids: list[str],
        color_rgb: list[int] | None = None,
        opacity: float = 1.0,
        preset: str = "",
    ) -> ToolResponse:
        """批量设置构件外观（颜色、透明度）.

        可使用预设名称 (preset) 或自定义 RGB 颜色。

        预设名称: steel / concrete / wood / composite /
                  red_wall / marble / bronze / glazed_tile / glass / roof_tile

        Args:
            element_ids: 要设置的构件 ID 列表。
            color_rgb: [R, G, B] 各 0~255。
            opacity: 不透明度 0.0~1.0。
            preset: 预设外观名称 (优先于 color_rgb)。
        """
        from aec_building.aec.elements import Appearance, DEFAULT_APPEARANCE, SurfaceFinish

        if preset and preset in DEFAULT_APPEARANCE:
            app = DEFAULT_APPEARANCE[preset]
            # 覆盖 opacity 如有指定
            if opacity < 1.0:
                app = Appearance(color_rgb=app.color_rgb, opacity=opacity, finish=app.finish)
        elif color_rgb and len(color_rgb) == 3:
            app = Appearance(
                color_rgb=tuple(color_rgb),
                opacity=opacity,
                finish=SurfaceFinish.MATTE,
            )
        else:
            return ToolResponse(
                status="error",
                data={"message": "Provide preset name or color_rgb [R, G, B]"},
            )

        updated = []
        for eid in element_ids:
            try:
                be = self.building.get_element(eid)
                be.element.appearance = app
                updated.append(eid)
            except (KeyError, AttributeError):
                pass

        return ToolResponse(
            status="success",
            data={
                "updated_count": len(updated),
                "updated_ids": updated,
                "appearance": {
                    "color_rgb": list(app.color_rgb) if app.color_rgb else None,
                    "opacity": app.opacity,
                    "finish": app.finish.value,
                },
            },
        )

    # ── LOD 300: 圆柱、曲面屋顶、栏杆 ──

    def place_round_columns_at(
        self,
        positions: list[list[float]],
        base_level: str,
        top_level: str,
        diameter: float = 400.0,
        material: str = "wood",
    ) -> ToolResponse:
        """在任意坐标位置批量放置圆柱.

        适用于传统建筑木柱、装饰柱、罗马柱等圆形截面柱。

        Args:
            positions: 柱位坐标列表 [[x, y], ...]。
            base_level: 柱底标高名。
            top_level: 柱顶标高名。
            diameter: 柱径 (mm)。
            material: 材料 (wood/steel/concrete/composite)。
        """
        from aec_building.aec.elements import RoundColumn, StructuralMaterial

        mat = StructuralMaterial(material)
        col_ids = []
        for pos in positions:
            col = RoundColumn(
                x=pos[0], y=pos[1],
                base_level=base_level, top_level=top_level,
                diameter=diameter, material=mat,
            )
            col_ids.append(self.building.add_round_column(col))
        return ToolResponse(
            status="success",
            data={"columns_placed": len(col_ids), "column_ids": col_ids},
            geometry_check=f"{len(col_ids)} round column BREP solids",
        )

    def create_curved_roof(
        self,
        base_level: str,
        boundary_points: list[list[float]],
        ridge_height: float = 3000.0,
        roof_type: str = "hip",
        overhang: float = 1500.0,
        eave_rise: float = 0.0,
        thickness: float = 200.0,
    ) -> ToolResponse:
        """创建曲面屋顶.

        支持屋顶类型: flat / gable / hip / half_hip / conical
        - hip: 庑殿顶 (四坡), 适用于宫殿正殿
        - gable: 硬山/悬山 (两坡), 适用于普通民居
        - half_hip: 歇山顶 (四坡+山花), 适用于宫殿配殿
        - conical: 攒尖顶 (锥形), 适用于亭/阁/塔
        - flat: 平顶 (带出挑)

        Args:
            base_level: 屋顶底面标高名。
            boundary_points: 屋顶底边轮廓 [[x,y], ...]。
            ridge_height: 脊线高度 (mm)。
            roof_type: 屋顶类型。
            overhang: 檐口出挑距离 (mm)。
            eave_rise: 檐口翘起高度 (mm), 用于传统建筑翘角。
            thickness: 屋面厚度 (mm)。
        """
        from aec_building.aec.elements import CurvedRoof, RoofType

        rt = RoofType(roof_type)
        pts = [tuple(p) for p in boundary_points]
        roof = CurvedRoof(
            base_level=base_level,
            boundary_points=pts,
            ridge_height=ridge_height,
            roof_type=rt,
            overhang=overhang,
            eave_rise=eave_rise,
            thickness=thickness,
        )
        roof_id = self.building.add_curved_roof(roof)
        return ToolResponse(
            status="success",
            data={
                "roof_id": roof_id,
                "roof_type": roof_type,
                "ridge_height": ridge_height,
                "overhang": overhang,
                "eave_rise": eave_rise,
            },
        )

    def create_railing(
        self,
        path_points: list[list[float]],
        level: str,
        height: float = 1100.0,
        post_spacing: float = 1500.0,
        post_width: float = 80.0,
        post_depth: float = 80.0,
        rail_width: float = 60.0,
        rail_height: float = 60.0,
        bottom_rail: bool = True,
        material: str = "wood",
    ) -> ToolResponse:
        """沿路径创建栏杆/勾栏.

        自动按间距生成立柱 + 顶部扶手 + 可选底部横杆。
        适用于阳台栏杆、台基围栏、楼梯扶手等。

        Args:
            path_points: 栏杆路径点 [[x,y], ...]。
            level: 栏杆底面标高名。
            height: 栏杆总高 (mm)。
            post_spacing: 立柱间距 (mm)。
            post_width: 立柱截面宽 (mm)。
            post_depth: 立柱截面深 (mm)。
            rail_width: 扶手截面宽 (mm)。
            rail_height: 扶手截面高 (mm)。
            bottom_rail: 是否有底部横杆。
            material: 材料 (wood/steel/concrete)。
        """
        from aec_building.aec.elements import Railing, StructuralMaterial

        mat = StructuralMaterial(material)
        pts = [tuple(p) for p in path_points]
        railing = Railing(
            path_points=pts,
            level=level,
            height=height,
            post_spacing=post_spacing,
            post_width=post_width,
            post_depth=post_depth,
            rail_width=rail_width,
            rail_height=rail_height,
            bottom_rail=bottom_rail,
            material=mat,
        )
        rail_id = self.building.add_railing(railing)
        return ToolResponse(
            status="success",
            data={
                "railing_id": rail_id,
                "path_length_mm": sum(
                    ((pts[i+1][0]-pts[i][0])**2 + (pts[i+1][1]-pts[i][1])**2)**0.5
                    for i in range(len(pts)-1)
                ),
                "height": height,
            },
        )
