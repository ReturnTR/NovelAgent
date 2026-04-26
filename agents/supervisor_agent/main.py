"""
Supervisor Agent 启动入口

组装模式：
1. 加载配置
2. 创建 A2AEventServer（构建 agent_card）
3. 创建 BaseAgent 核心并注入 A2AEventServer
4. 启动 FastAPI
"""

import os
import sys
import json
from pathlib import Path

# agent_dir 是 /path/to/NovelAgent3/agents/supervisor_agent
agent_dir = Path(__file__).parent
project_root = agent_dir.parent.parent

# 添加 agent_dir 到 path，这样才能 from cores.xxx import
sys.path.insert(0, str(agent_dir))
sys.path.insert(0, str(project_root))

from core.a2a.event_server import A2AEventServer
from cores.supervisor_agent import SupervisorAgent

# 从环境变量读取配置，动态加载
agent_id = os.getenv("AGENT_ID", "supervisor-001")
port = int(os.getenv("AGENT_PORT", 8001))

# step 1: 加载配置
with open(agent_dir / "agent_config.json", 'r', encoding='utf-8') as f:
    config = json.load(f)

# step 2: 创建 A2AEventServer（构建 agent_card）
registry_endpoint = config.get("registry", {}).get("endpoint", "http://localhost:8000")
a2a_server = A2AEventServer(
    agent_id=agent_id,
    config=config,
    agent_dir=agent_dir,
    port=port,
    registry_endpoint=registry_endpoint,
    agent_class=SupervisorAgent
)

# step 5: 启动 FastAPI
app = a2a_server.app


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=port)