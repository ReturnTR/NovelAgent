"""
A2A 协议数据类型定义

定义了 Agent-to-Agent 通信所需的核心数据结构：
- AgentCard: Agent 的元数据描述（相当于 Agent 的"数字名片"）
- A2AEvent: Agent 之间传递的事件消息
- EventType: 事件的类型枚举
- SendMessageMode: 消息发送模式（同步/异步）
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from enum import Enum
from datetime import datetime


class AgentCapability(BaseModel):
    """Agent 能力描述"""
    name: str  # 能力名称，如 "create_character"
    description: str  # 能力描述
    parameters: Dict[str, str] = Field(default_factory=dict)  # 能力参数定义


class AgentCard(BaseModel):
    """
    Agent 数字名片 - 用于服务发现和注册

    每个 Agent 启动时会创建一个 AgentCard，描述自己的：
    - 基本信息（ID、名称、类型、版本）
    - 网络位置（endpoint）
    - 能力列表（capabilities）
    - 状态（status）
    """
    agent_id: str  # Agent 唯一标识
    agent_name: str  # Agent 显示名称
    agent_type: str  # Agent 类型，如 "supervisor", "character"
    endpoint: str  # Agent 服务地址，如 "http://localhost:8001"
    version: str = "1.0.0"  # 版本号
    description: str = ""  # Agent 描述
    capabilities: List[AgentCapability] = Field(default_factory=list)  # 支持的能力列表
    status: str = "active"  # 状态：active, inactive, error
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")  # 创建时间
    last_heartbeat: Optional[str] = None  # 最后心跳时间
    metadata: Dict[str, Any] = Field(default_factory=dict)  # 额外元数据


class EventType(str, Enum):
    """
    A2A 事件类型枚举

    - TASK_REQUEST: 请求其他 Agent 执行任务
    - TASK_RESPONSE: 任务执行结果响应
    - TASK_PROGRESS: 任务进度报告
    - AGENT_DISCOVERY: Agent 发现请求
    - AGENT_REGISTER: Agent 注册请求
    - AGENT_UNREGISTER: Agent 注销请求
    - HEARTBEAT: 心跳检测
    - ERROR: 错误报告
    """
    TASK_REQUEST = "task_request"
    TASK_RESPONSE = "task_response"
    TASK_PROGRESS = "task_progress"
    AGENT_DISCOVERY = "agent_discovery"
    AGENT_REGISTER = "agent_register"
    AGENT_UNREGISTER = "agent_unregister"
    HEARTBEAT = "heartbeat"
    ERROR = "error"
    USER_MESSAGE = "user_message"  # Web Console 发起的用户消息


class A2AEvent(BaseModel):
    """
    A2A 事件 - Agent 之间传递的消息单位

    类似于 HTTP 请求/响应模型：
    - event_id: 消息唯一ID
    - event_type: 消息类型（见 EventType）
    - source: 发送方 Agent ID
    - target: 接收方 Agent ID（可选，用于点对点通信）
    - task_id: 关联的任务ID
    - timestamp: 发送时间
    - content: 消息内容（任务描述、参数、结果等）
    - metadata: 额外元数据
    """
    event_id: str  # 事件唯一标识
    event_type: EventType  # 事件类型
    source: str  # 发送方 Agent ID
    target: Optional[str] = None  # 接收方 Agent ID，None 表示广播
    task_id: Optional[str] = None  # 关联的任务ID
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")  # 时间戳
    content: Dict[str, Any] = Field(default_factory=dict)  # 消息内容
    metadata: Dict[str, Any] = Field(default_factory=dict)  # 额外元数据

    class Config:
        json_schema_extra = {
            "example": {
                "event_id": "evt-001",
                "event_type": "task_request",
                "source": "supervisor-001",
                "target": "character-001",
                "task_id": "task-001",
                "timestamp": "2024-04-17T10:00:00Z",
                "content": {
                    "task": "创建一个勇敢的男主角",
                    "context": {}
                }
            }
        }


class SendMessageMode(str, Enum):
    """
    消息发送模式

    - SYNC: 同步模式，会等待目标 Agent 返回结果
    - ASYNC: 异步模式，发送后立即返回，不等待结果
    """
    SYNC = "sync"
    ASYNC = "async"
