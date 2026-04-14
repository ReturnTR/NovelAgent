import asyncio
import json
from datetime import datetime
from typing import Dict, Optional
import aiohttp
from .identity import AgentIdentity
from .message_schema import A2AMessage, MessageType

class A2AProtocol:
    def __init__(self):
        self.agents: Dict[str, AgentIdentity] = {}
        self.message_id_counter = 0
    
    def generate_message_id(self) -> str:
        self.message_id_counter += 1
        return f"msg-{self.message_id_counter:06d}"
    
    async def send_message(self, message: A2AMessage) -> Optional[A2AMessage]:
        """发送A2A消息"""
        if message.receiver and message.receiver in self.agents:
            target_agent = self.agents[message.receiver]
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"{target_agent.endpoint}/a2a/message",
                        json=message.model_dump()
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            return A2AMessage(**data)
            except Exception as e:
                print(f"发送消息失败: {e}")
        return None
    
    async def broadcast_discovery(self):
        """广播发现请求"""
        discovery_message = A2AMessage(
            message_id=self.generate_message_id(),
            message_type=MessageType.AGENT_DISCOVERY,
            sender="coordinator",
            timestamp=datetime.utcnow().isoformat() + "Z",
            content={}
        )
        
        for agent_id, agent in list(self.agents.items()):
            try:
                await self.send_message(discovery_message)
            except Exception:
                agent.status = "error"
    
    def register_agent(self, identity: AgentIdentity):
        """注册Agent"""
        self.agents[identity.agent_id] = identity
    
    def unregister_agent(self, agent_id: str):
        """注销Agent"""
        if agent_id in self.agents:
            del self.agents[agent_id]
    
    def get_agent(self, agent_id: str) -> Optional[AgentIdentity]:
        """获取Agent信息"""
        return self.agents.get(agent_id)
    
    def get_all_agents(self) -> Dict[str, AgentIdentity]:
        """获取所有Agent"""
        return self.agents
