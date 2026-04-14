# 小说管理Agent系统架构改进方案

## 一、项目架构总览

### 1.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                          React 前端层                             │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  主Agent窗口  │  Agent1窗口  │  Agent2窗口  │  + 新建  │  │
│  │  (协调者)     │  (人物生成)  │  (大纲创建)  │  Agent    │  │
│  └─────────────────────────────────────────────────────────┘  │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │                    Agent会话管理器                        │  │
│  └─────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │ HTTP/A2A
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Agent协调服务层 (端口8000)                    │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │            Agent Commons (统一通信管理)                  │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │  │
│  │  │ A2A协议  │  │ 注册中心 │  │ 进程管理 │  │ 任务分发 │  │  │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘  │  │
│  └─────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │ 创建/管理进程
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Agent进程池                                │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │ 主Agent  │  │人物Agent │  │大纲Agent │  │内容Agent │  │
│  │(8001端口)│  │(8002端口)│  │(8003端口)│  │(8004端口)│  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  │
│           (每个Agent都是独立进程，独立文件夹)                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        MySQL 数据库                               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │ novels   │  │ persons  │  │ outlines │  │
│  └──────────┘  └──────────┘  └──────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Sessions 文件存储                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │supervisor│  │character │  │ outline  │  │cross_agent│ │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  │
│           (JSONL格式，记录所有Agent会话和交互)                 │
└─────────────────────────────────────────────────────────────────┘
```

## 二、目录结构设计

### 2.1 新的项目目录结构

```
Novel_Agent/
├── agents/                          # Agent进程目录（每个Agent一个文件夹）
│   ├── supervisor_agent/           # 主Agent（协调者）
│   │   ├── cores/                  # 核心代码
│   │   │   ├── __init__.py
│   │   │   ├── agent.py           # LangGraph实现
│   │   │   └── a2a_handler.py      # A2A协议处理
│   │   ├── skills/                 # 技能（渐进式披露）
│   │   │   ├── agent_management/
│   │   │   │   ├── skill.md
│   │   │   │   └── tools.py
│   │   │   └── task_coordination/
│   │   │       ├── skill.md
│   │   │       └── tools.py
│   │   ├── tools/                  # 工具函数
│   │   │   ├── __init__.py
│   │   │   ├── process_manager.py
│   │   │   └── registry.py
│   │   ├── prompts/                # Prompt文件
│   │   │   ├── system_prompt.txt
│   │   │   └── coordination_prompt.txt
│   │   ├── memories/               # 内存文件
│   │   │   ├── agent_registry.json
│   │   │   └── task_history.json
│   │   ├── requirements.txt
│   │   └── main.py                 # Agent启动入口
│   │
│   ├── character_agent/            # 人物生成Agent
│   │   ├── cores/
│   │   │   ├── __init__.py
│   │   │   └── agent.py
│   │   ├── skills/
│   │   │   ├── create_character/
│   │   │   │   ├── skill.md
│   │   │   │   └── tools.py
│   │   │   └── update_character/
│   │   │       ├── skill.md
│   │   │       └── tools.py
│   │   ├── tools/
│   │   ├── prompts/
│   │   ├── memories/
│   │   ├── requirements.txt
│   │   └── main.py
│   │
│   ├── outline_agent/              # 大纲生成Agent
│   ├── content_agent/              # 内容生成Agent
│   └── theme_agent/                # 主题生成Agent
│
├── agent_commons/                  # Agent公共组件
│   ├── __init__.py
│   ├── a2a/                        # A2A协议相关
│   │   ├── __init__.py
│   │   ├── message_schema.py       # 消息格式定义
│   │   ├── identity.py             # Agent身份名片
│   │   └── protocol.py             # 协议实现
│   ├── process/                    # 进程管理
│   │   ├── __init__.py
│   │   └── manager.py              # 进程管理器
│   ├── registry/                   # 注册中心
│   │   ├── __init__.py
│   │   └── agent_registry.py       # Agent注册管理
│   ├── coordinator/                # 协调器
│   │   ├── __init__.py
│   │   ├── main.py                 # FastAPI主入口
│   │   └── requirements.txt
│   └── coordinator.py              # 协调器主类
│
├── frontend/                        # React前端
│   ├── src/
│   │   ├── components/
│   │   │   ├── AgentWindow/       # Agent窗口组件
│   │   │   ├── AgentTabbar/       # Agent标签栏
│   │   │   └── Chat/               # 聊天界面
│   │   ├── services/
│   │   │   ├── a2aService.ts       # A2A协议客户端
│   │   │   └── agentService.ts
│   │   ├── store/                  # 状态管理
│   │   ├── types/                  # TypeScript类型
│   │   └── App.tsx
│   ├── package.json
│   └── tsconfig.json
│
├── db/                             # 数据库相关
│   ├── models.py
│   └── migrations/
│
├── sessions/                       # 会话文件存储（总目录）
│   ├── supervisor/                 # 主Agent会话
│   │   ├── sessions.json           # 会话元数据
│   │   ├── 53a58b60-b67b-4611-904b-0285b67f815f.jsonl  # 会话记录
│   │   └── ...
│   ├── character/                  # 人物Agent会话
│   │   ├── sessions.json
│   │   └── ...
│   ├── outline/                    # 大纲Agent会话
│   │   ├── sessions.json
│   │   └── ...
│   ├── content/                    # 内容Agent会话
│   │   ├── sessions.json
│   │   └── ...
│   ├── theme/                      # 主题Agent会话
│   │   ├── sessions.json
│   │   └── ...
│   └── cross_agent/                # 跨Agent协调会话
│       ├── sessions.json
│       └── ...
│
├── doc/
│   ├── readme.md
│   └── architecture_improvement.md
│
└── .env.example
```

## 三、Sessions 文件存储

### 3.1 存储结构说明

Sessions 采用文件存储方式，统一放在总目录下，按 Agent 类型分类管理：

```
sessions/
├── supervisor/                 # 主Agent会话
│   ├── sessions.json           # 会话元数据索引
│   ├── 53a58b60-b67b-4611-904b-0285b67f815f.jsonl  # 单个会话记录
│   └── ...
├── character/                  # 人物Agent会话
├── outline/                    # 大纲Agent会话
├── content/                    # 内容Agent会话
├── theme/                      # 主题Agent会话
└── cross_agent/                # 跨Agent协调会话
```

### 3.2 sessions.json 格式

每个 Agent 目录下的 `sessions.json` 存储所有会话的元数据：

```json
{
  "agent:supervisor:main": {
    "sessionId": "b1611b43-42de-4902-86cb-02d968842722",
    "updatedAt": 1774698427680,
    "systemSent": true,
    "status": "done",
    "startedAt": 1774698423993,
    "endedAt": 1774698427456,
    "runtimeMs": 3463,
    "modelProvider": "openai",
    "model": "gpt-4",
    "sessionFile": "/path/to/sessions/supervisor/b1611b43-42de-4902-86cb-02d968842722.jsonl"
  }
}
```

### 3.3 JSONL 会话文件格式

每个会话文件（.jsonl）记录完整的会话历史，每行一个 JSON 对象：

```json
{"type":"session","version":3,"id":"53a58b60-b67b-4611-904b-0285b67f815f","timestamp":"2026-03-08T17:57:34.398Z","cwd":"/Users/seco/AIProjects/Novel_Agent"}
{"type":"model_change","id":"d7285ec0","parentId":null,"timestamp":"2026-03-08T17:57:34.400Z","provider":"openai","modelId":"gpt-4"}
{"type":"message","id":"23cb1857","parentId":"d7285ec0","timestamp":"2026-03-08T17:57:34.407Z","message":{"role":"user","content":[{"type":"text","text":"创建一个人物"}]}}
{"type":"message","id":"570524ed","parentId":"23cb1857","timestamp":"2026-03-08T17:57:37.536Z","message":{"role":"assistant","content":[{"type":"text","text":"好的，我来帮你创建一个人物..."}]}}
{"type":"tool_call","id":"tool-001","parentId":"570524ed","timestamp":"2026-03-08T17:57:38.000Z","tool":"create_character","args":{...}}
{"type":"tool_result","id":"result-001","parentId":"tool-001","timestamp":"2026-03-08T17:57:39.000Z","result":{...}}
```

### 3.4 事件类型说明

| 事件类型 | 说明 | 关键字段 |
|---------|------|---------|
| `session` | 会话开始 | id, timestamp, cwd |
| `model_change` | 模型切换 | provider, modelId |
| `message` | 用户/助手消息 | role, content |
| `tool_call` | 工具调用 | tool, args |
| `tool_result` | 工具返回结果 | result |
| `a2a_message` | A2A协议消息 | sender, receiver, content |
| `agent_spawn` | 启动子Agent | agent_type, params |
| `agent_result` | 子Agent返回 | agent_id, result |
| `error` | 错误记录 | error_type, message |

### 3.5 Sessions 管理类

```python
# agent_commons/sessions/manager.py
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import uuid

