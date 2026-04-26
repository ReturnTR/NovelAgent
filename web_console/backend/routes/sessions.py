"""Session routes - proxies to pre-started agent APIs"""
from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


async def _find_agent_by_session(agent_service, session_id: str):
    """Find which agent owns a session"""
    agents = await agent_service.list_agents()
    for agent in agents:
        if agent["status"] == "active":
            sessions = await agent_service.get_agent_sessions(agent["agent_id"])
            for session in sessions:
                if session.get("session_id") == session_id:
                    return agent
    return None


@router.get("")
async def list_sessions(request: Request):
    """List sessions from all configured agents"""
    agent_service = request.app.state.agent_service
    all_sessions = []
    agents = await agent_service.list_agents()
    for agent in agents:
        if agent["status"] == "active":
            sessions = await agent_service.get_agent_sessions(agent["agent_id"])
            for session in sessions:
                session["agent_id"] = agent["agent_id"]
                session["agent_name"] = agent["agent_name"]
                session["agent_type"] = agent["agent_type"]
                all_sessions.append(session)
    return {"sessions": all_sessions}


@router.get("/{session_id}")
async def get_session(session_id: str, request: Request):
    """Get session info from agent"""
    agent_service = request.app.state.agent_service
    agent = await _find_agent_by_session(agent_service, session_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    sessions = await agent_service.get_agent_sessions(agent["agent_id"])
    for session in sessions:
        if session.get("session_id") == session_id:
            session["agent_name"] = agent["agent_name"]
            session["agent_type"] = agent["agent_type"]
            return session
    raise HTTPException(status_code=404, detail=f"Session {session_id} not found")


@router.get("/{session_id}/messages")
async def get_session_messages(session_id: str, request: Request):
    """Get session messages from agent API"""
    agent_service = request.app.state.agent_service
    agent = await _find_agent_by_session(agent_service, session_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    history = await agent_service.get_session_history(agent["agent_id"], session_id)
    if history:
        return {
            "session_id": session_id,
            "messages": history.get("messages", [])
        }
    return {"session_id": session_id, "messages": []}


@router.post("/new")
async def create_session(request: Request):
    """Create a new session - requires agent_id in body"""
    body = await request.json()
    agent_id = body.get("agent_id")
    if not agent_id:
        raise HTTPException(status_code=400, detail="agent_id is required")

    agent_service = request.app.state.agent_service
    try:
        result = await agent_service.create_agent_session(agent_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{session_id}")
async def delete_session(session_id: str, request: Request):
    """Delete a session"""
    agent_service = request.app.state.agent_service
    agent = await _find_agent_by_session(agent_service, session_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    try:
        await agent_service.delete_agent_session(agent["agent_id"], session_id)
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{session_id}/rename")
async def rename_session(session_id: str, request: Request):
    """Rename a session"""
    body = await request.json()
    new_name = body.get("session_name")
    if not new_name:
        raise HTTPException(status_code=400, detail="session_name is required")

    agent_service = request.app.state.agent_service
    agent = await _find_agent_by_session(agent_service, session_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    try:
        await agent_service.rename_agent_session(agent["agent_id"], session_id, new_name)
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{session_id}/activate")
async def activate_session(session_id: str, request: Request):
    """Activate a session"""
    agent_service = request.app.state.agent_service
    agent = await _find_agent_by_session(agent_service, session_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    try:
        result = await agent_service.activate_agent_session(agent["agent_id"], session_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
