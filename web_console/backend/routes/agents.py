"""Agent management routes - lifecycle operations for agents"""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Dict, List, Any

router = APIRouter(prefix="/api/agents", tags=["agents"])


class CreateAgentRequest(BaseModel):
    agent_id: str


@router.get("")
async def list_agents(request: Request) -> Dict[str, List[Any]]:
    """List all configured agents with status"""
    agent_service = request.app.state.agent_service
    agents = await agent_service.list_agents()
    return {"agents": agents}


@router.post("")
async def create_agent(request: Request, body: CreateAgentRequest):
    """Create/Start an agent"""
    agent_service = request.app.state.agent_service
    try:
        result = agent_service.create_agent(body.agent_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{agent_id}/suspend")
async def suspend_agent(agent_id: str, request: Request):
    """Suspend/Stop an agent"""
    agent_service = request.app.state.agent_service
    try:
        result = agent_service.suspend_agent(agent_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{agent_id}/resume")
async def resume_agent(agent_id: str, request: Request):
    """Resume/Start an agent"""
    agent_service = request.app.state.agent_service
    try:
        result = agent_service.resume_agent(agent_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{agent_id}")
async def delete_agent(agent_id: str, request: Request):
    """Delete an agent"""
    agent_service = request.app.state.agent_service
    try:
        result = agent_service.delete_agent(agent_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))