class SessionManager:
    def __init__(self, base_dir: str = "sessions"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(exist_ok=True)
    
    def create_session(self, agent_type: str) -> str:
        """创建新会话"""
        session_id = str(uuid.uuid4())
        session_dir = self.base_dir / agent_type
        session_dir.mkdir(exist_ok=True)
        
        session_file = session_dir / f"{session_id}.jsonl"
        sessions_json = session_dir / "sessions.json"
        
        # 写入会话开始事件
        start_event = {
            "type": "session",
            "version": 3,
            "id": session_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "cwd": str(Path.cwd())
        }
        
        with open(session_file, 'w') as f:
            f.write(json.dumps(start_event) + '\n')
        
        # 更新 sessions.json
        self._update_sessions_json(sessions_json, session_id, session_file)
        
        return session_id
    
    def append_event(self, agent_type: str, session_id: str, event: dict):
        """追加事件到会话文件"""
        session_file = self.base_dir / agent_type / f"{session_id}.jsonl"
        
        with open(session_file, 'a') as f:
            f.write(json.dumps(event, ensure_ascii=False) + '\n')
    
    def get_session_history(self, agent_type: str, session_id: str) -> List[dict]:
        """获取会话历史"""
        session_file = self.base_dir / agent_type / f"{session_id}.jsonl"
        
        events = []
        with open(session_file, 'r') as f:
            for line in f:
                events.append(json.loads(line))
        
        return events
    
    def _update_sessions_json(self, sessions_json: Path, session_id: str, session_file: Path):
        """更新 sessions.json"""
        if sessions_json.exists():
            with open(sessions_json, 'r') as f:
                sessions = json.load(f)
        else:
            sessions = {}
        
        sessions[f"session:{session_id}"] = {
            "sessionId": session_id,
            "updatedAt": int(datetime.utcnow().timestamp() * 1000),
            "sessionFile": str(session_file),
            "status": "active"
        }
        
        with open(sessions_json, 'w') as f:
            json.dump(sessions, f, indent=2)
```

### 3.6 为什么选择总目录管理

**优势**：

1. **统一管理**：所有 Agent 的会话集中在一个地方，便于查看和管理
2. **跨 Agent 追踪**：主 Agent 协调多个子 Agent 时，可以在 `cross_agent/` 目录下记录完整的协调流程
3. **便于搜索**：可以在整个 sessions 目录下搜索特定内容
4. **数据分析**：便于统计所有 Agent 的使用情况和性能指标
5. **备份简单**：只需备份一个目录即可保存所有会话历史
6. **避免冗余**：不需要在每个 Agent 目录下重复存储会话管理代码

**对比每个 Agent 独立管理的优势**：

| 方面 | 总目录管理 | 每个 Agent 独立管理 |
|------|-----------|-------------------|
| 跨 Agent 协调 | ✅ 容易追踪 | ❌ 分散难以追踪 |
| 会话搜索 | ✅ 统一搜索 | ❌ 需要搜索多个目录 |
| 数据分析 | ✅ 统一分析 | ❌ 需要聚合多个来源 |
| 备份恢复 | ✅ 简单 | ❌ 复杂 |
| 代码复用 | ✅ 统一管理类 | ❌ 每个 Agent 重复 |

## 四、A2A协议实现

### 4.1 Agent身份名片（Identity）

每个Agent启动时需要注册自己的身份信息：

```python
# agent_commons/a2a/identity.py
from pydantic import BaseModel, Field
from typing import List, Dict, Optional

class AgentCapability(BaseModel):
    name: str
    description: str
    parameters: Dict[str, str]

class AgentIdentity(BaseModel):
    agent_id: str
    agent_name: str
    agent_type: str  # supervisor, character, outline, content, theme
    endpoint: str  # http://localhost:8002
    version: str
    capabilities: List[AgentCapability]
    status: str = "active"  # active, idle, busy, error
    created_at: str
```

### 4.2 消息格式定义

```python
# agent_commons/a2a/message_schema.py
from pydantic import BaseModel, Field
from typing import Any, Optional, Dict
from enum import Enum

class MessageType(str, Enum):
    TASK_REQUEST = "task_request"
    TASK_RESPONSE = "task_response"
    TASK_PROGRESS = "task_progress"
    AGENT_DISCOVERY = "agent_discovery"
    HEARTBEAT = "heartbeat"
    ERROR = "error"

class A2AMessage(BaseModel):
    message_id: str
    message_type: MessageType
    sender: str  # agent_id
    receiver: Optional[str] = None  # agent_id, None 表示广播
    task_id: Optional[str] = None
    timestamp: str
    content: Dict[str, Any]
    
    class Config:
        schema_extra = {
            "example": {
                "message_id": "msg-001",
                "message_type": "task_request",
                "sender": "supervisor-001",
                "receiver": "character-001",
                "task_id": "task-001",
                "timestamp": "2024-04-13T10:00:00Z",
                "content": {
                    "capability": "create_character",
                    "params": {
                        "novel_id": 1,
                        "requirements": "创建一个勇敢的男主角"
                    }
                }
            }
        }
```

### 4.3 A2A协议处理类

```python
# agent_commons/a2a/protocol.py
import asyncio
import json
from datetime import datetime
from typing import Dict, Optional
import aiohttp
from agent_commons.a2a.identity import AgentIdentity
from agent_commons.a2a.message_schema import A2AMessage, MessageType

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
                        json=message.dict()
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
```

## 五、Agent进程管理

### 5.1 进程管理器

```python
# agent_commons/process/manager.py
import subprocess
import os
import signal
from pathlib import Path
from typing import Dict, Optional
from dataclasses import dataclass
import asyncio

@dataclass
class AgentProcess:
    agent_id: str
    agent_type: str
    process: subprocess.Popen
    port: int
    status: str  # starting, running, stopped, error
    log_file: Optional[str] = None

class ProcessManager:
    def __init__(self, base_port: int = 8001):
        self.processes: Dict[str, AgentProcess] = {}
        self.base_port = base_port
        self.next_port = base_port
        self.agents_dir = Path(__file__).parent.parent.parent / "agents"
    
    def get_next_port(self) -> int:
        port = self.next_port
        self.next_port += 1
        return port
    
    async def start_agent(self, agent_type: str) -> AgentProcess:
        """启动一个新的Agent进程"""
        agent_id = f"{agent_type}-{len(self.processes) + 1:03d}"
        port = self.get_next_port()
        
        agent_dir = self.agents_dir / f"{agent_type}_agent"
        if not agent_dir.exists():
            raise Exception(f"Agent目录不存在: {agent_dir}")
        
        main_py = agent_dir / "main.py"
        if not main_py.exists():
            raise Exception(f"Agent入口文件不存在: {main_py}")
        
        log_file = agent_dir / f"logs/{agent_id}.log"
        log_file.parent.mkdir(exist_ok=True)
        
        env = os.environ.copy()
        env["AGENT_ID"] = agent_id
        env["AGENT_PORT"] = str(port)
        
        process = subprocess.Popen(
            ["python", str(main_py)],
            cwd=str(agent_dir),
            env=env,
            stdout=open(log_file, "w"),
            stderr=subprocess.STDOUT
        )
        
        agent_process = AgentProcess(
            agent_id=agent_id,
            agent_type=agent_type,
            process=process,
            port=port,
            status="starting",
            log_file=str(log_file)
        )
        
        self.processes[agent_id] = agent_process
        
        await asyncio.sleep(2)
        
        if process.poll() is None:
            agent_process.status = "running"
        else:
            agent_process.status = "error"
        
        return agent_process
    
    def stop_agent(self, agent_id: str):
        """停止Agent进程"""
        if agent_id in self.processes:
            agent = self.processes[agent_id]
            try:
                agent.process.terminate()
                agent.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                agent.process.kill()
            agent.status = "stopped"
    
    def get_agent_status(self, agent_id: str) -> Optional[str]:
        """获取Agent状态"""
        if agent_id in self.processes:
            return self.processes[agent_id].status
        return None
```

## 六、子Agent扩展方案

### 6.1 设计理念

为了让子Agent的扩展变得简单，我们采用以下设计原则：

1. **统一执行流程**：所有子Agent都遵循相同的执行模式
2. **配置驱动**：通过配置文件定义Agent的特性
3. **基类抽象**：提取公共逻辑到基类
4. **插件式扩展**：新建Agent只需添加配置和特定工具

### 6.2 Agent 基类设计

```python
# agent_commons/base/agent_base.py
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from pathlib import Path
import json
from langgraph.graph import StateGraph, END
from agent_commons.a2a.protocol import A2AProtocol
from agent_commons.a2a.identity import AgentIdentity
from agent_commons.sessions.manager import SessionManager

class AgentState(TypedDict):
    messages: List[Dict[str, Any]]
    current_task: str
    context: Dict[str, Any]

class BaseAgent(ABC):
    """所有Agent的基类"""
    
    def __init__(self, agent_dir: str):
        self.agent_dir = Path(agent_dir)
        self.config = self._load_config()
        self.a2a = A2AProtocol()
        self.session_manager = SessionManager()
        self.graph = self._build_graph()
        
        # 从配置加载
        self.agent_type = self.config["agent_type"]
        self.agent_name = self.config["agent_name"]
        self.capabilities = self.config.get("capabilities", [])
        self.tools = self._load_tools()
        self.skills = self._load_skills()
    
    def _load_config(self) -> Dict[str, Any]:
        """加载Agent配置文件"""
        config_file = self.agent_dir / "agent_config.json"
        if not config_file.exists():
            raise FileNotFoundError(f"配置文件不存在: {config_file}")
        
        with open(config_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _load_tools(self) -> List[Any]:
        """加载工具函数"""
        tools = []
        tools_dir = self.agent_dir / "tools"
        if tools_dir.exists():
            for tool_file in tools_dir.glob("*.py"):
                if tool_file.name != "__init__.py":
                    module = __import__(
                        f"tools.{tool_file.stem}",
                        fromlist=["tools"]
                    )
                    if hasattr(module, "tools"):
                        tools.extend(module.tools)
        return tools
    
    def _load_skills(self) -> Dict[str, str]:
        """加载技能（渐进式披露的MD文件）"""
        skills = {}
        skills_dir = self.agent_dir / "skills"
        if skills_dir.exists():
            for skill_dir in skills_dir.iterdir():
                if skill_dir.is_dir():
                    skill_file = skill_dir / "skill.md"
                    if skill_file.exists():
                        with open(skill_file, 'r', encoding='utf-8') as f:
                            skills[skill_dir.name] = f.read()
        return skills
    
    def _build_graph(self) -> StateGraph:
        """构建工作流图"""
        graph = StateGraph(AgentState)
        
        # 添加标准节点
        graph.add_node("init", self._init_context)
        graph.add_node("load_skills", self._load_relevant_skills)
        graph.add_node("process", self._process_task)
        graph.add_node("execute", self._execute_tools)
        graph.add_node("respond", self._generate_response)
        
        # 定义标准流程
        graph.set_entry_point("init")
        graph.add_edge("init", "load_skills")
        graph.add_edge("load_skills", "process")
        graph.add_conditional_edge(
            "process",
            self._should_execute_tools,
            {
                True: "execute",
                False: "respond"
            }
        )
        graph.add_edge("execute", "respond")
        graph.add_edge("respond", END)
        
        return graph.compile()
    
    async def _init_context(self, state: AgentState) -> AgentState:
        """初始化上下文"""
        state["context"]["agent_type"] = self.agent_type
        state["context"]["capabilities"] = self.capabilities
        return state
    
    async def _load_relevant_skills(self, state: AgentState) -> AgentState:
        """加载相关技能（渐进式披露）"""
        task = state["current_task"]
        relevant_skills = {}
        
        for skill_name, skill_content in self.skills.items():
            if self._is_skill_relevant(skill_name, task):
                relevant_skills[skill_name] = skill_content
        
        state["context"]["loaded_skills"] = relevant_skills
        return state
    
    @abstractmethod
    async def _process_task(self, state: AgentState) -> AgentState:
        """处理任务（子类实现）"""
        pass
    
    async def _execute_tools(self, state: AgentState) -> AgentState:
        """执行工具调用"""
        if "tool_calls" in state["context"]:
            for tool_call in state["context"]["tool_calls"]:
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]
                
                # 查找并执行工具
                for tool in self.tools:
                    if tool.name == tool_name:
                        result = await tool.ainvoke(tool_args)
                        state["context"]["tool_results"].append({
                            "tool": tool_name,
                            "result": result
                        })
        
        return state
    
    async def _generate_response(self, state: AgentState) -> AgentState:
        """生成响应"""
        return state
    
    def _should_execute_tools(self, state: AgentState) -> bool:
        """判断是否需要执行工具"""
        return "tool_calls" in state["context"] and len(state["context"]["tool_calls"]) > 0
    
    @abstractmethod
    def _is_skill_relevant(self, skill_name: str, task: str) -> bool:
        """判断技能是否相关（子类实现）"""
        pass
    
    async def run(self, initial_state: AgentState) -> AgentState:
        """运行Agent"""
        return await self.graph.ainvoke(initial_state)
```

### 6.3 Agent 配置文件格式

每个Agent需要一个 `agent_config.json` 配置文件：

```json
{
  "agent_type": "character",
  "agent_name": "人物生成Agent",
  "version": "1.0.0",
  "description": "负责创建和管理小说人物",
  "capabilities": [
    {
      "name": "create_character",
      "description": "创建新人物",
      "parameters": {
        "novel_id": "小说ID",
        "character_data": "人物数据JSON"
      }
    },
    {
      "name": "update_character",
      "description": "更新人物信息",
      "parameters": {
        "character_id": "人物ID",
        "update_data": "更新数据JSON"
      }
    }
  ],
  "model": {
    "provider": "openai",
    "model_id": "gpt-4",
    "temperature": 0.7,
    "max_tokens": 4000
  },
  "skills": [
    {
      "name": "create_character",
      "description": "创建人物的技能指导",
      "trigger_keywords": ["创建", "新增", "生成", "人物"]
    },
    {
      "name": "update_character",
      "description": "更新人物的技能指导",
      "trigger_keywords": ["更新", "修改", "编辑", "人物"]
    }
  ],
  "tools": [
    "create_character_tool",
    "update_character_tool",
    "query_character_tool"
  ],
  "prompts": {
    "system_prompt": "prompts/system_prompt.txt",
    "task_prompt": "prompts/task_prompt.txt"
  }
}
```

### 6.4 具体Agent实现示例

#### 人物生成Agent

**目录结构**：
```
agents/character_agent/
├── agent_config.json          # 配置文件
├── main.py                    # 启动入口
├── cores/
│   └── character_agent.py     # 具体实现
├── skills/
│   ├── create_character/
│   │   ├── skill.md
│   │   └── tools.py
│   └── update_character/
│       ├── skill.md
│       └── tools.py
├── tools/
│   ├── __init__.py
│   ├── create_character_tool.py
│   ├── update_character_tool.py
│   └── query_character_tool.py
└── prompts/
    ├── system_prompt.txt
    └── task_prompt.txt
```

**实现代码**：
```python
# agents/character_agent/cores/character_agent.py
from agent_commons.base.agent_base import BaseAgent, AgentState
from typing import Dict, Any

class CharacterAgent(BaseAgent):
    """人物生成Agent"""
    
    async def _process_task(self, state: AgentState) -> AgentState:
        """处理人物相关任务"""
        task = state["current_task"]
        
        # 加载系统提示
        system_prompt = self._load_prompt("system_prompt")
        
        # 构建消息
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": task}
        ]
        
        # 调用LLM
        response = await self._call_llm(messages)
        
        # 检查是否需要工具调用
        if response.tool_calls:
            state["context"]["tool_calls"] = response.tool_calls
            state["context"]["tool_results"] = []
        
        # 添加响应到消息
        state["messages"].append({
            "role": "assistant",
            "content": response.content
        })
        
        return state
    
    def _is_skill_relevant(self, skill_name: str, task: str) -> bool:
        """判断技能是否相关"""
        skill_config = next(
            (s for s in self.config["skills"] if s["name"] == skill_name),
            None
        )
        
        if skill_config:
            keywords = skill_config.get("trigger_keywords", [])
            return any(keyword in task for keyword in keywords)
        
        return False
    
    def _load_prompt(self, prompt_name: str) -> str:
        """加载提示文件"""
        prompt_file = self.agent_dir / "prompts" / f"{prompt_name}.txt"
        if prompt_file.exists():
            with open(prompt_file, 'r', encoding='utf-8') as f:
                return f.read()
        return ""
