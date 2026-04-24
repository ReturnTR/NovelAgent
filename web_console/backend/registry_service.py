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
        registry = get_registry()
        return await registry.search_agents(keywords, agent_type)

    async def register_agent(self, agent_card: AgentCard) -> Dict[str, Any]:
        """Register agent to registry"""
        registry = get_registry()
        await registry.register_agent(agent_card)
        return {"status": "ok", "agent_id": agent_card.agent_id}