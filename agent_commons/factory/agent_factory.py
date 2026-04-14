from typing import Dict, Type
from pathlib import Path
import importlib

class AgentFactory:
    """Agent工厂，用于创建和管理Agent实例"""
    
    _agent_registry: Dict[str, Type] = {}
    
    @classmethod
    def register_agent(cls, agent_type: str, agent_class: Type):
        """注册Agent类型"""
        cls._agent_registry[agent_type] = agent_class
    
    @classmethod
    def create_agent(cls, agent_type: str, agent_dir: str):
        """创建Agent实例"""
        if agent_type not in cls._agent_registry:
            agent_module = importlib.import_module(
                f"agents.{agent_type}_agent.cores.{agent_type}_agent"
            )
            agent_class_name = f"{agent_type.capitalize()}Agent"
            agent_class = getattr(agent_module, agent_class_name)
            cls.register_agent(agent_type, agent_class)
        
        agent_class = cls._agent_registry[agent_type]
        return agent_class(agent_dir)
    
    @classmethod
    def list_available_agents(cls) -> list:
        """列出所有可用的Agent"""
        from pathlib import Path
        agents_dir = Path(__file__).parent.parent.parent / "agents"
        available_agents = []
        
        if not agents_dir.exists():
            return available_agents
        
        for agent_dir in agents_dir.iterdir():
            if agent_dir.is_dir() and agent_dir.name.endswith("_agent"):
                config_file = agent_dir / "agent_config.json"
                if config_file.exists():
                    available_agents.append(agent_dir.name)
        
        return available_agents
    
    @classmethod
    def get_agent_config(cls, agent_type: str) -> dict:
        """获取Agent配置"""
        from pathlib import Path
        import json
        
        agents_dir = Path(__file__).parent.parent.parent / "agents"
        config_file = agents_dir / f"{agent_type}_agent" / "agent_config.json"
        
        if not config_file.exists():
            raise FileNotFoundError(f"Agent config not found: {config_file}")
        
        with open(config_file, 'r', encoding='utf-8') as f:
            return json.load(f)