```

**启动入口**：
```python
# agents/character_agent/main.py
import os
import sys
from pathlib import Path
from fastapi import FastAPI, Request
from cores.character_agent import CharacterAgent
from agent_commons.a2a.message_schema import A2AMessage

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

app = FastAPI()

# 获取Agent配置
agent_id = os.getenv("AGENT_ID", "character-001")
port = int(os.getenv("AGENT_PORT", 8002))
agent_dir = Path(__file__).parent

# 初始化Agent
agent = CharacterAgent(str(agent_dir))

@app.on_event("startup")
async def startup():
    print(f"Character Agent 启动: {agent_id} (端口: {port})")

@app.post("/a2a/message")
async def handle_a2a_message(request: Request):
    data = await request.json()
    message = A2AMessage(**data)
    
    # 处理消息
    initial_state = {
        "messages": [],
        "current_task": message.content.get("task", ""),
        "context": {}
    }
    
    result = await agent.run(initial_state)
    
    return {
        "status": "ok",
        "result": result["messages"][-1] if result["messages"] else None
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=port)
```

### 6.5 新建Agent的步骤

要创建一个新的Agent，只需以下步骤：

#### 步骤1：创建目录结构
```bash
mkdir -p agents/new_agent/{cores,skills,tools,prompts}
```

#### 步骤2：创建配置文件
创建 `agent_config.json`：
```json
{
  "agent_type": "new_agent",
  "agent_name": "新Agent",
  "version": "1.0.0",
  "description": "新Agent的描述",
  "capabilities": [...],
  "model": {...},
  "skills": [...],
  "tools": [...],
  "prompts": {...}
}
```

#### 步骤3：创建Agent类
创建 `cores/new_agent.py`：
```python
from agent_commons.base.agent_base import BaseAgent, AgentState

