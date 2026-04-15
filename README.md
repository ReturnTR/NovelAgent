# Novel Agent - 多Agent协作的小说创作系统

## 项目简介

Novel Agent 是一个基于多Agent协作的小说创作系统，采用模块化设计，支持多种类型的Agent协同工作。

## 项目结构

```
Novel_Agent/
├── agent_commons/          # 公共模块
│   ├── a2a/               # A2A协议
│   │   ├── identity.py    # Agent身份名片
│   │   ├── message_schema.py  # 消息格式
│   │   └── protocol.py    # A2A协议处理
│   ├── base/              # Agent基类
│   │   └── agent_base.py  # 所有Agent的基类
│   ├── factory/           # Agent工厂
│   │   └── agent_factory.py  # Agent创建工厂
│   ├── process/           # 进程管理
│   │   └── manager.py     # 进程管理器
│   ├── registry/          # Agent注册中心
│   │   └── agent_registry.py  # Agent注册表
│   ├── sessions/          # 会话管理
│   │   └── manager.py     # 会话管理器
│   └── coordinator.py     # 协调器主类
├── agents/                # Agent实现
│   ├── supervisor_agent/  # 主控Agent
│   │   ├── cores/
│   │   │   └── supervisor_agent.py
│   │   ├── skills/
│   │   ├── tools/
│   │   ├── prompts/
│   │   ├── memories/
│   │   ├── agent_config.json
│   │   └── main.py
│   └── character_agent/   # 人物生成Agent
│       ├── cores/
│       │   └── character_agent.py
│       ├── skills/
│       ├── tools/
│       ├── prompts/
│       ├── memories/
│       ├── agent_config.json
│       └── main.py
├── frontend/              # 前端界面
│   ├── index.html        # 主页面
│   ├── app.js            # 应用逻辑
│   └── style.css         # 样式文件
├── sessions/              # 会话文件存储
│   ├── supervisor/
│   ├── character/
│   ├── outline/
│   ├── content/
│   ├── theme/
│   └── cross_agent/
├── doc/                   # 文档
├── main_api.py           # 统一API入口
├── test_architecture.py  # 架构测试
└── requirements.txt      # 依赖包
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

### 3. 测试架构

```bash
python test_architecture.py
```

### 4. 启动服务

#### 启动统一API入口（端口8000）
```bash
python main_api.py
```

#### 启动主控Agent（端口8001）
```bash
cd agents/supervisor_agent
python main.py
```

#### 启动人物生成Agent（端口8002）
```bash
cd agents/character_agent
python main.py
```

### 5. 访问前端

打开浏览器访问：`http://localhost:8000`

## 前端功能

### 多Agent窗口设计

前端支持多个Agent窗口：
- 左侧边栏显示所有可用的Agent
- 点击Agent切换当前对话
- 支持新建Agent窗口
- 实时显示Agent在线状态

### Agent列表

- **Supervisor** - 主控Agent，协调其他Agent
- **Character** - 人物生成Agent
- **Outline** - 大纲生成Agent（待实现）
- **Content** - 内容生成Agent（待实现）
- **Theme** - 主题分析Agent（待实现）

## 创建新的Agent

### 步骤1：创建目录结构

```bash
mkdir -p agents/new_agent/{cores,skills,tools,prompts,memories}
touch agents/new_agent/__init__.py
touch agents/new_agent/tools/__init__.py
```

### 步骤2：创建配置文件

创建 `agents/new_agent/agent_config.json`：

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

创建 `agents/new_agent/cores/new_agent.py`：

