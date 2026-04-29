"""Registry service - A2A Agent discovery and registration"""
import sys
import json
import logging
from typing import List, Dict, Any, Optional

from web_console.backend.config import PROJECT_ROOT, FIXED_AGENTS

sys.path.insert(0, str(PROJECT_ROOT))
from core.a2a import get_registry, AgentCard

logger = logging.getLogger(__name__)


class RegistryService:
    """Service for A2A Agent registry operations"""

    def __init__(self, logger: logging.Logger):
        self.logger = logger

    async def _auto_register(self):
        """如果注册中心为空，从配置文件自动注册活跃的 agent"""
        registry = get_registry()
        existing = await registry.list_agents()
        if existing:
            return

        import urllib.request
        for agent_config in FIXED_AGENTS:
            port = agent_config.get("port")
            if not port:
                continue
            try:
                card_url = f"http://127.0.0.1:{port}/.well-known/agent-card.json"
                req = urllib.request.Request(card_url)
                with urllib.request.urlopen(req, timeout=3) as resp:
                    card_data = json.loads(resp.read().decode())
                agent_card = AgentCard(**card_data)
                await registry.register_agent(agent_card)
                self.logger.info(f"Auto-registered agent: {agent_card.agent_id}")
            except Exception:
                pass

    async def list_agents(self) -> List[AgentCard]:
        """List all registered agents from registry"""
        await self._auto_register()
        registry = get_registry()
        return await registry.list_agents()

    async def get_agent(self, agent_id: str) -> Optional[AgentCard]:
        """Get specific agent from registry"""
        await self._auto_register()
        registry = get_registry()
        return await registry.get_agent(agent_id)

    async def search_agents(self, keywords: Optional[str] = None,
                           agent_type: Optional[str] = None) -> List[AgentCard]:
        """Search agents via registry with filtering"""
        await self._auto_register()
        registry = get_registry()
        return await registry.search_agents(keywords, agent_type)

    async def register_agent(self, agent_card: AgentCard) -> Dict[str, Any]:
        """Register agent to registry"""
        registry = get_registry()
        await registry.register_agent(agent_card)
        return {"status": "ok", "agent_id": agent_card.agent_id}