class NewAgent(BaseAgent):
    async def _process_task(self, state: AgentState) -> AgentState:
        # 实现具体逻辑
        return state
    
    def _is_skill_relevant(self, skill_name: str, task: str) -> bool:
        # 实现技能匹配逻辑
        return False
```

#### 步骤4：创建启动入口
创建 `main.py`（复制模板，修改Agent类名）

#### 步骤5：添加技能和工具
- 在 `skills/` 目录下添加技能MD文件
- 在 `tools/` 目录下添加工具函数

### 6.6 Agent工厂模式

为了进一步简化创建过程，可以提供Agent工厂：

```python
# agent_commons/factory/agent_factory.py
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
            # 动态加载Agent类
            agent_module = importlib.import_module(
                f"agents.{agent_type}_agent.cores.{agent_type}_agent"
            )
            agent_class = getattr(agent_module, f"{agent_type.capitalize()}Agent")
            cls.register_agent(agent_type, agent_class)
        
        agent_class = cls._agent_registry[agent_type]
        return agent_class(agent_dir)
    
    @classmethod
    def list_available_agents(cls) -> list:
        """列出所有可用的Agent"""
        agents_dir = Path(__file__).parent.parent.parent / "agents"
        available_agents = []
        
        for agent_dir in agents_dir.iterdir():
            if agent_dir.is_dir() and agent_dir.name.endswith("_agent"):
                config_file = agent_dir / "agent_config.json"
                if config_file.exists():
                    available_agents.append(agent_dir.name)
        
        return available_agents
