"""
A2A 事件服务器模块

负责：
1. 接收来自其他 Agent 的 A2A 事件
2. 处理不同类型的事件（任务请求、心跳等）
3. 触发 LangGraph 处理循环

核心设计：
- 每个 Agent 都有自己的 A2AEventServer
- 使用 FastAPI 提供 HTTP 端点
- 注入 A2AEventHandler 进行事件处理
- /event 端点返回 StreamingResponse 实现流式响应
"""

from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .event_handler import A2AEventHandler
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from .types import A2AEvent, EventType, AgentCard
from .registry_server import get_registry


class A2AEventServer:
    """
    A2A 事件服务器

    每个 Agent 拥有一个 A2AEventServer，用于：
    1. 接收其他 Agent 发送的事件
    2. 处理任务请求
    3. 返回流式响应

    端点：
    - /.well-known/agent-card.json: 获取 AgentCard
    - /event: 接收事件并返回流式响应
    - /register: 注册到中心
    - /health: 健康检查
    """

    def __init__(
        self,
        self_agent_card: AgentCard,
        event_handler: Optional['A2AEventHandler'] = None
    ):
        """
        初始化 A2A 事件服务器

        Args:
            self_agent_card: 当前 Agent 的 AgentCard
            event_handler: A2A 事件处理器（注入）
        """
        self.self_agent_card = self_agent_card
        self.event_handler = event_handler

        # 创建 FastAPI 应用并设置路由
        self.app = FastAPI(title=f"{self_agent_card.agent_name} A2A Server")
        self._setup_routes()

    def _setup_routes(self):
        """
        设置 FastAPI 路由

        端点列表：
        - GET /.well-known/agent-card.json: 返回 AgentCard
        - POST /event: 接收事件，返回流式响应
        - POST /register: 注册到注册中心
        - GET /health: 健康检查
        """

        @self.app.get("/.well-known/agent-card.json")
        async def get_agent_card():
            """返回当前 Agent 的 AgentCard，用于服务发现"""
            return JSONResponse(content=self.self_agent_card.model_dump())

        @self.app.post("/event")
        async def handle_event(request: Request):
            """
            核心端点：根据 event_type 分发到不同 Handler

            处理流程：
            1. 解析请求体为 A2AEvent
            2. 根据 event_type 分发：
               - USER_MESSAGE -> handle_user_message()
               - 其他 A2A 事件 -> handle_event()
            3. 返回 StreamingResponse 流式响应

            Returns:
                StreamingResponse (text/event-stream)
            """
            try:
                data = await request.json()
                event = A2AEvent(**data)
                print(f"[A2A Server] Received event: {event.event_id} type={event.event_type} from={event.source}")

                if event.event_type == EventType.USER_MESSAGE:
                    # 用户消息 -> handle_user_message
                    task = event.content.get("task", "")
                    session_id = event.content.get("session_id", "default")
                    return StreamingResponse(
                        self.event_handler.handle_user_message(task, session_id),
                        media_type="text/event-stream"
                    )
                else:
                    # A2A 事件 -> handle_event
                    return StreamingResponse(
                        self.event_handler.handle_event(event),
                        media_type="text/event-stream"
                    )

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

    def get_app(self) -> FastAPI:
        """
        获取 FastAPI 应用实例

        用于将 A2A 事件服务器挂载到主应用

        Returns:
            FastAPI 应用实例
        """
        return self.app