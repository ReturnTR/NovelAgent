"""Session management routes"""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

router = APIRouter(prefix="/api/sessions", tags=["sessions"])

class CreateAgentRequest(BaseModel):
    agent_type: str
    agent_name: str

class MessageModel(BaseModel):
    role: str
    content: Optional[str] = ""
    tool_calls: Optional[List[Dict]] = None
    tool_results: Optional[List[Dict]] = None

@router.get("")
async def list_sessions(request: Request, agent_type: str = None, status: str = None):
    session_service = request.app.state.session_service
    sessions = session_service.list_sessions(agent_type=agent_type, status=status)
    return {"sessions": sessions}

@router.post("")
async def create_session(request: Request, body: CreateAgentRequest):
    agent_service = request.app.state.agent_service
    try:
        result = agent_service.create_agent(body.agent_type, body.agent_name)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/{session_id}")
async def get_session(session_id: str, request: Request):
    session_service = request.app.state.session_service
    session = session_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    return session

@router.get("/{session_id}/messages")
async def get_session_messages(session_id: str, request: Request):
    session_service = request.app.state.session_service
    messages = session_service.get_session_messages(session_id)
    return {"messages": messages}

@router.post("/{session_id}/messages")
async def append_message(session_id: str, request: Request, body: MessageModel):
    session_service = request.app.state.session_service
    role = body.role
    content = body.content or ""
    tool_calls = body.tool_calls
    tool_results = body.tool_results

    if not role:
        raise HTTPException(status_code=400, detail="Missing role")
    if not content and not tool_calls and not tool_results:
        raise HTTPException(status_code=400, detail="Missing content, tool_calls, or tool_results")

    session_service.append_message(session_id, role, content, tool_calls, tool_results)
    return {"status": "ok", "received": {"tool_calls": tool_calls, "tool_results": tool_results}}

@router.delete("/{session_id}/messages/{message_index}")
async def delete_session_message(session_id: str, message_index: int, request: Request):
    session_service = request.app.state.session_service
    try:
        session_service.delete_message_by_index(session_id, message_index)
        return {"status": "ok", "message": "Message deleted successfully"}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")
    except IndexError:
        raise HTTPException(status_code=400, detail="Invalid message index")

@router.post("/{session_id}/agent-message")
async def append_agent_message(session_id: str, request: Request):
    session_service = request.app.state.session_service
    data = await request.json()
    role = data.get("role", "user")
    content = data.get("content", "")
    source_agent_id = data.get("source_agent_id", "")
    target_agent_id = data.get("target_agent_id", "")
    event_id = data.get("event_id")
    task_id = data.get("task_id")

    session_service.append_agent_message(
        session_id, role, content, source_agent_id, target_agent_id, event_id, task_id
    )
    return {"status": "ok", "message": "Agent message appended"}

@router.delete("/{session_id}")
async def delete_session(session_id: str, request: Request):
    agent_service = request.app.state.agent_service
    try:
        result = agent_service.delete_agent(session_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))