```

### 6.7 配置驱动的优势

**优势总结**：

1. **快速扩展**：新建Agent只需配置文件和少量代码
2. **统一管理**：所有Agent配置集中管理
3. **易于维护**：修改配置即可调整Agent行为
4. **降低错误**：基类处理通用逻辑，减少重复代码
5. **灵活定制**：通过重写基类方法实现特殊需求
6. **渐进式披露**：Skills按需加载，减少上下文负担

**对比传统方式**：

| 方面 | 配置驱动 | 传统硬编码 |
|------|---------|-----------|
| 新建Agent时间 | 10分钟 | 1-2小时 |
| 代码重复 | 最少 | 大量 |
| 维护难度 | 低 | 高 |
| 灵活性 | 高 | 低 |
| 学习曲线 | 平缓 | 陡峭 |

## 七、Agent目录结构实现

### 7.1 主Agent示例

```python
# agents/supervisor_agent/cores/agent.py
from langgraph.graph import StateGraph, END
from typing import TypedDict, List
from agent_commons.a2a.protocol import A2AProtocol
from agent_commons.a2a.identity import AgentIdentity
from agent_commons.process.manager import ProcessManager

class AgentState(TypedDict):
    messages: List[str]
    current_task: str
    available_agents: List[AgentIdentity]

