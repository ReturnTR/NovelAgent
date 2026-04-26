"""
Theme Agent 启动入口
"""

import os
import sys
import json
from pathlib import Path

# 从环境变量读取配置
agent_id = os.getenv("AGENT_ID", "theme-001")
port = int(os.getenv("AGENT_PORT", 8003))
agent_dir = Path(__file__).parent

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(agent_dir))

from core.a2a.event_server import A2AEventServer
from cores.supervisor_agent import SupervisorAgent

# step 1: 加载配置
with open(agent_dir / "agent_config.json", 'r', encoding='utf-8') as f:
    config = json.load(f)

# step 2: 创建 A2AEventServer（内部创建 Agent 实例）
registry_endpoint = config.get("registry", {}).get("endpoint", "http://localhost:8000")
a2a_server = A2AEventServer(
    agent_id=agent_id,
    config=config,
    agent_dir=agent_dir,
    port=port,
    registry_endpoint=registry_endpoint,
    agent_class=SupervisorAgent
)

# step 3: 启动 FastAPI
app = a2a_server.app


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=port)