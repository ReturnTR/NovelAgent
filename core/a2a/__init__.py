"""
A2A 模块 - Agent-to-Agent 通信框架

提供完整的 Agent 间通信机制，包括：

数据模型：
- AgentCard: Agent 数字名片
- A2AEvent: A2A 事件消息
- EventType: 事件类型枚举
- SendMessageMode: 发送模式（同步/异步）
- AgentCapability: Agent 能力描述

核心组件：
- A2AEventServer: 统一的 A2A 服务（接收+发送+Session+A2A Tools）
- AgentRegistryServer: 集中式注册中心

使用方式：
1. 注册中心由 Web Console Backend 提供
2. Agent 启动时创建 A2AEventServer
3. Agent 通过 A2AEventServer.tools 发现和发送消息
4. 其他 Agent 通过 A2AEventServer.app 接收消息
"""

from .types import (
    AgentCapability,
    AgentCard,
    A2AEvent,
    EventType,
    SendMessageMode
)
from .registry_server import AgentRegistryServer, get_registry
from .event_server import A2AEventServer

# 为了向后兼容，保留旧类名的导出
from .event_server import A2AEventServer as A2AEventHandler


def create_a2a_tools():
    """
    兼容旧接口：创建 A2A 工具列表

    注意：新的设计使用 A2AEventServer.tools 获取工具
    此函数仅用于向后兼容
    """
    return []

__all__ = [
    # 数据模型
    "AgentCapability",
    "AgentCard",
    "A2AEvent",
    "EventType",
    "SendMessageMode",
    # 注册中心
    "AgentRegistryServer",
    "get_registry",
    # 统一服务（同时包含接收、发送、Session、A2A Tools）
    "A2AEventServer",
    # 向后兼容别名
    "A2AEventHandler"
]