class SupervisorAgent:
    def __init__(self):
        self.a2a = A2AProtocol()
        self.process_manager = ProcessManager()
        self.graph = self.build_graph()
    
    def build_graph(self) -> StateGraph:
        graph = StateGraph(AgentState)
        
        graph.add_node("analyze_task", self.analyze_task)
        graph.add_node("select_agent", self.select_agent)
        graph.add_node("delegate_task", self.delegate_task)
        
        graph.set_entry_point("analyze_task")
        graph.add_edge("analyze_task", "select_agent")
        graph.add_edge("select_agent", "delegate_task")
        graph.add_edge("delegate_task", END)
        
        return graph.compile()
    
    async def analyze_task(self, state: AgentState):
        """分析任务需求"""
        return state
    
    async def select_agent(self, state: AgentState):
        """选择合适的Agent"""
        return state
    
    async def delegate_task(self, state: AgentState):
        """委派任务给子Agent"""
        return state
    
    async def run(self, initial_state: AgentState):
        return await self.graph.ainvoke(initial_state)
```

```python
# agents/supervisor_agent/main.py
from fastapi import FastAPI, Request
from cores.agent import SupervisorAgent
from agent_commons.a2a.message_schema import A2AMessage
from agent_commons.a2a.identity import AgentIdentity
import os

