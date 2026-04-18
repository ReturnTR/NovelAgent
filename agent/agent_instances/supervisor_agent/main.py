"""
Supervisor Agent 启动入口

负责：
1. 创建 SupervisorAgent 实例
2. 挂载 A2A 服务端路由
3. 启动时自动注册到注册中心
4. 提供 /chat/stream 接口处理用户对话
"""

import os
import sys
import json
from pathlib import Path

# 将项目根目录添加到 Python 路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from cores.supervisor_agent import SupervisorAgent
from datetime import datetime, timezone

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
agent_id = os.getenv("AGENT_ID", "supervisor-001")
port = int(os.getenv("AGENT_PORT", 8001))
agent_dir = Path(__file__).parent

# 创建 SupervisorAgent 实例
# 内部会：
# 1. 加载配置和工具
# 2. 初始化 A2A 客户端和服务端
# 3. 构建 LangGraph
agent = SupervisorAgent(str(agent_dir), agent_id=agent_id, port=port)

# 将 A2A 服务端路由挂载到 /a2a 路径
# 这样 A2A 事件端点（如 /a2a/event）就可以使用了
a2a_app = agent.get_a2a_app()
app.mount("/a2a", a2a_app)


@app.on_event("startup")
async def startup():
    """Agent 启动时的初始化操作"""
    print(f"Supervisor Agent 启动: {agent_id} (端口: {port})")
    print(f"Capabilities: {[c['name'] for c in agent.capabilities]}")
    tool_names = [getattr(t, "name", type(t).__name__) for t in agent.tools]
    print(f"Loaded tools: {tool_names}")

    # 将当前 Agent 注册到注册中心
    # 这样其他 Agent 就可以发现并与它通信
    await agent.register_with_registry()


@app.post("/chat/stream")
async def chat_stream(request: Request):
    """
    流式聊天接口

    接收用户的任务请求，通过 Agent 处理并流式返回结果

    请求体：
    {
        "task": "任务描述",
        "context": {}  // 可选的上下文数据
    }

    返回：
    SSE (Server-Sent Events) 流，包含处理过程中的事件
    """
    data = await request.json()
    task = data.get("task", "")
    context = data.get("context")

    async def generate():
        """生成器函数，用于流式返回处理事件"""
        try:
            # 调用 Agent 的流式处理接口
            async for event in agent.process_task_stream(task, context):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            error_msg = f"{str(e)}\n\nTraceback:\n{tb}"
            yield f"data: {json.dumps({'type': 'error', 'error': error_msg}, ensure_ascii=False)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn
    # 启动 uvicorn 服务器
    uvicorn.run(app, host="0.0.0.0", port=port)
