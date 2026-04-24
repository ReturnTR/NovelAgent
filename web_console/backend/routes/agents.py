"""Agent management routes"""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

router = APIRouter(prefix="/api/agents", tags=["agents"])

class CreateAgentRequest(BaseModel):
    agent_type: str
    agent_name: str

class UpdateAgentNameRequest(BaseModel):
    agent_name: str

@router.get("")
async def list_agents(request: Request):
    agent_service = request.app.state.agent_service
    agents = await agent_service.list_agents()
    return {"agents": agents}

@router.post("")
async def create_agent(request: Request, body: CreateAgentRequest):
    agent_service = request.app.state.agent_service
    try:
        result = agent_service.create_agent(body.agent_type, body.agent_name)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/{session_id}/suspend")
async def suspend_agent(session_id: str, request: Request):
    agent_service = request.app.state.agent_service
    try:
        result = agent_service.suspend_agent(session_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/{session_id}/resume")
async def resume_agent(session_id: str, request: Request):
    agent_service = request.app.state.agent_service
    try:
        result = agent_service.resume_agent(session_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.patch("/{session_id}/name")
async def update_agent_name(session_id: str, request: Request, body: UpdateAgentNameRequest):
    agent_service = request.app.state.agent_service
    try:
        result = agent_service.update_agent_name(session_id, body.agent_name)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.delete("/{session_id}")
async def delete_agent(session_id: str, request: Request):
    agent_service = request.app.state.agent_service
    try:
        result = agent_service.delete_agent(session_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))