app = FastAPI()
agent = SupervisorAgent()
agent_id = os.getenv("AGENT_ID", "supervisor-001")
port = int(os.getenv("AGENT_PORT", 8001))

@app.on_event("startup")
async def startup():
    identity = AgentIdentity(
        agent_id=agent_id,
        agent_name="Supervisor Agent",
        agent_type="supervisor",
        endpoint=f"http://localhost:{port}",
        version="1.0.0",
        capabilities=[],
        created_at="2024-04-13T00:00:00Z"
    )
    print(f"Supervisor Agent 启动: {agent_id}")

@app.post("/a2a/message")
async def handle_a2a_message(request: Request):
    data = await request.json()
    message = A2AMessage(**data)
    print(f"收到消息: {message}")
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=port)
```

## 八、React前端实现

### 8.1 Agent标签栏组件

```tsx
// frontend/src/components/AgentTabbar/index.tsx
import React, { useState } from 'react';
import { AgentSession } from '../../types';

interface AgentTabbarProps {
  sessions: AgentSession[];
  activeSessionId: string;
  onSwitchSession: (id: string) => void;
  onCloseSession: (id: string) => void;
  onCreateAgent: () => void;
}

const AgentTabbar: React.FC<AgentTabbarProps> = ({
  sessions,
  activeSessionId,
  onSwitchSession,
  onCloseSession,
  onCreateAgent,
}) => {
  return (
    <div className="agent-tabbar">
      <div className="tabs">
        {sessions.map((session) => (
          <div
            key={session.id}
            className={`agent-tab ${session.id === activeSessionId ? 'active' : ''} ${session.status}`}
            onClick={() => onSwitchSession(session.id)}
          >
            <span className="agent-icon">{session.icon}</span>
            <span className="agent-name">{session.name}</span>
            {sessions.length > 1 && (
              <button
                className="close-btn"
                onClick={(e) => {
                  e.stopPropagation();
                  onCloseSession(session.id);
                }}
              >
                ×
              </button>
            )}
            <span className={`status-indicator ${session.status}`}></span>
          </div>
        ))}
      </div>
      <button className="create-agent-btn" onClick={onCreateAgent}>
        + 新建Agent
      </button>
    </div>
  );
};

