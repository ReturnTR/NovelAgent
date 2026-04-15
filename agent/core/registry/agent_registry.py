from typing import Dict, List, Optional
from ..a2a.identity import AgentIdentity

class AgentRegistry:
    def __init__(self):
        self.agents: Dict[str, AgentIdentity] = {}
    
    async def register_agent(self, agent_id: str, agent_info: dict):
        """注册Agent"""
        identity = AgentIdentity(
            agent_id=agent_id,
            agent_name=agent_info.get("name", f"Agent-{agent_id}"),
            agent_type=agent_info.get("type", "generic"),
            endpoint=f"http://localhost:{agent_info.get('port', 8001)}",
            version="1.0.0",
            capabilities=agent_info.get("capabilities", []),
            status=agent_info.get("status", "active"),
            created_at=agent_info.get("created_at", "2024-04-13T00:00:00Z")
        )
        self.agents[agent_id] = identity
    
    async def remove_agent(self, agent_id: str):
        """移除Agent"""
        if agent_id in self.agents:
            del self.agents[agent_id]
    
    def get_agents(self) -> List[AgentIdentity]:
        """获取所有Agent"""
        return list(self.agents.values())
    
    def get_agent(self, agent_id: str) -> Optional[AgentIdentity]:
        """获取特定Agent"""
        return self.agents.get(agent_id)
    
    def get_agents_by_type(self, agent_type: str) -> List[AgentIdentity]:
        """根据类型获取Agent"""
        return [
            agent for agent in self.agents.values()
            if agent.agent_type == agent_type
        ]
    
    def update_agent_status(self, agent_id: str, status: str):
        """更新Agent状态"""
        if agent_id in self.agents:
            self.agents[agent_id].status = status
