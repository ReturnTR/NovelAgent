import os
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from cores.character_agent import CharacterAgent
from agent_commons.a2a.message_schema import A2AMessage
from agent_commons.a2a.identity import AgentIdentity
from datetime import datetime, timezone

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

agent_id = os.getenv("AGENT_ID", "character-001")
port = int(os.getenv("AGENT_PORT", 8002))
agent_dir = Path(__file__).parent

agent = CharacterAgent(str(agent_dir))

@app.on_event("startup")
async def startup():
    identity = AgentIdentity(
        agent_id=agent_id,
        agent_name="Character Agent",
        agent_type="character",
        endpoint=f"http://localhost:{port}",
        version="1.0.0",
        capabilities=agent.capabilities,
        created_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    )
    print(f"Character Agent 启动: {agent_id} (端口: {port})")
    print(f"Capabilities: {[c['name'] for c in agent.capabilities]}")

@app.post("/a2a/message")
async def handle_a2a_message(request: Request):
    data = await request.json()
    message = A2AMessage(**data)
    
    result = await agent.process_task(
        message.content.get("task", ""),
        message.content.get("context")
    )
    
    return {
        "status": "ok",
        "result": result
    }

@app.get("/health")
async def health():
    return {"status": "healthy", "agent_id": agent_id}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=port)
