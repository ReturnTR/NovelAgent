"""Registry routes for A2A Agent discovery"""
from fastapi import APIRouter, HTTPException, Request
from typing import Optional

router = APIRouter(prefix="/api/registry", tags=["registry"])

@router.get("/agents")
async def registry_list_agents(request: Request):
    registry_service = request.app.state.registry_service
    agents = await registry_service.list_agents()
    return {"count": len(agents), "agents": [agent.model_dump() for agent in agents]}

@router.get("/agents/{agent_id}")
async def registry_get_agent(agent_id: str, request: Request):
    registry_service = request.app.state.registry_service
    agent = await registry_service.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent.model_dump()

@router.get("/search")
async def registry_search_agents(request: Request, keywords: Optional[str] = None, agent_type: Optional[str] = None):
    registry_service = request.app.state.registry_service
    agents = await registry_service.search_agents(keywords, agent_type)
    return {"count": len(agents), "agents": [agent.model_dump() for agent in agents]}

@router.post("/register")
async def registry_register_agent(request: Request):
    registry_service = request.app.state.registry_service
    data = await request.json()
    from core.a2a import AgentCard
    agent_card = AgentCard(**data)
    return await registry_service.register_agent(agent_card)