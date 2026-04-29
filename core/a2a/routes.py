"""
FastAPI 路由模块

负责注册所有 HTTP 端点：
- AgentCard
- Session API
- Chat API
- A2A Event API
- Health Check
"""

import os
import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import aiohttp
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse


def _now_iso() -> str:
    """返回当前 UTC 时间 ISO 格式"""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def setup_routes(
    app: FastAPI,
    agent,
    agent_card,
    agent_name: str,
    agent_type: str,
    port: int,
    capabilities: list,
    tools: list,
    session_manager,
    registry_endpoint: str,
    handle_user_message,
    handle_event,
    handle_async_event,
) -> None:
    """
    设置 FastAPI 路由

    Args:
        app: FastAPI 应用实例
        agent: Agent 实例
        agent_card: AgentCard 实例
        agent_name: Agent 名称
        agent_type: Agent 类型
        port: Agent 端口
        capabilities: Agent 能力列表
        tools: Agent 工具列表
        session_manager: SessionManager 实例
        registry_endpoint: 注册中心地址
        handle_user_message: 处理用户消息的异步方法
        handle_event: 处理 A2A 事件的异步方法
    """

    @app.on_event("startup")
    async def startup():
        """启动时自动注册到注册中心"""
        from .types import A2AEvent
        print(f"[A2A Server] {agent_name} 启动 (端口: {port})")
        print(f"[A2A Server] Capabilities: {[c['name'] for c in capabilities]}")
        tool_names = [getattr(t, "name", type(t).__name__) for t in tools]
        print(f"[A2A Server] Loaded tools: {tool_names}")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{registry_endpoint}/api/registry/register",
                    json=agent_card.model_dump()
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        print(f"[A2A Server] Agent registered: {agent_card.agent_id} - {data.get('message')}")
                    else:
                        print(f"[A2A Server] Failed to register agent: {agent_card.agent_id} - Status: {response.status}")
        except Exception as e:
            print(f"[A2A Server] Error registering agent: {agent_card.agent_id} - {e}")

    @app.get("/session/{session_id}/history")
    async def get_session_history(session_id: str):
        """获取指定 session 的历史消息"""
        messages = session_manager.get_session_history(session_id)
        status = session_manager.get_session_status(session_id)
        return {
            "session_id": session_id,
            "metadata": {
                "agent_id": agent_card.agent_id,
                "agent_name": agent_card.agent_name,
                "agent_type": agent_card.agent_type,
                "status": status
            },
            "messages": messages
        }

    @app.get("/session/list")
    async def list_sessions():
        """列出该 Agent 所有 session"""
        sessions = session_manager.list_sessions()
        return {"sessions": sessions}

    @app.post("/session/new")
    async def create_session():
        """创建新 session"""
        session_id = session_manager.create_session()
        return {"session_id": session_id, "status": "created"}

    @app.delete("/session/{session_id}/delete")
    async def delete_session(session_id: str):
        """删除指定 session"""
        try:
            session_manager.delete_session(session_id)
            return {"status": "deleted", "session_id": session_id}
        except Exception as e:
            raise HTTPException(status_code=404, detail=str(e))

    @app.put("/session/{session_id}/rename")
    async def rename_session(session_id: str, request: Request):
        """重命名指定 session"""
        data = await request.json()
        new_name = data.get("session_name")
        if not new_name:
            raise HTTPException(status_code=400, detail="session_name is required")
        try:
            session_manager.rename_session(session_id, new_name)
            return {"status": "renamed", "session_id": session_id, "session_name": new_name}
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))

    @app.post("/session/{session_id}/activate")
    async def activate_session(session_id: str):
        """激活指定 session，暂停其他所有 session"""
        try:
            session_manager.activate_session(session_id)
            return {"status": "ok", "active_session": session_id}
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))

    @app.post("/chat/stream")
    async def chat_stream(request: Request):
        """流式聊天接口"""
        import logging
        logger = logging.getLogger(__name__)
        logger.info("[chat_stream] Received chat/stream request")

        data = await request.json()
        task = data.get("task", "")
        session_id = data.get("session_id", os.getenv("AGENT_SESSION_ID", "default"))
        logger.info(f"[chat_stream] task={task[:50]}..., session_id={session_id}")

        async def event_generator():
            try:
                async for event in handle_user_message(task, session_id):
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            except Exception as e:
                logger.error(f"[chat_stream] Error in event_generator: {e}")
                yield f"data: {json.dumps({'type': 'error', 'error': str(e)}, ensure_ascii=False)}\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream"
        )

    @app.get("/.well-known/agent-card.json")
    async def get_agent_card():
        """返回当前 Agent 的 AgentCard"""
        return JSONResponse(content=agent_card.model_dump())

    @app.post("/a2a/event")
    async def handle_a2a_event(request: Request):
        """
        核心端点：处理收到的 A2A 事件（同步模式，等待响应）
        """
        from .types import A2AEvent, EventType

        try:
            data = await request.json()
            event = A2AEvent(**data)
            print(f"[A2A Server] Received: {event.event_id} type={event.event_type} from={event.source}")

            async def event_generator():
                if event.event_type == EventType.USER_MESSAGE:
                    task = event.content.get("task", "")
                    session_id = event.content.get("session_id", "default")
                    async for evt in handle_user_message(task, session_id):
                        yield f"data: {json.dumps(evt, ensure_ascii=False)}\n\n"
                else:
                    async for evt in handle_event(event):
                        yield f"data: {json.dumps(evt, ensure_ascii=False)}\n\n"

            return StreamingResponse(
                event_generator(),
                media_type="text/event-stream"
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/a2a/async_event")
    async def handle_a2a_async_event(request: Request):
        """
        异步 A2A 事件端点（不等待响应，立即返回）

        接收异步消息，记录到 session，然后触发后台处理
        """
        from .types import A2AEvent

        try:
            data = await request.json()
            event = A2AEvent(**data)
            print(f"[A2A Server] Received async event: {event.event_id} from={event.source}")

            result = await handle_async_event(event)
            return JSONResponse(content=result)

        except Exception as e:
            return JSONResponse(content={"success": False, "message": str(e)}, status_code=500)

    @app.get("/health")
    async def health_check():
        """健康检查"""
        return {
            "status": "healthy",
            "agent_id": agent_card.agent_id,
            "agent_name": agent_card.agent_name
        }