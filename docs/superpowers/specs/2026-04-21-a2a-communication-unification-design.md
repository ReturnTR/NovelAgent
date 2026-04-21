# A2A 通信统一设计方案

**日期**：2026-04-21
**状态**：已确认

---

## 1. 目标

将现有的两种通信方式（直接通信 `/chat/stream` 和 A2A 通信）合并为统一的 A2A 协议层，同时将通信逻辑从 `BaseAgent` 中剥离，使 `BaseAgent` 只负责核心的 LangGraph 任务处理逻辑。

---

## 2. 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        Web Console Frontend                       │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼ HTTP (SSE)
┌─────────────────────────────────────────────────────────────────┐
│                    Web Console Backend (main_api.py)              │
│                         纯代理，无业务逻辑                         │
│                                                                 │
│   /api/agents/*     ──────────────────────────────→  Agent       │
│   /api/sessions/*   ──────────────────────────────→  Agent       │
│   /chat/stream      ──────POST {task}─────────────→  Agent      │
└─────────────────────────────────────────────────────────────────┘
                                │ A2A Protocol
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                     A2A Network (Agent Fleet)                    │
│                                                                 │
│   ┌─────────────┐      A2AEvent        ┌─────────────┐         │
│   │ Supervisor  │  ────────────────→  │  Character   │         │
│   │  Agent      │                      │   Agent      │         │
│   │  (Port 8001)│  ←───────────────   │  (Port 8002) │         │
│   └─────────────┘    TASK_RESPONSE     └─────────────┘         │
│         │                                                   │
│         │ User Message (source_type="user")                  │
│         ▼                                                   │
│   A2AEventHandler ──→ BaseAgent.process_task_stream()        │
│         │                                                   │
│         │ Session 维护在 Agent 内部                          │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. 新增 EventType.USER_MESSAGE

在 `agent/core/a2a/types.py` 中新增事件类型：

```python
class EventType(str, Enum):
    TASK_REQUEST = "task_request"
    TASK_RESPONSE = "task_response"
    TASK_PROGRESS = "task_progress"
    AGENT_DISCOVERY = "agent_discovery"
    AGENT_REGISTER = "agent_register"
    AGENT_UNREGISTER = "agent_unregister"
    HEARTBEAT = "heartbeat"
    ERROR = "error"
    USER_MESSAGE = "user_message"  # 新增：Web Console 发起的用户消息
```

**为什么用 EventType 而不是 content.source_type**：
- `event_type` 是 top-level 字段，`A2AEventServer` 可直接 switch 路由
- `A2AEventHandler` 无需解析 content 内部结构
- 扩展新来源只需新增 EventType，不改 content 结构

---

## 4. 新增 A2AEventHandler 类

**文件位置**：`agent/core/a2a/event_handler.py`

**职责**：
- 接收 `A2AEvent`（来自 A2A 网络）
- 接收 `USER_MESSAGE`（来自 Web Console）
- 调用 `BaseAgent.process_task_stream()` 处理
- 维护 Session 历史（读写 Agent 本地文件）
- yield 结构化事件给 FastAPI 端点

**核心接口**：

```python
class A2AEventHandler:
    def __init__(self, agent: BaseAgent, session_dir: str):
        """
        Args:
            agent: BaseAgent 实例
            session_dir: Agent 本地 Session 文件存储目录
        """

    async def handle_event(self, event: A2AEvent) -> AsyncIterator[Dict]:
        """
        处理 A2A 事件（Agent 间通信），yield 结构化事件
        Yields:
            {"type": "reasoning", "content": "..."}
            {"type": "tool_call", "tool_calls": [...]}
            {"type": "content", "content": "..."}
            {"type": "done", "skills_used": [...]}
        """

    async def handle_user_message(self, task: str, session_id: str) -> AsyncIterator[Dict]:
        """
        处理用户消息（来自 Web Console），yield 结构化事件
        """

    async def get_session_history(self, session_id: str) -> List[Dict]:
        """
        获取指定 session 的历史消息
        """

    def _save_message_to_session(self, session_id: str, message: Dict):
        """
        保存消息到 Agent 本地 Session 文件（JSONL 格式）
        """
```

---

## 5. BaseAgent 瘦身

**移除**（移到 `A2AEventHandler`）：
- `_on_event_received` 回调
- `_on_task_request` 回调
- `_get_session_messages` 方法
- `_append_agent_message_to_session` 方法
- `pending_events` 队列
- `event_server` 实例

**保留**：
- `process_task(task, context)` - 核心任务处理
- `process_task_stream(task, context)` - 流式任务处理
- `get_all_skills_metadata`
- `load_prompt`
- `_messages_to_dict`
- LangGraph 相关（`_build_graph`, `_init_llm`, `_build_standard_graph` 等）
- 工具加载（`_load_tools`）
- 技能加载（`_load_skills`）

**新增**：
- `set_event_handler(handler)` - 注入 A2AEventHandler（用于 main.py 挂载）

---

## 6. A2AEventServer 改造

**文件位置**：`agent/core/a2a/event_server.py`

**改造 `/event` 端点**：
- 支持流式响应（`StreamingResponse`）
- 根据 `event.event_type` 分发到 Handler

```python
@self.app.post("/event")
async def handle_event(request: Request):
    data = await request.json()
    event = A2AEvent(**data)

    if event.event_type == EventType.USER_MESSAGE:
        # 用户消息 → handle_user_message
        return StreamingResponse(
            handler.handle_user_message(
                event.content["task"],
                event.content["session_id"]
            ),
            media_type="text/event-stream"
        )
    else:
        # A2A 事件 → handle_event
        return StreamingResponse(
            handler.handle_event(event),
            media_type="text/event-stream"
        )
```

---

## 7. Agent main.py 改造

**示例（supervisor_agent/main.py）**：

```python
# 创建 Agent 实例
agent = SupervisorAgent(agent_dir, agent_id=agent_id, port=port)

# 创建 A2AEventHandler 并注入
from agent.core.a2a.event_handler import A2AEventHandler
handler = A2AEventHandler(
    agent=agent,
    session_dir=str(agent_dir / "sessions")
)
agent.set_event_handler(handler)

# 挂载 A2A 服务端
a2a_app = agent.get_a2a_app()
app.mount("/a2a", a2a_app)

# Session 历史接口（让 Backend 可以查询）
@app.get("/session/{session_id}/history")
async def get_session_history(session_id: str):
    messages = handler.get_session_history(session_id)
    return {"session_id": session_id, "messages": messages}

# /chat/stream 端点保留，内部改为通过 Handler 处理
@app.post("/chat/stream")
async def chat_stream(request: Request):
    data = await request.json()
    task = data.get("task")
    session_id = data.get("session_id") or os.getenv("AGENT_SESSION_ID", "default")

    return StreamingResponse(
        handler.handle_user_message(task, session_id),
        media_type="text/event-stream"
    )
```

---

## 8. Backend (main_api.py) 改造

Backend 变成**纯代理**，无业务逻辑：

```python
# 代理到 Agent 的 /session/{id}/history
@app.get("/api/sessions/{session_id}/messages")
async def get_session_messages(session_id: str):
    session = session_manager.get_session_by_id(session_id)
    port = session["port"]
    async with aiohttp.get(f"http://localhost:{port}/session/{session_id}/history") as resp:
        return await resp.json()

# 聊天代理到 Agent /chat/stream
@app.post("/chat/stream")
async def chat_stream(chat_message: ChatMessage):
    session = session_manager.get_session_by_id(chat_message.session_id)
    port = session["port"]
    async with aiohttp.post(
        f"http://localhost:{port}/chat/stream",
        json={"task": chat_message.message, "session_id": chat_message.session_id}
    ) as resp:
        return StreamingResponse(resp.content, media_type="text/event-stream")
```

---

## 9. 文件结构变更

```
agent/core/
├── base/
│   ├── agent_base.py        # 瘦身后：只有 LangGraph + LLM 逻辑
│   └── skill_manager.py     # 技能管理
├── a2a/
│   ├── event_handler.py     # ⭐ 新增：事件处理 + Session 维护
│   ├── event_server.py      # 改造：支持流式 + USER_MESSAGE
│   ├── types.py             # 改造：新增 USER_MESSAGE EventType
│   ├── client_tools.py      # 保持
│   ├── protocol.py          # 保持
│   ├── registry_server.py   # 保持
│   └── ...
```

---

## 10. 数据流

### 用户发送消息

```
Frontend → Backend /chat/stream
        → Agent /chat/stream
        → A2AEventHandler.handle_user_message()
        → A2AEventHandler._save_message_to_session() [保存用户消息]
        → agent.process_task_stream()
        → yield 结构化事件 (reasoning/tool_call/content/done)
        → A2AEventHandler._save_message_to_session() [保存 Agent 响应]
        → SSE 返回给 Backend → Frontend
```

### Agent 间通信

```
Agent A → A2AEvent (TASK_REQUEST) → Agent B /event
       → A2AEventHandler.handle_event()
       → agent.process_task_stream()
       → A2AEvent (TASK_RESPONSE) 返回给 Agent A
```

---

## 11. Session 存储设计

**存储位置**：`{agent_dir}/sessions/{session_id}.jsonl`

**格式**（每行一条 JSON）：
```jsonl
{"type": "message", "role": "user", "content": "...", "timestamp": "..."}
{"type": "message", "role": "assistant", "content": "...", "timestamp": "..."}
{"type": "message", "role": "tool", "tool_call_id": "...", "content": "...", "timestamp": "..."}
```

**Session 索引**：`sessions/sessions_index.json`
```json
{
  "sessions": [
    {
      "session_id": "xxx",
      "created_at": "...",
      "updated_at": "...",
      "status": "active"
    }
  ]
}
```

---

## 12. 实现顺序

1. 新增 `EventType.USER_MESSAGE` 到 `types.py`
2. 新增 `A2AEventHandler` 类到 `event_handler.py`
3. 改造 `A2AEventServer` 支持流式分发
4. 瘦 `BaseAgent`，移除通信相关代码
5. 改造 `Agent main.py` 挂载 Handler 和接口
6. 改造 `Backend main_api.py` 为纯代理模式
7. 测试完整流程
