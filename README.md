# Novel Agent - 多Agent协作的小说创作系统

## 项目简介

Novel Agent 是一个基于多Agent协作的小说创作系统，采用模块化设计，支持多种类型的Agent协同工作。

## 项目结构

```
Novel_Agent/
├── agent/                        # Agent模块
│   ├── core/                     # Agent核心模块
│   │   ├── a2a/                  # A2A协议实现
│   │   ├── base/                 # Agent基类
│   │   ├── factory/              # Agent工厂
│   │   ├── process/              # 进程管理
│   │   ├── registry/             # Agent注册
│   │   ├── sessions/             # 会话管理
│   │   └── tools/                # 基础工具
│   └── agent_instances/          # Agent实例
│       ├── supervisor_agent/     # 主控Agent
│       └── character_agent/     # 人物生成Agent
├── web_console/                  # Agent管理&交互模块
│   ├── backend/                  # 后端FastAPI服务
│   │   ├── main_api.py           # 统一API入口
│   │   └── sessions/             # 会话文件存储
│   └── frontend/                 # 前端界面
├── business/                     # 业务端模块（工具服务等）
├── .env                          # 环境变量
└── requirements.txt              # 依赖包
```

## 项目架构图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              用户层 (Browser)                                │
│                         ┌─────────────────────────┐                         │
│                         │      Frontend (8000)    │                         │
│                         │   ┌─────────────────┐   │                         │
│                         │   │   Web Console   │   │                         │
│                         │   │   - Agent 列表   │   │                         │
│                         │   │   - 聊天界面     │   │                         │
│                         │   │   - 会话历史     │   │                         │
│                         │   └────────┬────────┘   │                         │
│                         └────────────┼────────────┘                         │
└─────────────────────────────────────┼───────────────────────────────────────┘
                                      │
                                      │ HTTP/SSE
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Web Console Backend (8000)                         │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                         main_api.py                                   │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │    │
│  │  │  Agent 管理  │  │  会话管理      │  │  SSE 流式响应处理         │  │    │
│  │  │  - 启动/停止  │  │  - SessionMgr │  │  - chat/stream           │  │    │
│  │  │  - 状态监控   │  │  - 消息存储   │  │  - agent 通信           │  │    │
│  │  └──────────────┘  └──────┬───────┘  └──────────────────────────┘  │    │
│  └────────────────────────────┼──────────────────────────────────────────┘    │
│                               │                                                  │
│                    ┌──────────┴──────────┐                                     │
│                    │   Sessions 存储      │                                     │
│                    │  (JSONL 文件)       │                                     │
│                    └─────────────────────┘                                     │
└───────────────────────────────────────────────────────────────────────────────┘
                                      │
                    ┌─────────────────┴─────────────────┐
                    │         Agent 进程 (独立端口)       │
                    ▼                                  ▼
┌────────────────────────────────┐    ┌────────────────────────────────┐
│   Supervisor Agent (8001)       │    │   Character Agent (8002)       │
│  ┌────────────────────────┐    │    │  ┌────────────────────────┐    │
│  │   SupervisorAgent      │    │    │  │   CharacterAgent       │    │
│  │  ┌──────────────────┐  │    │    │  │  ┌──────────────────┐  │    │
│  │  │   BaseAgent      │  │    │    │  │  │   BaseAgent      │  │    │
│  │  │  - 任务编排       │  │    │    │  │  │  - 人物生成       │  │    │
│  │  │  - 工具调度       │  │    │    │  │  │  - 技能匹配       │  │    │
│  │  │  - LangGraph     │  │    │    │  │  │  - LangGraph     │  │    │
│  │  └──────────────────┘  │    │    │  │  └──────────────────┘  │    │
│  │  ┌──────────────────┐  │    │    │  │  ┌──────────────────┐  │    │
│  │  │   Tools          │  │    │    │  │  │   Tools          │  │    │
│  │  │  - MySQL Executor│  │    │    │  │  │  - ...           │  │    │
│  │  │  - Bash Executor │  │    │    │  │  │                  │  │    │
│  │  └──────────────────┘  │    │    │  │  └──────────────────┘  │    │
│  │  ┌──────────────────┐  │    │    │  │                        │    │
│  │  │   Skills         │  │    │    │  │                        │    │
│  │  │  - MySQL Skill   │  │    │    │  │                        │    │
│  │  │  - Skill Creator │  │    │    │  │                        │    │
│  │  └──────────────────┘  │    │    │  │                        │    │
│  └────────────────────────┘    │    │  └────────────────────────┘    │
└────────────────────────────────┘    └────────────────────────────────┘
                    ▲                                  ▲
                    │                                  │
                    └──────────────┬───────────────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    │     Business 模块            │
                    │  (工具服务 / 外部服务)        │
                    │  ┌─────────────────────┐    │
                    │  │  MySQL Server       │    │
                    │  │  File System        │    │
                    │  │  External APIs      │    │
                    │  └─────────────────────┘    │
                    └─────────────────────────────┘
```

### 架构说明

| 层级 | 组件 | 说明 |
|------|------|------|
| 用户层 | Frontend | 基于浏览器的前端界面，通过 HTTP/SSE 与后端通信 |
| 网关层 | main_api.py | 统一入口，负责 Agent 管理、会话管理、流式响应 |
| Agent层 | Agent 进程 | 每个 Agent 运行在独立进程中，通过 A2A 协议通信 |
| 业务层 | Business | 外部服务，如数据库、文件系统等，供 Agent 调用 |

### 请求流程

```
用户发送消息 → Frontend → main_api.py → Agent进程 → Tools → Business
                      ↑                           ↓
                      ← ← ← ← ← ← SSE 流式响应 ← ← ← ← ←
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

