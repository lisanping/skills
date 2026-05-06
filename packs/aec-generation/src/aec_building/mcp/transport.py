"""MCP JSON-RPC Transport — 标准 MCP 协议服务端.

将 GeometryKernelMCP 的工具方法暴露为标准 MCP 协议接口。
支持 stdio transport，供 Agent harness 通过 JSON-RPC 调用。

启动方式:
    python -m aec_building.mcp.transport

或在 MCP 配置中:
    {
        "mcpServers": {
            "geometry-kernel": {
                "command": "python",
                "args": ["-m", "aec_building.mcp.transport"]
            }
        }
    }
"""

from __future__ import annotations

import json
import sys
from typing import Any

from aec_building.mcp.server import GeometryKernelMCP, ToolResponse

# MCP 工具 schema 定义
TOOL_DEFINITIONS = [
    {
        "name": "solve_constraints",
        "description": "从结构化约束求解几何参数（轴网、标高、楼板边界、核心筒/中庭位置）",
        "inputSchema": {
            "type": "object",
            "properties": {
                "floors": {"type": "integer", "default": 3, "description": "层数"},
                "area_per_floor": {"type": "number", "default": 800.0, "description": "每层目标面积 (m²)"},
                "shape": {"type": "string", "default": "L", "enum": ["L", "rectangle", "polygon", "circular", "courtyard", "custom"], "description": "平面形状"},
                "max_span": {"type": "number", "default": 9.0, "description": "最大柱距 (m)"},
                "floor_height": {"type": "number", "default": 3900.0, "description": "层高 (mm)"},
                "cutout_corner": {"type": "string", "default": "NE", "enum": ["NE", "NW", "SE", "SW"]},
                "has_atrium": {"type": "boolean", "default": False},
                "core_position": {"type": "string", "default": "north", "enum": ["north", "south", "east", "west"]},
                "entrance_direction": {"type": "string", "default": "south", "enum": ["north", "south", "east", "west"]},
                "polygon_sides": {"type": "integer", "default": 0, "description": "正多边形边数 (shape=polygon 时使用, 3~36)"},
                "custom_boundary": {"type": "array", "items": {"type": "array", "items": {"type": "number"}}, "description": "自定义边界点 (shape=custom 时使用)"},
                "building_style": {"type": "string", "default": "", "description": "建筑风格标签"},
                "center_x": {"type": "number", "default": 0.0, "description": "多边形/圆形中心 X (mm)"},
                "center_y": {"type": "number", "default": 0.0, "description": "多边形/圆形中心 Y (mm)"},
            },
        },
    },
    {
        "name": "validate_constraints",
        "description": "验证当前建筑是否满足设计约束集",
        "inputSchema": {
            "type": "object",
            "properties": {
                "floors": {"type": "integer", "default": 3},
                "area_per_floor": {"type": "number", "default": 800.0},
                "shape": {"type": "string", "default": "L"},
                "structure": {"type": "string", "default": "steel_frame"},
                "max_span": {"type": "number", "default": 9.0},
                "floor_height": {"type": "number", "default": 3900.0},
                "has_atrium": {"type": "boolean", "default": False},
                "core_position": {"type": "string", "default": ""},
                "entrance_position": {"type": "string", "default": ""},
            },
        },
    },
    {
        "name": "create_project",
        "description": "创建新建筑项目并建立轴网系统（合并 TC 1-3）",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "项目名称"},
                "x_grid_names": {"type": "array", "items": {"type": "string"}},
                "x_grid_positions": {"type": "array", "items": {"type": "number"}},
                "y_grid_names": {"type": "array", "items": {"type": "string"}},
                "y_grid_positions": {"type": "array", "items": {"type": "number"}},
                "level_names": {"type": "array", "items": {"type": "string"}},
                "level_elevations": {"type": "array", "items": {"type": "number"}},
            },
            "required": ["name", "x_grid_names", "x_grid_positions",
                         "y_grid_names", "y_grid_positions",
                         "level_names", "level_elevations"],
        },
    },
    {
        "name": "create_floors",
        "description": "创建多层楼板（合并 TC 4-5）",
        "inputSchema": {
            "type": "object",
            "properties": {
                "boundary_points": {
                    "type": "array",
                    "items": {"type": "array", "items": {"type": "number"}},
                    "description": "楼板轮廓点 [[x,y], ...]",
                },
                "levels": {"type": "array", "items": {"type": "string"}},
                "thickness": {"type": "number", "default": 150.0},
            },
            "required": ["boundary_points", "levels"],
        },
    },
    {
        "name": "place_columns",
        "description": "在轴网交点批量放置柱子（TC 7，粗粒度）",
        "inputSchema": {
            "type": "object",
            "properties": {
                "base_level": {"type": "string"},
                "top_level": {"type": "string"},
                "skip_x": {"type": "array", "items": {"type": "string"}},
                "skip_y": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["base_level", "top_level"],
        },
    },
    {
        "name": "create_walls",
        "description": "批量创建墙体（TC 8/14）",
        "inputSchema": {
            "type": "object",
            "properties": {
                "walls": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "start": {"type": "array", "items": {"type": "number"}},
                            "end": {"type": "array", "items": {"type": "number"}},
                            "base_level": {"type": "string"},
                            "top_level": {"type": "string"},
                            "wall_type": {"type": "string", "default": "interior"},
                        },
                        "required": ["start", "end", "base_level", "top_level"],
                    },
                },
            },
            "required": ["walls"],
        },
    },
    {
        "name": "create_opening",
        "description": "基于轴网参照的楼板开洞（TC 6，参照驱动）",
        "inputSchema": {
            "type": "object",
            "properties": {
                "x_grid_start": {"type": "string"},
                "x_grid_end": {"type": "string"},
                "y_grid_start": {"type": "string"},
                "y_grid_end": {"type": "string"},
                "target_slab_ids": {"type": "array", "items": {"type": "string"}},
                "inset": {"type": "number", "default": 500.0},
            },
            "required": ["x_grid_start", "x_grid_end",
                         "y_grid_start", "y_grid_end", "target_slab_ids"],
        },
    },
    {
        "name": "modify_element",
        "description": "修改构件参数并返回受影响的依赖链（TC 9/11）",
        "inputSchema": {
            "type": "object",
            "properties": {
                "element_id": {"type": "string"},
                "changes": {"type": "object"},
            },
            "required": ["element_id", "changes"],
        },
    },
    {
        "name": "check_compliance",
        "description": "执行规范合规检查（TC 16，最有价值的一步）",
        "inputSchema": {
            "type": "object",
            "properties": {
                "standards": {"type": "array", "items": {"type": "string"}},
                "scope": {"type": "array", "items": {"type": "string"}},
                "extra_info": {"type": "object"},
            },
        },
    },
    {
        "name": "export_model",
        "description": "导出建筑模型到独立文件夹（STEP + PNG + summary.json）",
        "inputSchema": {
            "type": "object",
            "properties": {
                "output_path": {"type": "string", "description": "输出根目录"},
                "formats": {
                    "type": "array",
                    "items": {"type": "string"},
                    "default": ["step", "png_3d", "png_plan", "summary"],
                    "description": "step / colored_step / ifc / glb / obj / stl / dae / dxf / png_3d / png_plan / summary",
                },
            },
            "required": ["output_path"],
        },
    },
    {
        "name": "get_summary",
        "description": "获取当前建筑状态摘要（上下文压缩，§7.1）",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "create_curtain_wall",
        "description": "创建幕墙（TC 13，网格分割+竖梃）",
        "inputSchema": {
            "type": "object",
            "properties": {
                "start": {"type": "array", "items": {"type": "number"}},
                "end": {"type": "array", "items": {"type": "number"}},
                "base_level": {"type": "string"},
                "top_level": {"type": "string"},
                "panel_width": {"type": "number", "default": 1500.0},
            },
            "required": ["start", "end", "base_level", "top_level"],
        },
    },
    {
        "name": "auto_place_doors",
        "description": "在内墙上自动放置办公室门（TC 15）",
        "inputSchema": {
            "type": "object",
            "properties": {
                "door_spacing": {"type": "number", "default": 4000.0},
                "door_width": {"type": "number", "default": 900.0},
                "door_height": {"type": "number", "default": 2100.0},
            },
        },
    },
    {
        "name": "place_beams",
        "description": "在轴网交点间自动放置结构梁",
        "inputSchema": {
            "type": "object",
            "properties": {
                "level": {"type": "string"},
                "beam_width": {"type": "number", "default": 300.0},
                "beam_height": {"type": "number", "default": 600.0},
            },
            "required": ["level"],
        },
    },
    {
        "name": "visual_check",
        "description": "执行视觉自检（TC 18，检查点节点）",
        "inputSchema": {
            "type": "object",
            "properties": {
                "screenshot_path": {"type": "string", "default": ""},
            },
        },
    },
    {
        "name": "create_staircase",
        "description": "创建楼梯（TC 10-12，失败返回可操作修复建议）",
        "inputSchema": {
            "type": "object",
            "properties": {
                "x_grid": {"type": "string", "description": "定位参照 X 轴线"},
                "y_grid": {"type": "string", "description": "定位参照 Y 轴线"},
                "base_level": {"type": "string"},
                "top_level": {"type": "string"},
                "offset_x": {"type": "number", "default": 0.0},
                "offset_y": {"type": "number", "default": 0.0},
                "width": {"type": "number", "default": 1200.0, "description": "梯段宽 (mm)"},
                "riser_height": {"type": "number", "default": 165.0, "description": "踏步高 (mm)"},
                "tread_depth": {"type": "number", "default": 280.0, "description": "踏步深 (mm)"},
                "stair_type": {
                    "type": "string", "default": "u_turn",
                    "enum": ["u_turn", "l_turn", "straight"],
                },
            },
            "required": ["x_grid", "y_grid", "base_level", "top_level"],
        },
    },
    {
        "name": "generate_report",
        "description": "生成交付报告（TC 20，约束状态 + 关键参数 + 未决事项）",
        "inputSchema": {
            "type": "object",
            "properties": {
                "compliance_result": {"type": "object", "description": "合规检查结果"},
                "exported_files": {"type": "array", "items": {"type": "string"}},
                "open_issues": {
                    "type": "array", "items": {"type": "string"},
                    "description": "用户指定的未决事项",
                },
            },
        },
    },
    {
        "name": "take_snapshot",
        "description": "保存当前 Building 状态快照（§7.1 上下文管理）",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "default": ""},
            },
        },
    },
    {
        "name": "rollback",
        "description": "回滚 Building 到指定快照版本（§7.2 状态回滚）",
        "inputSchema": {
            "type": "object",
            "properties": {
                "version": {"type": "integer"},
            },
            "required": ["version"],
        },
    },
    {
        "name": "state_diff",
        "description": "计算两个快照版本的差异（§7.2 状态 diff）",
        "inputSchema": {
            "type": "object",
            "properties": {
                "from_version": {"type": "integer"},
                "to_version": {"type": "integer"},
            },
            "required": ["from_version", "to_version"],
        },
    },
    {
        "name": "place_columns_at",
        "description": "在任意坐标位置批量放置柱子（适用于环形柱网、自由散布等非矩形柱网）",
        "inputSchema": {
            "type": "object",
            "properties": {
                "positions": {
                    "type": "array",
                    "items": {"type": "array", "items": {"type": "number"}},
                    "description": "柱位坐标 [[x, y], ...] (mm)",
                },
                "base_level": {"type": "string"},
                "top_level": {"type": "string"},
                "section_width": {"type": "number", "default": 400.0, "description": "截面宽 (mm)"},
                "section_depth": {"type": "number", "default": 400.0, "description": "截面深 (mm)"},
                "section_thickness": {"type": "number", "default": 0.0, "description": "壁厚 (mm, 0=实心)"},
                "material": {"type": "string", "default": "wood", "enum": ["steel", "concrete", "wood", "composite"]},
            },
            "required": ["positions", "base_level", "top_level"],
        },
    },
    {
        "name": "place_beams_at",
        "description": "在任意位置批量放置梁（环向梁、径向梁、斗拱短梁、交叉斜撑等）",
        "inputSchema": {
            "type": "object",
            "properties": {
                "beams": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "start": {"type": "array", "items": {"type": "number"}, "description": "[x, y] (mm)"},
                            "end": {"type": "array", "items": {"type": "number"}, "description": "[x, y] (mm)"},
                            "level": {"type": "string"},
                            "width": {"type": "number", "default": 250.0},
                            "height": {"type": "number", "default": 400.0},
                            "material": {"type": "string", "default": "wood"},
                        },
                        "required": ["start", "end", "level"],
                    },
                },
            },
            "required": ["beams"],
        },
    },
    {
        "name": "place_windows",
        "description": "在墙体上批量放置窗户",
        "inputSchema": {
            "type": "object",
            "properties": {
                "windows": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "host_wall_id": {"type": "string"},
                            "position": {"type": "number", "default": 0.5, "description": "沿墙体位置 (0~1)"},
                            "width": {"type": "number", "default": 1500.0},
                            "height": {"type": "number", "default": 1800.0},
                            "sill_height": {"type": "number", "default": 900.0},
                        },
                        "required": ["host_wall_id"],
                    },
                },
            },
            "required": ["windows"],
        },
    },
    {
        "name": "set_appearance",
        "description": "批量设置构件外观（颜色/透明度/材质预设）。预设: steel/concrete/wood/red_wall/marble/bronze/glazed_tile/glass/roof_tile",
        "inputSchema": {
            "type": "object",
            "properties": {
                "element_ids": {"type": "array", "items": {"type": "string"}, "description": "构件 ID 列表"},
                "color_rgb": {"type": "array", "items": {"type": "integer"}, "description": "[R, G, B] 各 0~255"},
                "opacity": {"type": "number", "default": 1.0, "description": "不透明度 0~1"},
                "preset": {"type": "string", "default": "", "description": "预设名称 (优先于 color_rgb)"},
            },
            "required": ["element_ids"],
        },
    },
    # ── LOD 300: 圆柱、曲面屋顶、栏杆 ──
    {
        "name": "place_round_columns_at",
        "description": "在任意坐标位置批量放置圆柱（传统建筑木柱、装饰柱、罗马柱等圆形截面柱）",
        "inputSchema": {
            "type": "object",
            "properties": {
                "positions": {
                    "type": "array",
                    "items": {"type": "array", "items": {"type": "number"}},
                    "description": "柱位坐标 [[x, y], ...] (mm)",
                },
                "base_level": {"type": "string"},
                "top_level": {"type": "string"},
                "diameter": {"type": "number", "default": 400.0, "description": "柱径 (mm)"},
                "material": {"type": "string", "default": "wood", "enum": ["steel", "concrete", "wood", "composite"]},
            },
            "required": ["positions", "base_level", "top_level"],
        },
    },
    {
        "name": "create_curved_roof",
        "description": "创建曲面屋顶（庑殿/歇山/硬山/攒尖顶）。支持类型: flat/gable/hip/half_hip/conical",
        "inputSchema": {
            "type": "object",
            "properties": {
                "base_level": {"type": "string", "description": "屋顶底面标高"},
                "boundary_points": {
                    "type": "array",
                    "items": {"type": "array", "items": {"type": "number"}},
                    "description": "屋顶底边轮廓 [[x,y], ...] (mm)",
                },
                "ridge_height": {"type": "number", "default": 3000.0, "description": "脊线高度 (mm)"},
                "roof_type": {"type": "string", "default": "hip", "enum": ["flat", "gable", "hip", "half_hip", "conical"]},
                "overhang": {"type": "number", "default": 1500.0, "description": "檐口出挑 (mm)"},
                "eave_rise": {"type": "number", "default": 0.0, "description": "檐口翤起高度 (mm)"},
                "thickness": {"type": "number", "default": 200.0, "description": "屋面厚度 (mm)"},
            },
            "required": ["base_level", "boundary_points"],
        },
    },
    {
        "name": "create_railing",
        "description": "沿路径创建栏杆/勾栏（自动生成立柱 + 扶手 + 可选底部横杆）",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path_points": {
                    "type": "array",
                    "items": {"type": "array", "items": {"type": "number"}},
                    "description": "栏杆路径点 [[x,y], ...] (mm)",
                },
                "level": {"type": "string", "description": "栏杆底面标高"},
                "height": {"type": "number", "default": 1100.0, "description": "栏杆总高 (mm)"},
                "post_spacing": {"type": "number", "default": 1500.0, "description": "立柱间距 (mm)"},
                "post_width": {"type": "number", "default": 80.0, "description": "立柱截面宽 (mm)"},
                "post_depth": {"type": "number", "default": 80.0, "description": "立柱截面深 (mm)"},
                "rail_width": {"type": "number", "default": 60.0, "description": "扶手截面宽 (mm)"},
                "rail_height": {"type": "number", "default": 60.0, "description": "扶手截面高 (mm)"},
                "bottom_rail": {"type": "boolean", "default": True, "description": "是否有底部横杆"},
                "material": {"type": "string", "default": "wood", "enum": ["steel", "concrete", "wood", "composite"]},
            },
            "required": ["path_points", "level"],
        },
    },
]


