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
- AgentRegistryServer: 集中式注册中心
- A2AClient: A2A 客户端
- A2AEventServer: A2A 事件服务器

工具函数：
- create_a2a_tools(): 创建 LangChain Tools

使用方式：
1. 注册中心由 Web Console Backend 提供
2. Agent 启动时创建 A2AClient 和 A2AEventServer
3. Agent 通过 A2AClient 发现和发送消息
4. 其他 Agent 通过 A2AEventServer 接收消息
"""

from .types import (
    AgentCapability,
    AgentCard,
    A2AEvent,
    EventType,
    SendMessageMode
)
from .registry_server import AgentRegistryServer, get_registry
from .client_tools import (
    A2AClient,
    init_a2a_client,
    get_a2a_client,
    create_a2a_tools
)
from .event_server import A2AEventServer
from .event_handler import A2AEventHandler

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
    # 客户端
    "A2AClient",
    "init_a2a_client",
    "get_a2a_client",
    "create_a2a_tools",
    # 服务端
    "A2AEventServer",
    # 事件处理器
    "A2AEventHandler"
]
