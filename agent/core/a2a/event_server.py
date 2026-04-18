"""
A2A 事件服务器模块

负责：
1. 接收来自其他 Agent 的 A2A 事件
2. 处理不同类型的事件（任务请求、心跳等）
3. 触发 LangGraph 处理循环

核心设计：
- 每个 Agent 都有自己的 A2AEventServer
- 使用 FastAPI 提供 HTTP 端点
- 事件到达后存入 pending_events 队列，下次 process_task() 时处理
"""

import asyncio
import uuid
from typing import Optional, Callable, Dict, Any
from datetime import datetime, timezone
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from .types import A2AEvent, EventType, AgentCard, AgentCapability
from .registry_server import get_registry


class A2AEventServer:
    """
    A2A 事件服务器

    每个 Agent 拥有一个 A2AEventServer，用于：
    1. 接收其他 Agent 发送的事件
    2. 处理任务请求
    3. 返回响应

    端点：
    - /.well-known/agent-card.json: 获取 AgentCard
    - /a2a/event: 接收事件
    - /a2a/register: 注册到中心
    - /a2a/health: 健康检查
    """

    def __init__(
        self,
        self_agent_card: AgentCard,
        on_event_received: Optional[Callable[[A2AEvent], Any]] = None,
        on_task_request: Optional[Callable[[A2AEvent], Any]] = None
    ):
        """
        初始化 A2A 事件服务器

        Args:
            self_agent_card: 当前 Agent 的 AgentCard
            on_event_received: 收到任意事件时的回调
            on_task_request: 收到任务请求时的回调
        """
        self.self_agent_card = self_agent_card  # 当前 Agent 的 AgentCard
        self.on_event_received = on_event_received  # 事件接收回调
        self.on_task_request = on_task_request  # 任务请求回调
        self.pending_events: Dict[str, A2AEvent] = {}  # 待处理的事件

        # 创建 FastAPI 应用并设置路由
        self.app = FastAPI(title=f"{self_agent_card.agent_name} A2A Server")
        self._setup_routes()

    def _setup_routes(self):
        """
        设置 FastAPI 路由

        端点列表：
        - GET /.well-known/agent-card.json: 返回 AgentCard
        - POST /a2a/event: 接收事件
        - POST /a2a/register: 注册到注册中心
        - GET /a2a/health: 健康检查
        """

        @self.app.get("/.well-known/agent-card.json")
        async def get_agent_card():
            """返回当前 Agent 的 AgentCard，用于服务发现"""
            return JSONResponse(content=self.self_agent_card.model_dump())
        
        @self.app.post("/event")
        async def handle_event(request: Request):
            """
            核心端点：接收 A2A 事件

            处理流程：
            1. 解析请求体为 A2AEvent
            2. 如果有 on_event_received 回调，异步调用
            3. 如果是 TASK_REQUEST 类型，调用 on_task_request 处理
            4. 返回 ACK 确认

            Returns:
                JSON 响应（A2AEvent 或确认消息）
            """
            try:
                data = await request.json()
                event = A2AEvent(**data)

                print(f"[A2A Server] Received event: {event.event_id} type={event.event_type} from={event.source}")

                # 如果注册了事件接收回调，异步处理
                if self.on_event_received:
                    asyncio.create_task(self._call_handler(self.on_event_received, event))

                # 如果是任务请求，调用任务处理回调
                if event.event_type == EventType.TASK_REQUEST:
                    if self.on_task_request:
                        response_event = await self._handle_task_request(event)
                        if response_event:
                            return JSONResponse(content=response_event.model_dump())

                # 返回确认响应
                ack_event = A2AEvent(
                    event_id=f"evt-{str(uuid.uuid4())[:8]}",
                    event_type=EventType.TASK_RESPONSE,
                    source=self.self_agent_card.agent_id,
                    target=event.source,
                    task_id=event.task_id,
                    content={
                        "status": "received",
                        "message": "Event received"
                    }
                )

                return JSONResponse(content=ack_event.model_dump())

            except Exception as e:
                print(f"[A2A Server] Error handling event: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/register")
        async def register_with_registry():
            """
            将当前 Agent 注册到注册中心

            通常在 Agent 启动时调用
            """
            try:
                registry = get_registry()
                await registry.register_agent(self.self_agent_card)
                return {"success": True, "message": "Agent registered"}
            except Exception as e:
                return {"success": False, "error": str(e)}

        @self.app.get("/health")
        async def health_check():
            """健康检查端点"""
            return {
                "status": "healthy",
                "agent_id": self.self_agent_card.agent_id,
                "agent_name": self.self_agent_card.agent_name
            }

    async def _call_handler(self, handler: Callable, event: A2AEvent):
        """
        调用事件处理回调

        Args:
            handler: 回调函数
            event: 事件对象
        """
        try:
            # 判断是否是异步函数
            if asyncio.iscoroutinefunction(handler):
                await handler(event)
            else:
                handler(event)
        except Exception as e:
            print(f"[A2A Server] Error in event handler: {e}")

    async def _handle_task_request(self, event: A2AEvent) -> Optional[A2AEvent]:
        """
        处理任务请求事件

        调用 on_task_request 回调，执行实际任务处理：

        同步模式：
        1. 提取任务内容
        2. 调用 on_task_request 处理
        3. 返回结果

        异步模式：
        1. 提取任务内容
        2. 异步调用 on_task_request（不等待）
        3. 返回"正在处理"确认

        Args:
            event: TASK_REQUEST 事件

        Returns:
            响应事件，或 None
        """
        try:
            if self.on_task_request:
                if asyncio.iscoroutinefunction(self.on_task_request):
                    result = await self.on_task_request(event)
                else:
                    result = self.on_task_request(event)

                # 构造响应事件
                response_event = A2AEvent(
                    event_id=f"evt-{str(uuid.uuid4())[:8]}",
                    event_type=EventType.TASK_RESPONSE,
                    source=self.self_agent_card.agent_id,
                    target=event.source,
                    task_id=event.task_id,
                    content={
                        "status": "completed",
                        "result": result
                    }
                )
                return response_event

        except Exception as e:
            print(f"[A2A Server] Error handling task request: {e}")
            # 返回错误事件
            error_event = A2AEvent(
                event_id=f"evt-{str(uuid.uuid4())[:8]}",
                event_type=EventType.ERROR,
                source=self.self_agent_card.agent_id,
                target=event.source,
                task_id=event.task_id,
                content={
                    "error": str(e)
                }
            )
            return error_event

        return None

    def get_app(self) -> FastAPI:
        """
        获取 FastAPI 应用实例

        用于将 A2A 事件服务器挂载到主应用

        Returns:
            FastAPI 应用实例
        """
        return self.app
