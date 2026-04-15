import os
import sys
import json
from pathlib import Path

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from cores.supervisor_agent import SupervisorAgent
from agent.core.a2a.message_schema import A2AMessage
from agent.core.a2a.identity import AgentIdentity
from datetime import datetime, timezone

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

agent_id = os.getenv("AGENT_ID", "supervisor-001")
port = int(os.getenv("AGENT_PORT", 8001))
agent_dir = Path(__file__).parent

agent = SupervisorAgent(str(agent_dir))

@app.on_event("startup")
async def startup():
    identity = AgentIdentity(
        agent_id=agent_id,
        agent_name="Supervisor Agent",
        agent_type="supervisor",
        endpoint=f"http://localhost:{port}",
        version="1.0.0",
        capabilities=agent.capabilities,
        created_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    )
    print(f"Supervisor Agent 启动: {agent_id} (端口: {port})")
    print(f"Capabilities: {[c['name'] for c in agent.capabilities]}")
    tool_names = [getattr(t, "name", type(t).__name__) for t in agent.tools]
    print(f"Loaded tools: {tool_names}")

@app.post("/a2a/message")
async def handle_a2a_message(request: Request):
    """同步处理消息"""
    data = await request.json()
    print(data)
    message = A2AMessage(**data)
    
    result = await agent.process_task(
        message.content.get("task", ""),
        message.content.get("context")
    )
    
    return {
        "status": "ok",
        "result": result
    }

@app.post("/a2a/message/stream")
async def handle_a2a_message_stream(request: Request):
    """流式处理消息（SSE）"""
    data = await request.json()
    message = A2AMessage(**data)
    
    async def generate():
        try:
            async for event in agent.process_task_stream(
                message.content.get("task", ""),
                message.content.get("context")
            ):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            error_msg = f"{str(e)}\n\nTraceback:\n{tb}"
            yield f"data: {json.dumps({'type': 'error', 'error': error_msg}, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(generate(), media_type="text/event-stream")

@app.get("/health")
async def health():
    return {"status": "healthy", "agent_id": agent_id}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=port)
