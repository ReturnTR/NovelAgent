"""
测试用 Registry 服务器

基于 core.a2a.registry_server.AgentRegistryServer
提供 Agent 注册、发现、搜索功能

运行方式：
    python -m tests.integration.test_registry_server
"""

import asyncio
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.a2a.registry_server import AgentRegistryServer, get_registry
from core.a2a.types import AgentCard

app = FastAPI(title="Test Registry Server")
registry: AgentRegistryServer = get_registry()


class RegisterRequest(BaseModel):
    agent_id: str
    agent_name: str
    agent_type: str
    endpoint: str
    version: str = "1.0.0"
    description: str = ""
    capabilities: List[Any] = []
    status: str = "active"


@app.get("/api/registry/agents")
async def list_agents():
    """列出所有已注册的 Agent"""
    agents = await registry.list_agents()
    return {"count": len(agents), "agents": [agent.model_dump() for agent in agents]}


@app.get("/api/registry/agents/{agent_id}")
async def get_agent(agent_id: str):
    """获取特定 Agent 的信息"""
    agent = await registry.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent.model_dump()


@app.get("/api/registry/search")
async def search_agents(keywords: Optional[str] = None, agent_type: Optional[str] = None):
    """搜索 Agent"""
    agents = await registry.search_agents(keywords=keywords, agent_type=agent_type)
    return {"count": len(agents), "agents": [agent.model_dump() for agent in agents]}


@app.post("/api/registry/register")
async def register_agent(request: RegisterRequest):
    """注册新的 Agent"""
    agent_card = AgentCard(
        agent_id=request.agent_id,
        agent_name=request.agent_name,
        agent_type=request.agent_type,
        endpoint=request.endpoint,
        version=request.version,
        description=request.description,
        capabilities=request.capabilities,
        status=request.status
    )
    await registry.register_agent(agent_card)
    return {"status": "ok", "agent_id": agent_card.agent_id}


@app.get("/health")
async def health():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)