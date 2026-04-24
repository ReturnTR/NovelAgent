"""Agent service - manages Agent lifecycle (create/suspend/resume/delete)"""
import asyncio
import aiohttp
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from config import AGENT_MAIN_FILES
from process_manager import AgentProcessManager
from session_service import SessionService

logger = logging.getLogger(__name__)


class AgentService:
    """Service for Agent lifecycle management"""

    def __init__(self, process_manager: AgentProcessManager, logger: logging.Logger):
        self.process_manager = process_manager
        self.session_service = process_manager.session_manager
        self.logger = logger

    async def list_agents(self) -> List[Dict[str, Any]]:
        """List all agents with status"""
        self.session_service.sync_sessions_status(self.process_manager._get_all_running_pids())
        sessions = self.session_service.list_sessions()

        agents = []
        for session in sessions:
            port = session.get("port")
            status = "inactive"

            if port:
                try:
                    async with aiohttp.ClientSession() as http_session:
                        async with http_session.get(
                            f"http://localhost:{port}/a2a/health",
                            timeout=aiohttp.ClientTimeout(total=2)
                        ) as response:
                            if response.status == 200:
                                status = "active"
                except Exception:
                    pass

            session_id = session.get("session_id") or session.get("id")
            agents.append({
                "agent_type": session.get("agent_type"),
                "agent_name": session.get("agent_name"),
                "agent_id": session.get("agent_id"),
                "port": port,
                "pid": session.get("pid"),
                "status": status,
                "session_id": session_id,
                "updated_at": session.get("updated_at"),
                "message_count": session.get("message_count", 0),
                "capabilities": []
            })

        return agents

    def create_agent(self, agent_type: str, agent_name: str) -> Dict[str, Any]:
        """Create new Agent instance"""
        self.logger.info(f"Creating agent: type={agent_type}, name={agent_name}")
        if agent_type not in AGENT_MAIN_FILES:
            raise ValueError(f"Unknown agent type: {agent_type}")

        session_id = self.session_service.create_session(agent_type, agent_name)
        port, pid = self.process_manager.start_agent_process(
            session_id, agent_type, agent_name, AGENT_MAIN_FILES[agent_type]
        )
        self.session_service.update_session_port_pid(session_id, port, pid)

        return {
            "status": "ok",
            "message": f"Agent {agent_name} created",
            "session_id": session_id,
            "agent_type": agent_type,
            "agent_name": agent_name,
            "port": port,
            "pid": pid
        }

    def suspend_agent(self, session_id: str) -> Dict[str, Any]:
        """Suspend Agent"""
        session = self.session_service.get_session_by_id(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        pid = session.get("pid")
        if pid:
            self.process_manager.stop_agent_process(pid)

        port = session.get("port")
        if port:
            self.process_manager.release_port(port)

        self.session_service.update_session_port_pid(session_id, None, None)
        self.session_service.update_session_status(session_id, "suspended")

        return {"status": "ok", "message": f"Agent {session_id} suspended"}

    def resume_agent(self, session_id: str) -> Dict[str, Any]:
        """Resume Agent"""
        session = self.session_service.get_session_by_id(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        pid = session.get("pid")
        if pid and self.process_manager.is_process_running(pid):
            return {"status": "ok", "message": f"Agent {session_id} is already running"}

        agent_type = session.get("agent_type")
        port, new_pid = self.process_manager.start_agent_process(
            session_id,
            agent_type,
            session.get("agent_name"),
            AGENT_MAIN_FILES.get(agent_type, "")
        )
        self.session_service.update_session_port_pid(session_id, port, new_pid)
        self.session_service.update_session_status(session_id, "active")

        return {
            "status": "ok",
            "message": f"Agent {session_id} resumed",
            "port": port,
            "pid": new_pid
        }

    def update_agent_name(self, session_id: str, new_name: str) -> Dict[str, Any]:
        """Update Agent name"""
        self.session_service.update_session_agent_name(session_id, new_name)
        return {"status": "ok", "message": f"Agent name updated to {new_name}"}

    def delete_agent(self, session_id: str) -> Dict[str, Any]:
        """Delete Agent"""
        session = self.session_service.get_session_by_id(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        pid = session.get("pid")
        if pid:
            self.process_manager.stop_agent_process(pid)

        port = session.get("port")
        if port:
            self.process_manager.release_port(port)

        self.session_service.delete_session(session_id)

        return {"status": "ok", "message": f"Agent {session_id} deleted"}

    async def chat_stream(self, session_id: str, message: str):
        """Stream chat to Agent"""
        session = self.session_service.get_session_by_id(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        port = session.get("port")
        if not port:
            raise ValueError("Agent is not running, please resume it first")

        self.session_service.append_message(session_id, "user", message)
        session_messages = self.session_service.get_session_messages(session_id)

        async def generate():
            try:
                async with aiohttp.ClientSession() as http_session:
                    async with http_session.post(
                        f"http://localhost:{port}/chat/stream",
                        json={
                            "task": message,
                            "context": session_messages
                        },
                        timeout=aiohttp.ClientTimeout(total=120)
                    ) as response:
                        if response.status == 200:
                            async for line in response.content:
                                line = line.decode('utf-8').strip()
                                if not line.startswith('data:'):
                                    continue
                                try:
                                    data = json.loads(line[5:].strip())
                                    event_type = data.get('type')

                                    if event_type in ('assistant', 'content'):
                                        content = data.get('content', '')
                                        self.session_service.append_message(session_id, "assistant", content)
                                        yield f"data: {json.dumps({'type': 'content', 'content': content}, ensure_ascii=False)}\n\n"

                                    elif event_type == 'tool_call':
                                        tool_calls = data.get('tool_calls', [])
                                        yield f"data: {json.dumps({'type': 'tool_call', 'tool_calls': tool_calls}, ensure_ascii=False)}\n\n"

                                    elif event_type == 'reasoning':
                                        reasoning_content = data.get('content', '')
                                        self.session_service.append_message(session_id, "assistant", "", reasoning_content=reasoning_content)
                                        yield f"data: {json.dumps({'type': 'reasoning', 'content': reasoning_content}, ensure_ascii=False)}\n\n"

                                    elif event_type == 'tool_result':
                                        tool_call_id = data.get('tool_call_id')
                                        content = data.get('content', '')
                                        self.session_service.append_message(session_id, "tool", content, tool_call_id=tool_call_id)
                                        yield f"data: {json.dumps({'type': 'tool_result', 'tool_call_id': tool_call_id, 'content': content}, ensure_ascii=False)}\n\n"

                                    elif event_type == 'done':
                                        yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"

                                    elif event_type == 'error':
                                        error = data.get('error')
                                        yield f"data: {json.dumps({'type': 'error', 'error': error}, ensure_ascii=False)}\n\n"

                                except json.JSONDecodeError:
                                    continue
                        else:
                            error_msg = f"Agent response error: {response.status}"
                            yield f"data: {json.dumps({'type': 'error', 'error': error_msg}, ensure_ascii=False)}\n\n"

            except aiohttp.ClientError as e:
                error_msg = f'Connection failed: {str(e)}'
                self.logger.error(error_msg)
                yield f"data: {json.dumps({'type': 'error', 'error': error_msg}, ensure_ascii=False)}\n\n"
            except Exception as e:
                error_msg = f'Processing failed: {str(e)}'
                self.logger.error(error_msg)
                yield f"data: {json.dumps({'type': 'error', 'error': error_msg}, ensure_ascii=False)}\n\n"

        from fastapi.responses import StreamingResponse
        return StreamingResponse(generate(), media_type="text/event-stream")