class MCPTransport:
    """stdio JSON-RPC transport for MCP protocol.

    处理 MCP 标准的 initialize / tools/list / tools/call 消息。
    """

    def __init__(self) -> None:
        self.mcp = GeometryKernelMCP()

    def handle_message(self, message: dict) -> dict | None:
        """处理单条 JSON-RPC 消息."""
        method = message.get("method", "")
        msg_id = message.get("id")
        params = message.get("params", {})

        if method == "initialize":
            return self._respond(msg_id, {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {
                    "name": "geometry-kernel-mcp",
                    "version": "0.2.0",
                },
            })

        if method == "notifications/initialized":
            return None  # notification, no response

        if method == "tools/list":
            return self._respond(msg_id, {"tools": TOOL_DEFINITIONS})

        if method == "tools/call":
            return self._handle_tool_call(msg_id, params)

        return self._error(msg_id, -32601, f"Method not found: {method}")

    def _handle_tool_call(self, msg_id: Any, params: dict) -> dict:
        """执行工具调用."""
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

        # 将 JSON 数组转为 tuple（boundary_points 等）
        if "boundary_points" in arguments:
            arguments["boundary_points"] = [tuple(p) for p in arguments["boundary_points"]]

        method_map = {
            "solve_constraints": self.mcp.solve_constraints,
            "validate_constraints": self.mcp.validate_constraints,
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
            "create_staircase": self.mcp.create_staircase,
            "generate_report": self.mcp.generate_report,
            "take_snapshot": self.mcp.take_snapshot,
            "rollback": self.mcp.rollback,
            "state_diff": self.mcp.state_diff,
            "place_columns_at": self.mcp.place_columns_at,
            "place_beams_at": self.mcp.place_beams_at,
            "place_windows": self.mcp.place_windows,
            "set_appearance": self.mcp.set_appearance,
            # LOD 300
            "place_round_columns_at": self.mcp.place_round_columns_at,
            "create_curved_roof": self.mcp.create_curved_roof,
            "create_railing": self.mcp.create_railing,
        }

        method = method_map.get(tool_name)
        if method is None:
            return self._error(msg_id, -32602, f"Unknown tool: {tool_name}")

        try:
            resp: ToolResponse = method(**arguments)
            return self._respond(msg_id, {
                "content": [
                    {"type": "text", "text": json.dumps(resp.to_dict(), ensure_ascii=False)},
                ],
            })
        except Exception as e:
            return self._respond(msg_id, {
                "content": [
                    {"type": "text", "text": json.dumps({
                        "status": "error",
                        "data": {"message": str(e)},
                    })},
                ],
                "isError": True,
            })

    def _respond(self, msg_id: Any, result: dict) -> dict:
        return {"jsonrpc": "2.0", "id": msg_id, "result": result}

    def _error(self, msg_id: Any, code: int, message: str) -> dict:
        return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}

    def run_stdio(self) -> None:
        """Run the MCP server on stdio (line-delimited JSON-RPC)."""
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                message = json.loads(line)
                response = self.handle_message(message)
                if response is not None:
                    sys.stdout.write(json.dumps(response) + "\n")
                    sys.stdout.flush()
            except json.JSONDecodeError:
                err = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}
                sys.stdout.write(json.dumps(err) + "\n")
                sys.stdout.flush()


def main():
    transport = MCPTransport()
    transport.run_stdio()


if __name__ == "__main__":
    main()