创建 `.env` 文件：

```env
OPENAI_API_KEY=your_api_key
OPENAI_API_BASE=https://api.openai.com/v1
OPENAI_MODEL=gpt-4
```

### 3. 启动服务

#### 启动统一API入口（端口8000）
```bash
cd web_console/backend
python main_api.py
```

#### 启动主控Agent（端口8001）
```bash
cd agent/agent_instances/supervisor_agent
python main.py
```

#### 启动人物生成Agent（端口8002）
```bash
cd agent/agent_instances/character_agent
python main.py
```

### 4. 访问前端

打开浏览器访问：`http://localhost:8000`

## 模块说明

### Agent模块 (agent/)

负责Agent的运行和生成逻辑。

| 目录 | 说明 |
|------|------|
| core/ | Agent核心模块，包含基类、工厂、协议等 |
| agent_instances/ | Agent实例，包含具体业务逻辑 |

### 管理&交互模块 (web_console/)

用户的后台，直接管理Agent生命周期，与Agent进行对话交互。

| 目录 | 说明 |
|------|------|
| backend/ | 后端FastAPI服务 |
| frontend/ | 前端界面 |
| backend/sessions/ | 会话文件存储 |

### 业务逻辑模块 (business/)

负责业务逻辑，例如工具服务（MySQL、文件系统等）。

## 核心特性

### 1. 配置驱动

所有Agent通过配置文件定义，无需硬编码。

### 2. 统一基类

BaseAgent 提供了：
- 配置加载
- 工具加载
- 技能加载（渐进式披露）
- 会话管理
- 事件日志

### 3. 会话文件存储

会话记录存储在 `web_console/backend/sessions/` 目录下：
- JSONL格式存储
- 支持事件追加
- 便于跨Agent追踪

### 4. Agent工厂

AgentFactory 提供了：
- 动态加载Agent
- Agent注册
- 列出可用Agent

### 5. 进程管理

ProcessManager 提供了：
- 启动Agent进程
- 停止Agent进程
- 状态监控

### 6. 多Agent窗口

前端支持：
- 多个Agent同时在线
- 实时切换Agent
- 独立的会话历史
- 流式输出

## 创建新的Agent

### 步骤1：创建目录结构

```bash
mkdir -p agent/agent_instances/new_agent/{cores,skills,tools,prompts,memories}
touch agent/agent_instances/new_agent/__init__.py
touch agent/agent_instances/new_agent/tools/__init__.py
```

### 步骤2：创建配置文件

创建 `agent/agent_instances/new_agent/agent_config.json`：

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

### 步骤3：创建Agent类

创建 `agent/agent_instances/new_agent/cores/new_agent.py`：

```python
from agent.core.base.agent_base import BaseAgent
from typing import Dict, Any, Optional

class NewAgent(BaseAgent):
    async def process_task(self, task: str, context: Optional[Dict] = None) -> Dict[str, Any]:
        # 实现具体逻辑
        return {"status": "ok", "result": "处理完成"}

    def is_skill_relevant(self, skill_name: str, task: str) -> bool:
        # 实现技能匹配逻辑
        return False
```

### 步骤4：创建启动入口

创建 `agent/agent_instances/new_agent/main.py`（复制 supervisor_agent/main.py，修改类名）

### 步骤5：更新 main_api.py

在 `web_console/backend/main_api.py` 中添加新Agent的配置：

```python
AGENT_MAIN_FILES = {
    "supervisor": "agent/agent_instances/supervisor_agent/main.py",
    "character": "agent/agent_instances/character_agent/main.py",
    "new_agent": "agent/agent_instances/new_agent/main.py",  # 添加新Agent
}
```

## API接口

### 统一API（端口8000）

| 接口 | 方法 | 说明 |
|------|------|------|
| `/` | GET | 前端页面 |
| `/api/agents` | GET | 列出所有Agent |
| `/api/agents/{session_id}/resume` | POST | 恢复Agent |
| `/chat/stream` | POST | 流式聊天接口 |
| `/health` | GET | 健康检查 |

### Agent API（各Agent端口）

| 接口 | 方法 | 说明 |
|------|------|------|
| `/a2a/message` | POST | A2A消息接口 |
| `/a2a/message/stream` | POST | A2A流式消息接口 |
| `/health` | GET | 健康检查 |

## 技术栈

- **后端**: FastAPI, Python 3.12
- **前端**: HTML, CSS, JavaScript
- **AI**: LangChain, OpenAI API
- **存储**: JSONL文件存储
- **协议**: A2A (Agent-to-Agent) 协议

## 会话文件格式

```jsonl
{"type": "message", "role": "user", "content": "...", "timestamp": "..."}
{"type": "message", "role": "assistant", "content": "...", "tool_calls": [...], "timestamp": "..."}
{"type": "message", "role": "tool", "content": "...", "tool_call_id": "...", "timestamp": "..."}
```

## 许可证

MIT License


## 改进
1. agent冻结功能，即上下文固定，这样能保持Agent的状态，固有现有Agent功能

一个agent在线实例，他和其他的agent相比，哪些有区别：
1. skill
2. tool
3. prompt
4. memory系统
5. 上下文内容
6. 执行工作流（这个可以统一成tool循环）



就看相同的agent类，不同的agent实例，之间的区别。
1. 上下文
2. memory

