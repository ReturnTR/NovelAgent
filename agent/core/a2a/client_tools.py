"""
A2A 客户端工具模块

提供：
1. A2AClient 类：封装与注册中心和目标 Agent 通信的逻辑
2. create_a2a_tools() 函数：创建三个 LangChain Tools，供 Agent 调用

三个 Tools：
- discover_agents: 发现可用 Agent
- send_agent_message: 同步发送消息（等待返回）
- send_agent_message_async: 异步发送消息（立即返回）

设计思路：
- 使用全局单例模式管理 A2AClient 实例
- 工具函数使用 asyncio.get_event_loop().run_until_complete() 在同步上下文中执行异步代码
- 区分同步/异步两种消息发送模式
"""

import asyncio
import uuid
import aiohttp
import requests
from typing import Dict, List, Optional, Any
from langchain_core.tools import tool
from datetime import datetime, timezone
from .types import AgentCard, A2AEvent, EventType, SendMessageMode


class A2AClient:
    """
    A2A 客户端

    负责：
    1. 与注册中心通信，发现可用 Agent
    2. 向目标 Agent 发送 A2A 事件
    3. 支持同步/异步两种发送模式

    每个 Agent 都有一个 A2AClient 实例，用于与其他 Agent 通信
    """

    def __init__(self, self_agent_id: str, registry_endpoint: str = "http://localhost:8000"):
        """
        初始化 A2A 客户端

        Args:
            self_agent_id: 当前 Agent 的 ID
            registry_endpoint: 注册中心地址，默认 "http://localhost:8000"
        """
        self.self_agent_id = self_agent_id  # 当前 Agent 的 ID
        self.registry_endpoint = registry_endpoint  # 注册中心地址
        self.session: Optional[aiohttp.ClientSession] = None  # HTTP 会话

    async def _ensure_session(self):
        """
        确保 HTTP 会话可用

        如果会话不存在或已关闭，则创建新会话
        使用单会话可以复用连接，提高性能
        """
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()

    async def close(self):
        """
        关闭 HTTP 会话

        在 Agent 关闭时调用，释放资源
        """
        if self.session and not self.session.closed:
            await self.session.close()

    def discover_agents(
        self,
        keywords: Optional[str] = None,
        agent_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        从注册中心发现可用 Agent

        Args:
            keywords: 搜索关键词（匹配名称、描述、能力）
            agent_type: 按 Agent 类型筛选

        Returns:
            符合条件的 Agent 列表（字典形式）
        """
        try:
            # 构建查询参数
            params = {}
            if keywords:
                params["keywords"] = keywords
            if agent_type:
                params["agent_type"] = agent_type

            # 调用注册中心的搜索接口
            response = requests.get(
                f"{self.registry_endpoint}/api/registry/search",
                params=params,
                timeout=30
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("agents", [])
            return []
        except Exception as e:
            print(f"[A2A Client] Error discovering agents: {e}")
            return []

    def send_event(
        self,
        target_endpoint: str,
        event: A2AEvent,
        timeout: int = 30
    ) -> Optional[A2AEvent]:
        """
        向目标 Agent 发送 A2A 事件（核心发送方法）

        这是 A2A 通信的核心方法：
        1. 构造 HTTP POST 请求
        2. 发送到目标 Agent 的 /a2a/event 端点
        3. 等待响应并返回

        Args:
            target_endpoint: 目标 Agent 的地址，如 "http://localhost:8002"
            event: 要发送的 A2A 事件
            timeout: 超时时间（秒）

        Returns:
            目标 Agent 返回的响应事件，或 None（如果失败）
        """
        try:
            # 发送 POST 请求到目标 Agent 的 /a2a/event 端点
            response = requests.post(
                f"{target_endpoint}/a2a/event",
                json=event.model_dump(),
                timeout=timeout
            )
            if response.status_code == 200:
                data = response.json()
                return A2AEvent(**data)
            return None
        except Exception as e:
            print(f"[A2A Client] Error sending event: {e}")
            return None

    def send_agent_message(
        self,
        target_agent_id: str,
        task: str,
        context: Optional[Dict[str, Any]] = None,
        mode: SendMessageMode = SendMessageMode.SYNC,
        timeout: int = 30
    ) -> Dict[str, Any]:
        """
        向指定 Agent 发送消息

        这是对外的主要接口，内部调用 send_event() 实际发送：

        同步模式流程：
        1. 发现目标 Agent 的地址
        2. 构造 TASK_REQUEST 事件
        3. 发送并等待响应
        4. 返回响应内容

        异步模式流程：
        1. 发现目标 Agent 的地址
        2. 构造 TASK_REQUEST 事件
        3. 发送（使用短超时）
        4. 立即返回，不等待结果

        Args:
            target_agent_id: 目标 Agent ID
            task: 任务描述
            context: 任务上下文
            mode: 发送模式（同步/异步）
            timeout: 超时时间

        Returns:
            同步模式：包含执行结果的字典
            异步模式：包含发送确认的字典
        """
        # 从注册中心查找目标 Agent
        target_agents = self.discover_agents()
        target_agent = next((a for a in target_agents if a.get("agent_id") == target_agent_id), None)

        # 目标 Agent 不存在
        if not target_agent:
            return {
                "success": False,
                "error": f"Agent {target_agent_id} not found"
            }

        # 构造 A2A 事件
        event = A2AEvent(
            event_id=f"evt-{str(uuid.uuid4())[:8]}",  # 生成唯一事件ID
            event_type=EventType.TASK_REQUEST,  # 任务请求类型
            source=self.self_agent_id,  # 发送方是当前 Agent
            target=target_agent_id,  # 接收方是目标 Agent
            task_id=f"task-{str(uuid.uuid4())[:8]}",  # 生成任务ID
            content={
                "task": task,  # 任务内容
                "context": context or {},  # 上下文
                "mode": mode.value,  # 发送模式
                "timeout": timeout  # 超时时间
            }
        )

        # 获取目标 Agent 的地址
        target_endpoint = target_agent.get("endpoint")

        # 根据模式发送
        if mode == SendMessageMode.SYNC:
            # 同步模式：等待目标 Agent 返回结果
            response_event = self.send_event(target_endpoint, event, timeout=timeout)
            if response_event:
                return {
                    "success": True,
                    "event": response_event.model_dump(),
                    "result": response_event.content.get("result")
                }
            return {
                "success": False,
                "error": "No response received"
            }
        else:
            # 异步模式：发送后立即返回
            self.send_event(target_endpoint, event, timeout=5)
            return {
                "success": True,
                "message": "Message sent asynchronously",
                "event_id": event.event_id,
                "task_id": event.task_id
            }


# ============================================================================
# 全局单例管理
# ============================================================================

# 全局 A2AClient 实例
_a2a_client_instance: Optional[A2AClient] = None


def init_a2a_client(self_agent_id: str, registry_endpoint: str = "http://localhost:8000"):
    """
    初始化全局 A2AClient 实例

    Args:
        self_agent_id: 当前 Agent 的 ID
        registry_endpoint: 注册中心地址
    """
    global _a2a_client_instance
    _a2a_client_instance = A2AClient(self_agent_id, registry_endpoint)


def get_a2a_client() -> A2AClient:
    """
    获取全局 A2AClient 实例

    Returns:
        A2AClient 实例

    Raises:
        RuntimeError: 如果未初始化
    """
    if _a2a_client_instance is None:
        raise RuntimeError("A2A Client not initialized. Call init_a2a_client() first.")
    return _a2a_client_instance


# ============================================================================
# LangChain Tools
# ============================================================================

def create_a2a_tools() -> List:
    """
    创建 A2A 相关的 LangChain Tools

    返回三个 Tool：
    1. discover_agents - 发现可用 Agent
    2. send_agent_message - 同步发送消息
    3. send_agent_message_async - 异步发送消息

    这些 Tool 可以被 LLM 调用，实现 Agent 之间的通信

    Returns:
        Tool 列表
    """

    @tool("discover_agents")
    def discover_agents(
        keywords: Optional[str] = None,
        agent_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        搜索和发现可用的 Agent

        Args:
            keywords: 搜索关键词，可以匹配 Agent 名称、描述或能力
            agent_type: 按 Agent 类型筛选，如 "character", "supervisor"

        Returns:
            找到的 Agent 列表，包含 AgentCard 信息

        Example:
            discover_agents(keywords="character")
            discover_agents(agent_type="character")
        """
        # 直接调用同步方法
        client = get_a2a_client()
        try:
            agents = client.discover_agents(keywords, agent_type)
            return {
                "success": True,
                "count": len(agents),
                "agents": agents
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    @tool("send_agent_message")
    def send_agent_message(
        target_agent_id: str,
        task: str,
        context: Optional[Dict[str, Any]] = None,
        timeout: int = 30
    ) -> Dict[str, Any]:
        """
        向指定的 Agent 发送消息（同步模式，等待返回结果）

        使用场景：
        - 需要等待目标 Agent 处理完成后才能继续
        - 需要获取目标 Agent 的执行结果

        Args:
            target_agent_id: 目标 Agent 的 ID
            task: 任务描述
            context: 任务上下文数据
            timeout: 超时时间（秒），默认 30 秒

        Returns:
            同步响应结果，包含：
            - success: 是否成功
            - result: 目标 Agent 返回的结果
            - error: 错误信息（如果失败）

        Example:
            send_agent_message(
                target_agent_id="character-001",
                task="创建一个勇敢的男主角",
                context={"novel_id": 1},
                timeout=60
            )
        """
        client = get_a2a_client()
        try:
            result = client.send_agent_message(
                target_agent_id=target_agent_id,
                task=task,
                context=context,
                mode=SendMessageMode.SYNC,
                timeout=timeout
            )
            return result
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    @tool("send_agent_message_async")
    def send_agent_message_async(
        target_agent_id: str,
        task: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        向指定的 Agent 发送消息（异步模式，发送后立即返回，不等待结果）

        使用场景：
        - 不需要立即获取结果
        - 目标 Agent 可以慢慢处理
        - 发送后当前 Agent 可以继续做其他事情

        特点：
        - timeout 固定为 0 或很小的值
        - 发送后立即返回，不等待目标 Agent 处理
        - 目标 Agent 处理完成后会通过 /a2a/event 回调

        Args:
            target_agent_id: 目标 Agent 的 ID
            task: 任务描述
            context: 任务上下文数据

        Returns:
            异步发送确认，包含：
            - success: 是否成功发送
            - message: 状态信息
            - event_id: 事件ID
            - task_id: 任务ID

        Example:
            send_agent_message_async(
                target_agent_id="character-001",
                task="创建一个勇敢的男主角",
                context={"novel_id": 1}
            )
        """
        client = get_a2a_client()
        try:
            result = client.send_agent_message(
                target_agent_id=target_agent_id,
                task=task,
                context=context,
                mode=SendMessageMode.ASYNC,
                timeout=0  # 异步模式，超时为 0
            )
            return result
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    return [discover_agents, send_agent_message, send_agent_message_async]