```python
from agent_commons.base.agent_base import BaseAgent
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

创建 `agents/new_agent/main.py`（复制 supervisor_agent/main.py，修改类名）

### 步骤5：更新 main_api.py

在 `main_api.py` 中添加新Agent的端口配置：

```python
AGENT_PORTS = {
    "supervisor": 8001,
    "character": 8002,
    "new_agent": 8003  # 添加新Agent
}
```

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

### 3. Sessions 文件存储

会话记录存储在 `sessions/` 目录下，按Agent类型分类：
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

## API接口

### 统一API（端口8000）

- `GET /` - 前端页面
- `GET /api/agents` - 列出所有Agent
- `POST /chat/stream` - 流式聊天接口
- `GET /health` - 健康检查

### Agent API（各Agent端口）

- `POST /a2a/message` - A2A消息接口
- `GET /health` - 健康检查

## 开发计划

- [ ] 实现更多Agent类型（outline_agent, content_agent, theme_agent）
- [ ] 添加工具函数
- [ ] 集成LLM调用
- [ ] 实现流式输出优化
- [ ] 添加Agent间协作功能
- [ ] 实现前端多窗口管理

## 技术栈

- **后端**: FastAPI, Python 3.12
- **前端**: HTML, CSS, JavaScript
- **AI**: LangChain, OpenAI API
- **存储**: JSONL文件存储
- **协议**: A2A (Agent-to-Agent) 协议

## 最新功能更新

### 1. LLM集成与流式输出

**功能描述**：
- 集成LangChain和OpenAI API，支持多种LLM模型
- 支持Kimi API（moonshot-v1-8k模型）
- 实现流式输出，逐字显示响应内容
- 实时Markdown渲染，支持代码高亮

**技术实现**：
- BaseAgent添加了`_init_llm()`和`generate_response()`方法
- 使用langchain_openai的ChatOpenAI类
- 前端使用marked.js和highlight.js进行Markdown渲染
- SSE（Server-Sent Events）协议实现流式传输

**配置示例**：
```json
{
  "model": {
    "provider": "openai",
    "model_id": "moonshot-v1-8k",
    "temperature": 0.7,
    "max_tokens": 4000
  }
}
```

### 2. 会话管理功能完善

**功能描述**：
- 用户消息和助手回复都正确记录到会话文件
- 会话文件路径正确指向项目根目录的`sessions/{agent_type}`目录
- 新增`user_message`和`assistant_message`事件类型
- 支持会话持久化和恢复

**会话文件格式**：
```jsonl
{"type": "session", "version": 3, "id": "873fca7f-52bc-4843-9927-24f309c42018", ...}
{"type": "user_message", "role": "user", "content": "测试会话记录功能", ...}
{"type": "task_received", "task": "测试会话记录功能", ...}
{"type": "assistant_message", "role": "assistant", "content": "好的，我会记录我们的对话内容...", ...}
{"type": "task_completed", "result": {...}}
```

**技术实现**：
- BaseAgent从项目根目录初始化SessionManager
- Agent在处理任务时记录用户消息和助手回复
- 会话文件存储在`/Users/seco/AIProjects/Novel_Agent/sessions/{agent_type}/`目录

### 3. Agent切换时的会话恢复

**功能描述**：
- 切换Agent时会自动恢复该Agent之前的会话
- 如果该Agent有历史记录，会显示所有对话
- 如果没有历史记录，会显示欢迎信息
- 支持在不同Agent之间无缝切换

**技术实现**：
- 前端使用localStorage存储每个Agent的会话信息
- switchAgent函数从localStorage恢复会话
- 会话信息包括session_id和messages数组
- 页面刷新时自动恢复当前Agent的会话

**前端代码示例**：
```javascript
// 保存会话
localStorage.setItem(`session_${currentAgentType}`, JSON.stringify({
    session_id: currentSessionId,
    messages: messages
}));

// 恢复会话
const savedSession = localStorage.getItem(`session_${agentType}`);
if (savedSession) {
    const sessionData = JSON.parse(savedSession);
    currentSessionId = sessionData.session_id;
    messages = sessionData.messages || [];
}
```

### 4. 前端Agent显示优化

**功能描述**：
- 只显示在线的Agent，离线Agent不显示在列表中
- 实时更新Agent在线状态（每30秒刷新一次）
- 支持通过"新建Agent"按钮创建新的Agent窗口
- 每个Agent窗口都有独立的会话

**技术实现**：
- loadAgents函数过滤status为'active'的Agent
- 使用setInterval定时刷新Agent列表
- openNewAgentWindow函数打开新窗口并切换到指定Agent

### 5. 代码块样式修复

**功能描述**：
- 修复了代码块显示问题，现在代码块能够正确显示
- 支持语法高亮
- 深色背景代码块，浅色文本

**CSS样式**：
```css
.bubble pre {
    background: #2d2d2d;
    color: #f8f8f2;
    padding: 15px;
    border-radius: 8px;
    font-family: 'Courier New', monospace;
    font-size: 14px;
    line-height: 1.4;
}

.bubble pre code {
    background: transparent;
    color: inherit;
    padding: 0;
}
```

## 使用指南

### 发送消息
1. 在输入框中输入消息
2. 点击"发送"按钮或按Enter键
3. 消息会被正确记录到会话文件中
4. 助手回复也会被记录

### 切换Agent
1. 点击左侧Agent列表中的Agent
2. 会自动恢复该Agent的会话
3. 如果有历史记录，会显示所有对话
4. 如果没有历史记录，会显示欢迎信息

### 刷新页面
- 刷新页面后会恢复当前Agent的会话
- 所有历史对话都会保留

### 查看会话文件
- 会话文件存储在`/Users/seco/AIProjects/Novel_Agent/sessions/{agent_type}/`目录
- 每个会话都有一个唯一的session_id
- 文件格式为JSONL，每行一个JSON对象

## 许可证

MIT License


prompt ：
system_prompt：作为模型开头的prompt