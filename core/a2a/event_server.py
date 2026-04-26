"""
A2A 事件服务器模块

专门负责服务端通信能力：
1. 接收端：处理来自其他 Agent 的 A2A 事件
2. 发送端：向其他 Agent 发送消息
3. Session 管理：维护会话历史
4. A2A Tools：提供给 LLM 调用的工具

核心设计：
- 不依赖 BaseAgent，只通过接口协议与核心能力交互
- 使用 FastAPI 提供 HTTP 端点
- 内部管理 Session 历史
- 暴露 A2A Tools 给 LLM 调用

子模块：
- session.py: Session 管理
- client.py: A2A 客户端（发现/发送/tools）
- routes.py: FastAPI 路由
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional, AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .types import A2AEvent, AgentCard
from .session import SessionManager
from .client import A2AClient
from .routes import setup_routes


def _now_iso() -> str:
    """返回当前 UTC 时间 ISO 格式"""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class A2AEventServer:
    """
    A2A 事件服务器（统一版本）

    整合了接收、发送、Session管理、A2A Tools 的完整能力：

    端点：
    - GET /.well-known/agent-card.json: 获取 AgentCard
    - POST /event: 接收事件，返回流式响应
    - GET /health: 健康检查

    工具（供 LLM 调用）：
    - discover_agents: 发现可用 Agent
    - send_agent_message: 同步发送消息
    - send_agent_message_async: 异步发送消息
    """

    def __init__(
        self,
        agent_id: str,
        config: Dict[str, Any],
        agent_dir: Path,
        port: int,
        registry_endpoint: str = "http://localhost:8000",
        session_dir: Optional[str] = None,
        agent_class: Optional[type] = None,
    ):
        """
        初始化 A2A 事件服务器

        Args:
            agent_id: Agent 唯一标识
            config: Agent 配置字典
            agent_dir: Agent 配置目录
            port: 服务端口
            registry_endpoint: 注册中心地址
            session_dir: Session 文件存储目录，默认在 agent_dir/sessions
            agent_class: Agent 类，用于创建实例
        """
        self.agent_id = agent_id
        self.config = config
        self.agent_dir = agent_dir
        self.port = port
        self.registry_endpoint = registry_endpoint

        # 如果传入的是类，则创建实例
        if isinstance(agent_class, type):
            self.agent = agent_class(config=config, agent_dir=agent_dir)
        else:
            self.agent = agent_class

        # 从 config 中提取信息
        self.agent_name = config.get("agent_name", "Unknown")
        self.agent_type = config.get("agent_type", "unknown")
        self.capabilities = config.get("capabilities", [])

        # 构建 AgentCard
        self.self_agent_card = AgentCard.from_config(
            agent_id=self.agent_id,
            agent_name=self.agent_name,
            agent_type=self.agent_type,
            endpoint=f"http://localhost:{self.port}",
            config=config
        )

        # Session 管理
        if session_dir is None:
            session_dir = str(Path(agent_dir) / "sessions")
        self.session_manager = SessionManager(session_dir, self.agent_id)

        # A2A 客户端
        self.a2a_client = A2AClient(self.agent_id, self.registry_endpoint)

        # 创建 A2A Tools
        self.a2a_tools = self.a2a_client.get_tools()

        # 创建 FastAPI 应用
        self.app = FastAPI(title=f"{self.agent_name} A2A Server")
        self._setup_cors()
        setup_routes(
            app=self.app,
            agent=self.agent,
            agent_card=self.self_agent_card,
            agent_name=self.agent_name,
            agent_type=self.agent_type,
            port=self.port,
            capabilities=self.capabilities,
            tools=self.a2a_tools,
            session_manager=self.session_manager,
            registry_endpoint=self.registry_endpoint,
            handle_user_message=self.handle_user_message,
            handle_event=self.handle_event,
        )

        # 让 Agent 注入 A2A Tools
        self.agent.add_tools_and_restart(self.a2a_tools)

    def _setup_cors(self):
        """添加 CORS 中间件"""
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # =========================================================================
    # 事件处理
    # =========================================================================

    async def handle_user_message(self, task: str, session_id: str) -> AsyncIterator[Dict]:
        """处理用户消息（来自 Web Console）"""
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"[handle_user_message] session_id={session_id}, task={task[:50]}...")

        # 确保该 session 是唯一的 active session
        self.session_manager.ensure_active_session(session_id)
        self.session_manager._get_or_create_session(session_id)

        # 获取历史记录（在保存当前消息之前，避免重复）
        history = self.session_manager.get_session_history(session_id)
        logger.info(f"[handle_user_message] history length={len(history)}")

        user_msg = {
            "type": "message",
            "role": "user",
            "content": task,
            "timestamp": _now_iso()
        }

        first_event_yielded = False
        try:
            async for event in self.agent.process_task_stream(task, history):
                # 在第一个事件之前保存用户消息（确保消息先写入 session 文件）
                if not first_event_yielded:
                    self.session_manager._append_message_to_session_file(session_id, user_msg)
                    first_event_yielded = True

                evt_type = event.get("type")
                logger.info(f"[handle_user_message] event type={evt_type}")

                if evt_type == "reasoning":
                    reasoning_content_value = event.get("content", "")
                    reasoning_msg = {
                        "type": "message",
                        "role": "assistant",
                        "content": "",
                        "reasoning_content": reasoning_content_value,
                        "timestamp": _now_iso()
                    }
                    reasoning_msg = {k: v for k, v in reasoning_msg.items() if v}
                    self.session_manager._append_message_to_session_file(session_id, reasoning_msg)
                    yield event

                elif evt_type == "assistant":
                    content = event.get("content", "")
                    assistant_msg = {
                        "type": "message",
                        "role": "assistant",
                        "content": content,
                        "timestamp": _now_iso()
                    }
                    assistant_msg = {k: v for k, v in assistant_msg.items() if v}
                    self.session_manager._append_message_to_session_file(session_id, assistant_msg)
                    yield event

                elif evt_type == "tool_call":
                    tool_calls = event.get("tool_calls", [])
                    tool_call_msg = {
                        "type": "message",
                        "role": "assistant",
                        "tool_calls": tool_calls,
                        "timestamp": _now_iso()
                    }
                    self.session_manager._append_message_to_session_file(session_id, tool_call_msg)
                    yield event

                elif evt_type == "tool_result":
                    tool_result = event.get("content", "")
                    tool_call_id = event.get("tool_call_id", "")
                    tool_msg = {
                        "type": "message",
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "content": tool_result,
                        "timestamp": _now_iso()
                    }
                    self.session_manager._append_message_to_session_file(session_id, tool_msg)
                    yield event

                elif evt_type == "done":
                    yield event
        except Exception:
            # 确保用户消息被保存（即使处理失败）
            if not first_event_yielded:
                self.session_manager._append_message_to_session_file(session_id, user_msg)
            raise

    async def handle_event(self, event: A2AEvent) -> AsyncIterator[Dict]:
        """处理 A2A 事件（Agent 间通信）"""
        source = event.source
        session_id = f"a2a_{source}"
        self.session_manager._get_or_create_session(session_id)

        request_msg = {
            "type": "agent_request",
            "role": "user",  # 来自其他 Agent 的请求当作 user 消息
            "source_agent_id": source,
            "target_agent_id": event.target,
            "content": event.content.get("task", ""),
            "event_id": event.event_id,
            "timestamp": _now_iso()
        }
        self.session_manager._append_message_to_session_file(session_id, request_msg)

        task = event.content.get("task", "")
        # 1. 加载自己的 A2A 会话历史（Agent 的上下文由自己维护）
        session_history = self.session_manager.get_session_history(session_id)
        # 2. 合并传入的请求信息（如果有消息格式的上下文则合并）
        # incoming_context 可能是 dict（额外参数）或 list（消息历史）
        incoming_context = event.content.get("context")
        if isinstance(incoming_context, list) and incoming_context:
            context = session_history + incoming_context
        else:
            context = session_history

        response_content = ""
        async for evt in self.agent.process_task_stream(task, context):
            evt_type = evt.get("type")

            if evt_type == "tool_call":
                tool_call_msg = {
                    "type": "message",
                    "role": "assistant",
                    "tool_calls": evt.get("tool_calls", []),
                    "timestamp": _now_iso()
                }
                self.session_manager._append_message_to_session_file(session_id, tool_call_msg)
            elif evt_type == "tool_result":
                tool_result_msg = {
                    "type": "message",
                    "role": "tool",
                    "tool_call_id": evt.get("tool_call_id", ""),
                    "content": evt.get("content", ""),
                    "timestamp": _now_iso()
                }
                self.session_manager._append_message_to_session_file(session_id, tool_result_msg)
            elif evt_type == "assistant":
                response_content = evt.get("content", "")
                assistant_msg = {
                    "type": "message",
                    "role": "assistant",
                    "content": response_content,
                    "timestamp": _now_iso()
                }
                self.session_manager._append_message_to_session_file(session_id, assistant_msg)

            yield evt

        if response_content:
            response_msg = {
                "type": "agent_response",
                "role": "assistant",  # Agent 的响应当作 assistant 消息
                "source_agent_id": self.agent_id,
                "target_agent_id": source,
                "content": response_content,
                "event_id": event.event_id,
                "timestamp": _now_iso()
            }
            self.session_manager._append_message_to_session_file(session_id, response_msg)

    # =========================================================================
    # 兼容性方法
    # =========================================================================

    def get_app(self) -> FastAPI:
        """获取 FastAPI 应用"""
        return self.app
