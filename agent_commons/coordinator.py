from .a2a.protocol import A2AProtocol
from .process.manager import ProcessManager
from .registry.agent_registry import AgentRegistry
from .factory.agent_factory import AgentFactory

class AgentCoordinator:
    def __init__(self):
        self.a2a = A2AProtocol()
        self.process_manager = ProcessManager()
        self.registry = AgentRegistry()
    
    async def start_agent(self, agent_type: str):
        """启动一个新的Agent进程"""
        process = await self.process_manager.start_agent(agent_type)
        
        await self.registry.register_agent(process.agent_id, {
            "type": agent_type,
            "port": process.port,
            "status": process.status
        })
        
        return process
    
    async def send_message(self, agent_id: str, message):
        """发送A2A消息"""
        return await self.a2a.send_message(agent_id, message)
    
    async def get_available_agents(self):
        """获取所有可用的Agent"""
        return self.registry.get_agents()
    
    async def stop_agent(self, agent_id: str):
        """停止Agent进程"""
        await self.process_manager.stop_agent(agent_id)
        await self.registry.remove_agent(agent_id)
    
    def list_agent_types(self) -> list:
        """列出所有可用的Agent类型"""
        return AgentFactory.list_available_agents()
    
    async def create_agent_instance(self, agent_type: str):
        """创建Agent实例（不启动进程）"""
        from pathlib import Path
        project_root = Path(__file__).parent.parent
        agent_dir = str(project_root / "agents" / f"{agent_type}_agent")
        return AgentFactory.create_agent(agent_type, agent_dir)