export default AgentTabbar;
```

### 8.2 Agent窗口组件

```tsx
// frontend/src/components/AgentWindow/index.tsx
import React, { useState, useEffect, useRef } from 'react';
import { AgentSession, Message } from '../../types';
import { a2aService } from '../../services/a2aService';

interface AgentWindowProps {
  session: AgentSession;
}

const AgentWindow: React.FC<AgentWindowProps> = ({ session }) => {
  const [messages, setMessages] = useState<Message[]>(session.messages);
  const [input, setInput] = useState('');
  const chatEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim()) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: input,
      timestamp: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput('');

    await a2aService.sendMessage(session.id, input);
  };

  return (
    <div className="agent-window">
      <div className="chat-container">
        {messages.map((message) => (
          <div key={message.id} className={`message ${message.role}`}>
            <div className="bubble">{message.content}</div>
          </div>
        ))}
        <div ref={chatEndRef} />
      </div>
      <div className="input-area">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSend()}
          placeholder="输入消息..."
        />
        <button onClick={handleSend}>发送</button>
      </div>
    </div>
  );
};

export default AgentWindow;
```

## 九、实施步骤

### 第一阶段：基础框架搭建
1. 创建新的目录结构
2. 实现A2A协议基础类
3. 实现进程管理器
4. 创建Agent协调服务

### 第二阶段：Agent实现
1. 迁移现有agents到新目录结构
2. 实现主Agent（supervisor）
3. 实现人物生成Agent
4. 实现大纲生成Agent
5. 实现内容生成Agent

### 第三阶段：前端开发
1. 初始化React项目
2. 实现Agent标签栏
3. 实现Agent窗口组件
4. 实现A2A协议客户端
5. 实现状态管理

### 第四阶段：集成测试
1. Agent进程启动/停止测试
2. A2A协议通信测试
3. 端到端功能测试
4. 性能优化

## 十、Agent Commons 核心功能

### 10.1 协调器主类

```python
# agent_commons/coordinator.py
from .a2a.protocol import A2AProtocol
from .process.manager import ProcessManager
from .registry.agent_registry import AgentRegistry

class AgentCoordinator:
    def __init__(self):
        self.a2a = A2AProtocol()
        self.process_manager = ProcessManager()
        self.registry = AgentRegistry()
    
    async def start_agent(self, agent_type):
        """启动一个新的Agent进程"""
        process = await self.process_manager.start_agent(agent_type)
        
        # 注册Agent
        await self.registry.register_agent(process.agent_id, {
            "type": agent_type,
            "port": process.port,
            "status": process.status
        })
        
        return process
    
    async def send_message(self, agent_id, message):
        """发送A2A消息"""
        return await self.a2a.send_message(agent_id, message)
    
    async def get_available_agents(self):
        """获取所有可用的Agent"""
        return self.registry.get_agents()
    
    async def stop_agent(self, agent_id):
        """停止Agent进程"""
        await self.process_manager.stop_agent(agent_id)
        await self.registry.remove_agent(agent_id)
```

### 10.2 Agent注册中心

```python
# agent_commons/registry/agent_registry.py
from typing import Dict, List
from agent_commons.a2a.identity import AgentIdentity

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
    
    def get_agent(self, agent_id: str) -> AgentIdentity:
        """获取特定Agent"""
        return self.agents.get(agent_id)
```

## 十一、优势总结

1. **模块化设计**：每个Agent独立，便于单独开发和测试
2. **可扩展性**：轻松添加新的Agent类型
3. **进程隔离**：一个Agent崩溃不影响其他Agent
4. **标准化协议**：A2A协议便于与其他系统集成
5. **灵活的前端**：多窗口模式提供良好的用户体验
6. **渐进式披露**：Skills支持渐进式知识披露
7. **内存管理**：每个Agent独立的memories目录
8. **统一通信管理**：Agent Commons 集中管理A2A协议、进程和注册中心
9. **结构清晰**：避免功能冗余，提高代码可维护性
10. **易于扩展**：模块化设计便于添加新功能
11. **会话统一管理**：Sessions 文件存储便于跨 Agent 追踪和分析

这个架构设计既满足了当前需求，又为未来的扩展提供了良好的基础。
