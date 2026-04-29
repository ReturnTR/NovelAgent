"""
Check Agent 启动入口

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

agent_dir = Path(__file__).parent
project_root = agent_dir.parent.parent

sys.path.insert(0, str(agent_dir))
sys.path.insert(0, str(project_root))

from core.a2a.event_server import A2AEventServer
from cores.check_agent import CheckAgent

agent_id = os.getenv("AGENT_ID", "check-001")
port = int(os.getenv("AGENT_PORT", 8005))

with open(agent_dir / "agent_config.json", 'r', encoding='utf-8') as f:
    config = json.load(f)

registry_endpoint = config.get("registry", {}).get("endpoint", "http://localhost:8000")
a2a_server = A2AEventServer(
    agent_id=agent_id,
    config=config,
    agent_dir=agent_dir,
    port=port,
    registry_endpoint=registry_endpoint,
    agent_class=CheckAgent
)

app = a2a_server.app


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=port)