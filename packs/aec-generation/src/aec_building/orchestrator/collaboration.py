"""多 Agent 协同 — 事件总线 + 角色分工协议.

对应案例 §7.3（多 Agent 分工）：
  架构 Agent + 结构 Agent + 合规 Agent + 机电 Agent 协同编排。

设计模式：
- EventBus: 发布/订阅机制，Agent 修改 Building 后广播事件
- AgentRole: 声明 Agent 的职责范围和可调用的 MCP 工具
- CollaborationSession: 管理多个 Agent 的交互会话

关键约束：
- 单一 Building 实例作为共享状态（线程安全由上层保证）
- 事件是不可变的 dataclass，可序列化
- 每个 Agent 只能修改自己 role 声明的构件类型
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class EventType(Enum):
    """Building 事件类型."""

    ELEMENT_ADDED = "element_added"
    ELEMENT_MODIFIED = "element_modified"
    ELEMENT_REMOVED = "element_removed"
    OPENING_ADDED = "opening_added"
    STAIRCASE_ADDED = "staircase_added"
    GRID_MODIFIED = "grid_modified"
    COMPLIANCE_CHECKED = "compliance_checked"
    SNAPSHOT_TAKEN = "snapshot_taken"
    EXPORT_COMPLETED = "export_completed"


@dataclass(frozen=True)
class BuildingEvent:
    """不可变事件.

    Attributes:
        event_type: 事件类型。
        source_agent: 发起事件的 Agent 角色名。
        element_id: 相关构件 ID（如适用）。
        data: 事件数据负载。
        timestamp: 事件时间戳。
    """

    event_type: EventType
    source_agent: str
    element_id: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


# 事件处理器类型
EventHandler = Callable[[BuildingEvent], None]


class EventBus:
    """发布/订阅事件总线.

    Agent 订阅感兴趣的事件类型，当其他 Agent 修改 Building 时收到通知。

    用法::

        bus = EventBus()
        bus.subscribe(EventType.ELEMENT_ADDED, compliance_agent.on_element_added)
        bus.publish(BuildingEvent(
            event_type=EventType.ELEMENT_ADDED,
            source_agent="structural",
            element_id="col_0001",
        ))
    """

    def __init__(self) -> None:
        self._handlers: dict[EventType, list[EventHandler]] = {}
        self._history: list[BuildingEvent] = []

    def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """订阅事件类型."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    def unsubscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """取消订阅."""
        if event_type in self._handlers:
            self._handlers[event_type] = [
                h for h in self._handlers[event_type] if h is not handler
            ]

    def publish(self, event: BuildingEvent) -> None:
        """发布事件，通知所有订阅者."""
        self._history.append(event)
        for handler in self._handlers.get(event.event_type, []):
            handler(event)

    @property
    def history(self) -> list[BuildingEvent]:
        return list(self._history)

    def history_since(self, timestamp: float) -> list[BuildingEvent]:
        """获取指定时间戳之后的事件."""
        return [e for e in self._history if e.timestamp > timestamp]

    def clear_history(self) -> None:
        self._history.clear()


@dataclass
class AgentRole:
    """Agent 角色声明.

    定义一个 Agent 的职责范围：
    - 可操作的构件类型
    - 可调用的 MCP 工具
    - 订阅的事件类型

    用于防止 Agent 越权操作和冲突检测。
    """

    name: str
    description: str
    allowed_element_types: list[str] = field(default_factory=list)
    allowed_tools: list[str] = field(default_factory=list)
    subscribed_events: list[EventType] = field(default_factory=list)

    def can_modify(self, element_type: str) -> bool:
        """检查是否有权修改该类型构件."""
        return element_type in self.allowed_element_types or "*" in self.allowed_element_types

    def can_call(self, tool_name: str) -> bool:
        """检查是否有权调用该工具."""
        return tool_name in self.allowed_tools or "*" in self.allowed_tools


# ── 预定义角色 ──

STRUCTURAL_AGENT = AgentRole(
    name="structural",
    description="结构 Agent — 负责柱、梁、楼板结构属性",
    allowed_element_types=["Column", "FloorSlab"],
    allowed_tools=["create_project", "create_floors", "place_columns", "modify_element", "get_summary"],
    subscribed_events=[EventType.GRID_MODIFIED, EventType.OPENING_ADDED],
)

ARCHITECTURAL_AGENT = AgentRole(
    name="architectural",
    description="建筑 Agent — 负责墙体、幕墙、门窗、楼梯",
    allowed_element_types=["Wall", "CurtainWall", "Door", "Window", "Staircase"],
    allowed_tools=[
        "create_project", "create_walls", "create_curtain_wall",
        "auto_place_doors", "create_opening", "modify_element", "get_summary",
    ],
    subscribed_events=[EventType.ELEMENT_ADDED, EventType.ELEMENT_MODIFIED],
)

COMPLIANCE_AGENT = AgentRole(
    name="compliance",
    description="合规 Agent — 负责规范检查，只读不写",
    allowed_element_types=[],
    allowed_tools=["check_compliance", "get_summary", "visual_check"],
    subscribed_events=[
        EventType.ELEMENT_ADDED, EventType.ELEMENT_MODIFIED,
        EventType.STAIRCASE_ADDED, EventType.OPENING_ADDED,
    ],
)

ORCHESTRATOR_AGENT = AgentRole(
    name="orchestrator",
    description="编排 Agent — 全权限，协调其他 Agent",
    allowed_element_types=["*"],
    allowed_tools=["*"],
    subscribed_events=[EventType.COMPLIANCE_CHECKED, EventType.EXPORT_COMPLETED],
)


@dataclass
class CollaborationSession:
    """多 Agent 协同会话.

    管理一次建筑设计的完整协同过程：
    - 注册参与的 Agent 角色
    - 通过 EventBus 广播变更
    - 维护 Building + StateManager
    - 提供权限检查
    """

    building: Any  # Building
    event_bus: EventBus = field(default_factory=EventBus)
    _agents: dict[str, AgentRole] = field(default_factory=dict)

    def register_agent(self, role: AgentRole) -> None:
        """注册 Agent 角色."""
        self._agents[role.name] = role
        # 自动订阅声明的事件
        for event_type in role.subscribed_events:
            # 创建一个默认日志处理器
            pass  # 实际的 handler 由 Agent 自己注册

    def check_permission(self, agent_name: str, tool_name: str) -> bool:
        """检查 Agent 是否有权调用指定工具."""
        role = self._agents.get(agent_name)
        if role is None:
            return False
        return role.can_call(tool_name)

    def check_element_permission(self, agent_name: str, element_type: str) -> bool:
        """检查 Agent 是否有权修改指定类型构件."""
        role = self._agents.get(agent_name)
        if role is None:
            return False
        return role.can_modify(element_type)

    @property
    def agents(self) -> dict[str, AgentRole]:
        return dict(self._agents)

    def status(self) -> dict[str, Any]:
        """会话状态摘要."""
        return {
            "agents": {name: role.description for name, role in self._agents.items()},
            "event_count": len(self.event_bus.history),
            "building_summary": self.building.summary() if self.building else {},
        }
