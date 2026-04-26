"""Agent service - manages Agent lifecycle with process control"""
import aiohttp
import json
import logging
from typing import List, Dict, Any, Optional

from web_console.backend.config import FIXED_AGENTS, agent_state
from web_console.backend.process_manager import AgentProcessManager

logger = logging.getLogger(__name__)


class AgentService:
    """Service for Agent lifecycle management.

    Manages agent processes based on FIXED_AGENTS config.
    Proxies requests to Agent APIs.
    """

    def __init__(self, process_manager: AgentProcessManager, logger: logging.Logger):
        self.process_manager = process_manager
        self.logger = logger

    def _get_agent_config(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get agent config by agent_id"""
        for agent in FIXED_AGENTS:
            if agent["agent_id"] == agent_id:
                return agent
        return None

    async def _check_agent_health(self, port: int) -> str:
        """Check if agent is healthy via /health endpoint"""
        try:
            async with aiohttp.ClientSession() as http_session:
                async with http_session.get(
                    f"http://localhost:{port}/health",
                    timeout=aiohttp.ClientTimeout(total=2)
                ) as response:
                    if response.status == 200:
                        return "active"
                    return "inactive"
        except Exception:
            return "inactive"

    async def _get_agent_card(self, port: int) -> Optional[Dict[str, Any]]:
        """Get agent card from agent"""
        try:
            async with aiohttp.ClientSession() as http_session:
                async with http_session.get(
                    f"http://localhost:{port}/.well-known/agent-card.json",
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    if response.status == 200:
                        return await response.json()
                    return None
        except Exception:
            return None

    async def list_agents(self) -> List[Dict[str, Any]]:
        """List all configured agents with status and capabilities"""
        agents = []

        for agent_config in FIXED_AGENTS:
            agent_id = agent_config["agent_id"]
            state = agent_state.get_by_id(agent_id)

            pid = state.get("pid") if state else None
            status = state.get("status", "inactive") if state else "inactive"
            port = state.get("port", agent_config.get("port")) if state else agent_config.get("port")

            # Verify actual health status
            if port and status == "active":
                actual_status = await self._check_agent_health(port)
                if actual_status != "active":
                    status = "inactive"
                    if pid:
                        agent_state.set_inactive(agent_id)
                        pid = None

            capabilities = []
            if port and status == "active":
                card = await self._get_agent_card(port)
                if card and "capabilities" in card:
                    capabilities = card["capabilities"]

            # Get actual session_id from agent
            actual_session_id = f"wc-{agent_id}"
            if port and status == "active":
                sessions = await self.get_agent_sessions(agent_id)
                if sessions:
                    # Use most recent active session or first available
                    active_sessions = [s for s in sessions if s.get("status") == "active"]
                    if active_sessions:
                        actual_session_id = active_sessions[0].get("session_id")
                    else:
                        actual_session_id = sessions[0].get("session_id")

            agents.append({
                "agent_type": agent_config["agent_type"],
                "agent_name": agent_config["agent_name"],
                "agent_id": agent_id,
                "port": port,
                "pid": pid,
                "status": status,
                "session_id": actual_session_id,
                "capabilities": capabilities
            })

        return agents

    async def get_agent_sessions(self, agent_id: str) -> List[Dict[str, Any]]:
        """Get all sessions for an agent via agent's /session/list API"""
        state = agent_state.get_by_id(agent_id)
        if not state or not state.get("port"):
            return []

        port = state["port"]
        try:
            async with aiohttp.ClientSession() as http_session:
                async with http_session.get(
                    f"http://localhost:{port}/session/list",
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("sessions", [])
                    return []
        except Exception as e:
            self.logger.error(f"Failed to get sessions from agent {agent_id}: {e}")
            return []

    async def get_session_history(self, agent_id: str, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session history from agent via /session/{session_id}/history API"""
        state = agent_state.get_by_id(agent_id)
        if not state or not state.get("port"):
            return None

        port = state["port"]
        try:
            async with aiohttp.ClientSession() as http_session:
                async with http_session.get(
                    f"http://localhost:{port}/session/{session_id}/history",
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    if response.status == 200:
                        return await response.json()
                    return None
        except Exception as e:
            self.logger.error(f"Failed to get session history: {e}")
            return None

    async def create_agent_session(self, agent_id: str) -> Dict[str, Any]:
        """Create a new session in the agent via /session/new API"""
        state = agent_state.get_by_id(agent_id)
        if not state or not state.get("port"):
            raise ValueError(f"Agent {agent_id} is not running")

        port = state["port"]
        async with aiohttp.ClientSession() as http_session:
            async with http_session.post(
                f"http://localhost:{port}/session/new",
                timeout=aiohttp.ClientTimeout(total=5)
            ) as response:
                if response.status == 200:
                    return await response.json()
                raise Exception(f"Failed to create session: {response.status}")

    async def delete_agent_session(self, agent_id: str, session_id: str) -> None:
        """Delete a session in the agent via /session/{session_id}/delete API"""
        state = agent_state.get_by_id(agent_id)
        if not state or not state.get("port"):
            raise ValueError(f"Agent {agent_id} is not running")

        port = state["port"]
        async with aiohttp.ClientSession() as http_session:
            async with http_session.delete(
                f"http://localhost:{port}/session/{session_id}/delete",
                timeout=aiohttp.ClientTimeout(total=5)
            ) as response:
                if response.status != 200:
                    raise Exception(f"Failed to delete session: {response.status}")

    async def rename_agent_session(self, agent_id: str, session_id: str, new_name: str) -> None:
        """Rename a session in the agent via /session/{session_id}/rename API"""
        state = agent_state.get_by_id(agent_id)
        if not state or not state.get("port"):
            raise ValueError(f"Agent {agent_id} is not running")

        port = state["port"]
        async with aiohttp.ClientSession() as http_session:
            async with http_session.put(
                f"http://localhost:{port}/session/{session_id}/rename",
                json={"session_name": new_name},
                timeout=aiohttp.ClientTimeout(total=5)
            ) as response:
                if response.status != 200:
                    raise Exception(f"Failed to rename session: {response.status}")

    async def activate_agent_session(self, agent_id: str, session_id: str) -> Dict[str, Any]:
        """Activate a session in the agent via /session/{session_id}/activate API"""
        state = agent_state.get_by_id(agent_id)
        if not state or not state.get("port"):
            raise ValueError(f"Agent {agent_id} is not running")

        port = state["port"]
        async with aiohttp.ClientSession() as http_session:
            async with http_session.post(
                f"http://localhost:{port}/session/{session_id}/activate",
                timeout=aiohttp.ClientTimeout(total=5)
            ) as response:
                if response.status == 200:
                    return await response.json()
                raise Exception(f"Failed to activate session: {response.status}")

    async def get_or_create_agent_session(self, agent_id: str) -> Optional[str]:
        """Get or create a session in the agent, return session_id"""
        state = agent_state.get_by_id(agent_id)
        if not state or not state.get("port"):
            return None

        port = state["port"]
        agent_session_id = state.get("agent_session_id")

        if agent_session_id:
            try:
                async with aiohttp.ClientSession() as http_session:
                    async with http_session.get(
                        f"http://localhost:{port}/session/{agent_session_id}/history",
                        timeout=aiohttp.ClientTimeout(total=5)
                    ) as response:
                        if response.status == 200:
                            return agent_session_id
            except Exception:
                pass

        new_session_id = f"wc-{agent_id}"
        return new_session_id

    # ============================================================================
    # Agent Lifecycle Operations
    # ============================================================================

    def create_agent(self, agent_id: str) -> Dict[str, Any]:
        """Create/start Agent instance"""
        agent_config = self._get_agent_config(agent_id)
        if not agent_config:
            raise ValueError(f"Unknown agent_id: {agent_id}")

        # Check if already running
        state = agent_state.get_by_id(agent_id)
        if state and state.get("pid"):
            if self.process_manager.is_process_running(state["pid"]):
                return {
                    "status": "ok",
                    "message": f"Agent {agent_id} is already running",
                    "session_id": f"wc-{agent_id}",
                    "agent_session_id": state.get("agent_session_id"),
                    "port": state["port"],
                    "pid": state["pid"]
                }

        port = agent_config["port"]
        pid = self.process_manager.start_agent_process(
            agent_id=agent_id,
            agent_type=agent_config["agent_type"],
            agent_name=agent_config["agent_name"],
            main_file=agent_config["main_file"],
            port=port
        )

        agent_state.set_active(agent_id, pid, port)

        return {
            "status": "ok",
            "message": f"Agent {agent_id} created",
            "session_id": f"wc-{agent_id}",
            "agent_id": agent_id,
            "port": port,
            "pid": pid
        }

    def suspend_agent(self, agent_id: str) -> Dict[str, Any]:
        """Suspend/Stop Agent"""
        state = agent_state.get_by_id(agent_id)
        if not state:
            raise ValueError(f"Agent {agent_id} not found")

        pid = state.get("pid")
        if pid:
            self.process_manager.stop_agent_process(pid)

        port = state.get("port")
        if port:
            self.process_manager.release_port(port)

        agent_state.set_inactive(agent_id)

        return {"status": "ok", "message": f"Agent {agent_id} suspended"}

    def resume_agent(self, agent_id: str) -> Dict[str, Any]:
        """Resume/Start Agent"""
        agent_config = self._get_agent_config(agent_id)
        if not agent_config:
            raise ValueError(f"Unknown agent_id: {agent_id}")

        state = agent_state.get_by_id(agent_id)
        if not state:
            return self.create_agent(agent_id)

        pid = state.get("pid")
        if pid and self.process_manager.is_process_running(pid):
            return {"status": "ok", "message": f"Agent {agent_id} is already running"}

        port = agent_config["port"]
        new_pid = self.process_manager.start_agent_process(
            agent_id=agent_id,
            agent_type=agent_config["agent_type"],
            agent_name=agent_config["agent_name"],
            main_file=agent_config["main_file"],
            port=port
        )

        agent_state.set_active(agent_id, new_pid, port)

        return {
            "status": "ok",
            "message": f"Agent {agent_id} resumed",
            "port": port,
            "pid": new_pid
        }

    def delete_agent(self, agent_id: str) -> Dict[str, Any]:
        """Delete Agent"""
        state = agent_state.get_by_id(agent_id)
        if not state:
            raise ValueError(f"Agent {agent_id} not found")

        pid = state.get("pid")
        if pid:
            self.process_manager.stop_agent_process(pid)

        port = state.get("port")
        if port:
            self.process_manager.release_port(port)

        agent_state.set_inactive(agent_id)

        return {"status": "ok", "message": f"Agent {agent_id} deleted"}

    async def chat_stream(self, agent_id: str, message: str):
        """Stream chat to Agent - proxies to agent's /chat/stream API

        The Agent manages its own session internally. We pass a session_id
        that the Agent will use/create.
        """
        state = agent_state.get_by_id(agent_id)
        if not state or not state.get("port"):
            raise ValueError(f"Agent {agent_id} is not running")

        port = state["port"]

        # Get actual session_id from agent's active session
        sessions = await self.get_agent_sessions(agent_id)
        agent_session_id = f"wc-{agent_id}"
        if sessions:
            active_sessions = [s for s in sessions if s.get("status") == "active"]
            if active_sessions:
                agent_session_id = active_sessions[0].get("session_id")
            elif sessions:
                agent_session_id = sessions[0].get("session_id")

        async def generate():
            try:
                async with aiohttp.ClientSession() as http_session:
                    async with http_session.post(
                        f"http://localhost:{port}/chat/stream",
                        json={
                            "task": message,
                            "session_id": agent_session_id
                        },
                        timeout=aiohttp.ClientTimeout(total=120)
                    ) as response:
                        if response.status == 200:
                            async for line in response.content:
                                yield line
                        else:
                            error_data = {"type": "error", "error": f"Agent response error: {response.status}"}
                            yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n".encode()

            except aiohttp.ClientError as e:
                error_data = {"type": "error", "error": f'Connection failed: {str(e)}'}
                yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n".encode()
            except Exception as e:
                error_data = {"type": "error", "error": f'Processing failed: {str(e)}'}
                yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n".encode()

        from fastapi.responses import StreamingResponse
        return StreamingResponse(generate(), media_type="text/event-stream")
