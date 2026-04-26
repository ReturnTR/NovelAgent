import subprocess
import asyncio
from typing import Dict, Optional
from dataclasses import dataclass
from pathlib import Path
import uuid

@dataclass
class AgentProcess:
    agent_id: str
    agent_type: str
    port: int
    process: subprocess.Popen
    status: str

class ProcessManager:
    def __init__(self):
        self.processes: Dict[str, AgentProcess] = {}
        self.base_port = 8001
        self.port_counter = 0
    
    def get_next_port(self) -> int:
        self.port_counter += 1
        return self.base_port + self.port_counter
    
    async def start_agent(self, agent_type: str, agent_dir: Optional[str] = None) -> AgentProcess:
        """启动一个新的Agent进程"""
        agent_id = f"{agent_type}-{str(uuid.uuid4())[:8]}"
        port = self.get_next_port()
        
        if not agent_dir:
            project_root = Path(__file__).parent.parent.parent.parent
            agent_dir = str(project_root / "agent" / "agent_instances" / f"{agent_type}_agent")
        
        main_file = Path(agent_dir) / "main.py"
        
        if not main_file.exists():
            raise FileNotFoundError(f"Agent main file not found: {main_file}")
        
        env = {
            "AGENT_ID": agent_id,
            "AGENT_PORT": str(port),
            "PYTHONPATH": str(Path(__file__).parent.parent.parent.parent)
        }
        
        import os
        env.update(os.environ)
        
        process = subprocess.Popen(
            ["python", str(main_file)],
            cwd=agent_dir,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        agent_process = AgentProcess(
            agent_id=agent_id,
            agent_type=agent_type,
            port=port,
            process=process,
            status="running"
        )
        
        self.processes[agent_id] = agent_process
        
        await asyncio.sleep(2)
        
        return agent_process
    
    async def stop_agent(self, agent_id: str):
        """停止Agent进程"""
        if agent_id in self.processes:
            agent = self.processes[agent_id]
            agent.process.terminate()
            
            try:
                agent.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                agent.process.kill()
            
            agent.status = "stopped"
            del self.processes[agent_id]
    
    def get_agent_status(self, agent_id: str) -> Optional[str]:
        """获取Agent状态"""
        if agent_id in self.processes:
            return self.processes[agent_id].status
        return None
    
    def list_running_agents(self) -> Dict[str, AgentProcess]:
        """列出所有运行中的Agent"""
        return {
            agent_id: agent
            for agent_id, agent in self.processes.items()
            if agent.status == "running"
        }
