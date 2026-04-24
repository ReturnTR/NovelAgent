"""Registry service - A2A Agent discovery and registration"""
import sys
import aiohttp
import logging
from typing import List, Dict, Any, Optional

from config import PROJECT_ROOT

sys.path.insert(0, str(PROJECT_ROOT))
from core.a2a import get_registry, AgentCard

logger = logging.getLogger(__name__)


class RegistryService:
    """Service for A2A Agent registry operations"""

    def __init__(self, session_service, logger: logging.Logger):
        self.session_service = session_service
        self.logger = logger

    async def list_agents(self) -> List[AgentCard]:
        """List all registered agents from registry"""
        registry = get_registry()
        return await registry.list_agents()

    async def get_agent(self, agent_id: str) -> Optional[AgentCard]:
        """Get specific agent from registry"""
        registry = get_registry()
        return await registry.get_agent(agent_id)

    async def search_agents(self, keywords: Optional[str] = None,
                           agent_type: Optional[str] = None) -> List[AgentCard]:
        """Search agents via registry with filtering"""
        # Get active sessions
        active_sessions = []
        for session in self.session_service.list_sessions():
            if session.get("status") == "active" and session.get("port"):
                active_sessions.append(session)

        # Fetch AgentCards from each active Agent
        agents = []
        for session in active_sessions:
            port = session.get("port")
            try:
                async with aiohttp.ClientSession() as http_session:
                    async with http_session.get(
                        f"http://localhost:{port}/a2a/.well-known/agent-card.json",
                        timeout=aiohttp.ClientTimeout(total=2)
                    ) as response:
                        if response.status == 200:
                            agent_card_data = await response.json()
                            agent_card = AgentCard(**agent_card_data)
                            agents.append(agent_card)
            except Exception as e:
                self.logger.debug(f"Failed to get agent card from port {port}: {e}")

        # Apply filters
        filtered_agents = []
        for agent in agents:
            if agent_type and agent.agent_type != agent_type:
                continue
            if keywords:
                keywords_lower = keywords.lower()
                match = False
                if keywords_lower in agent.agent_name.lower():
                    match = True
                elif keywords_lower in agent.description.lower():
                    match = True
                else:
                    for cap in agent.capabilities:
                        if keywords_lower in cap.name.lower() or keywords_lower in cap.description.lower():
                            match = True
                            break
                if not match:
                    continue
            filtered_agents.append(agent)

        return filtered_agents

    async def register_agent(self, agent_card: AgentCard) -> Dict[str, Any]:
        """Register agent to registry"""
        registry = get_registry()
        await registry.register_agent(agent_card)
        return {"status": "ok", "agent_id": agent_card.agent_id}