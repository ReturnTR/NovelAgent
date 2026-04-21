"""
Character Agent 启动入口

负责：
1. 创建 CharacterAgent 实例
2. 挂载 A2A 服务端路由
3. 启动时自动注册到注册中心
"""

import os
import sys
from pathlib import Path

# 将项目根目录添加到 Python 路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from cores.character_agent import CharacterAgent

from agent.core.a2a import A2AEventHandler
from agent.core.a2a.types import A2AEvent, EventType

# 创建 FastAPI 应用
app = FastAPI()

# 添加 CORS 中间件，允许跨域请求
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有方法
    allow_headers=["*"],  # 允许所有头部
)

# 从环境变量读取配置，或使用默认值
agent_id = os.getenv("AGENT_ID", "character-001")
port = int(os.getenv("AGENT_PORT", 8002))
agent_dir = Path(__file__).parent

# 创建 CharacterAgent 实例
# 内部会：
# 1. 加载配置和工具
# 2. 初始化 A2A 客户端和服务端
# 3. 构建 LangGraph
agent = CharacterAgent(str(agent_dir), agent_id=agent_id, port=port)

# 创建 A2AEventHandler
handler = A2AEventHandler(
    agent=agent,
    session_dir=str(Path(__file__).parent / "sessions")
)

# 将 A2A 服务端路由挂载到 /a2a 路径
# 这样 A2A 事件端点（如 /a2a/event）就可以使用了
a2a_app = agent.get_a2a_app()
app.mount("/a2a", a2a_app)


@a2a_app.post("/event")
async def handle_event(request: Request):
    """A2A 事件处理端点"""
    data = await request.json()
    event = A2AEvent(**data)

    if event.event_type == EventType.USER_MESSAGE:
        task = event.content.get("task", "")
        session_id = event.content.get("session_id", os.getenv("AGENT_SESSION_ID", "default"))
        return StreamingResponse(
            handler.handle_user_message(task, session_id),
            media_type="text/event-stream"
        )
    else:
        return StreamingResponse(
            handler.handle_event(event),
            media_type="text/event-stream"
        )


@app.on_event("startup")
async def startup():
    """Agent 启动时的初始化操作"""
    print(f"Character Agent 启动: {agent_id} (端口: {port})")
    print(f"Capabilities: {[c['name'] for c in agent.capabilities]}")
    tool_names = [getattr(t, "name", type(t).__name__) for t in agent.tools]
    print(f"Loaded tools: {tool_names}")

    # 将当前 Agent 注册到注册中心
    # 这样其他 Agent（如 Supervisor）就可以发现并与它通信
    await agent.register_with_registry()


@app.get("/session/{session_id}/history")
async def get_session_history(session_id: str):
    """获取指定 session 的历史消息"""
    messages = handler.get_session_history(session_id)
    return {"session_id": session_id, "messages": messages}


@app.post("/chat/stream")
async def chat_stream(request: Request):
    """流式聊天接口 - 通过 Handler 处理"""
    data = await request.json()
    task = data.get("task", "")
    session_id = data.get("session_id", os.getenv("AGENT_SESSION_ID", "default"))

    return StreamingResponse(
        handler.handle_user_message(task, session_id),
        media_type="text/event-stream"
    )


if __name__ == "__main__":
    import uvicorn
    # 启动 uvicorn 服务器
    uvicorn.run(app, host="0.0.0.0", port=port)
