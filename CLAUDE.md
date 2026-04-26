# NovelAgent3 项目指南

## 项目架构

```
NovelAgent3/
├── agents/                          # Agent 实例
│   ├── supervisor_agent/            # 主控 Agent
│   │   ├── agent_config.json        # Agent 配置
│   │   ├── prompts/                # Prompt 模板
│   │   ├── skills/                  # 技能目录（实际加载来源）
│   │   └── sessions/                # 会话历史
│   └── test_agent/                  # 测试专用 Agent
│
├── core/                           # 核心模块
│   ├── base/                        # 基础组件
│   │   ├── agent_base.py           # BaseAgent 基类
│   │   ├── llm/                    # LLM 提供者
│   │   │   └── openai_provider.py  # Kimi k2.5 支持
│   │   ├── node_factory.py         # LangGraph 节点工厂
│   │   ├── skill_manager.py        # 技能管理器
│   │   └── tool_manager.py         # 工具管理器
│   └── a2a/                        # A2A 通信
│       ├── event_server.py         # A2A 事件服务器
│       └── types.py               # A2A 类型定义
│
└── tests/                          # 测试
    ├── integration/                # 集成测试
    │   ├── conftest.py             # Fixtures
    │   ├── test_real_agent.py      # 真实 Agent 测试
    │   └── test_tool_calling.py    # 工具调用测试
    └── utils/                      # 测试工具
        ├── agent_runner.py         # Agent 生命周期管理
        └── checkers.py             # LogChecker, SessionChecker
```

## 核心概念

### 1. Agent 配置 (agent_config.json)

| 字段 | 用途 | 备注 |
|------|------|------|
| `capabilities` | 构建 AgentCard，用于 A2A 通信 | ✅ 实际使用 |
| `skills` (配置) | 无实际作用 | ❌ 冗余字段 |
| `skills` (目录) | `agent_dir/skills/` | ✅ 实际加载来源 |
| `tools` | 工具列表 | ✅ 实际使用 |
| `model` | LLM 配置 | ✅ 实际使用 |

### 2. 工具调用流程

```
用户请求
    ↓
process_task_stream()  [agent_base.py]
    ↓
LLM.invoke() → [TOOL_CALL]  [openai_provider.py]
    ↓
工具执行 → [TOOL_RESULT:OK/FAIL]  [agent_base.py]
    ↓
LLM.invoke() (第二次) → 最终回复
```

### 3. A2A 通信上下文处理

子 Agent 收到请求时，会**主动加载自己的 A2A 会话历史**：

```
收到 A2A 事件
    ↓
从 session 文件加载历史（a2a_{source}.jsonl）
    ↓
合并发送方传来的额外上下文（如果有）
    ↓
传入 process_task_stream() 处理
```

**Session 消息格式**（统一）：

| type | role | 数据字段 | 说明 |
|------|------|---------|------|
| `message` | `user` | `content` | 用户消息 |
| `message` | `assistant` | `content`, `tool_calls` | Assistant 消息 |
| `message` | `tool` | `tool_call_id`, `content` | 工具结果 |
| `agent_request` | `user` | `task` | 来自其他 Agent 的请求 |
| `agent_response` | `assistant` | `content` | 发回给请求方的响应 |

### 4. 推理模式 (Kimi k2.5)

- `temperature=1.0` 启用思考模式
- `reasoning_content` 必须在带 tool_calls 的 assistant 消息中填充
- 工具调用流程必须保留 `tool_calls`，不能清空

### 5. Agent 对外 API 端点

| 端点 | 方法 | 功能 |
|------|------|------|
| `/.well-known/agent-card.json` | GET | 获取 Agent 元信息 |
| `/session/{session_id}/history` | GET | 获取 session 历史消息 |
| `/session/list` | GET | 列出所有 session |
| `/session/{session_id}/activate` | POST | 激活指定 session |
| `/chat/stream` | POST | 流式聊天（Web Console） |
| `/a2a/event` | POST | **核心**：处理 A2A 事件 |
| `/health` | GET | 健康检查 |

## 测试框架

### 运行测试

```bash
# 运行所有集成测试
python -m pytest tests/integration/ -v

# 运行工具调用测试
python -m pytest tests/integration/test_tool_calling.py -v

# 运行真实 Agent 测试
python -m pytest tests/integration/test_real_agent.py -v
```

### 测试 Fixtures

| Fixture | 用途 |
|---------|------|
| `agent_runner` | Agent 启动/停止/聊天 |
| `session_checker` | Session 断言 |
| `chat_result` | 发送聊天并返回 ChatResult |

### 测试示例

```python
@pytest.mark.asyncio
async def test_execute_bash_tool(agent_runner, session_checker):
    events = await agent_runner.chat_async("执行 ls 命令")

    from tests.utils.agent_runner import ChatResult
    result = ChatResult(events)

    assert result.has_tool_call
    assert result.first_tool_name == "execute_bash"

    session = session_checker("test-session")
    session.assert_has_tool_call("execute_bash")
    session.assert_has_reasoning()
```

### 日志标签

启用方式：`export AGENT_DEBUG=true`

| 标签 | 位置 | 内容 |
|------|------|------|
| `[LLM_REQUEST]` | openai_provider.py | LLM 请求消息数 |
| `[LLM_RESPONSE]` | openai_provider.py | LLM 响应内容、tool_calls |
| `[REASONING_INJECT]` | openai_provider.py | reasoning_content 注入 |
| `[TOOL_CALL]` | agent_base.py | 工具名称和参数 |
| `[TOOL_RESULT:OK/FAIL]` | agent_base.py | 工具执行结果和耗时 |

## 重要配置

### 环境变量

| 变量 | 用途 | 示例 |
|------|------|------|
| `OPENAI_API_KEY` | LLM API 密钥 | `sk-...` |
| `OPENAI_API_BASE` | LLM API 地址 | `https://api.moonshot.cn/v1` |
| `AGENT_DIR` | Agent 配置目录 | `/agents/supervisor_agent` |
| `AGENT_DEBUG` | 启用调试日志 | `true`/`false` |

### 调试模式

```bash
# 启用全部调试
export AGENT_DEBUG=true

# 只启用 LLM 调试
export AGENT_DEBUG_LLM=true

# 只启用工具调试
export AGENT_DEBUG_TOOL=true
```

---

## 开发准则

1. **Think Before Coding** - 不确定时先问清楚
2. **Simplicity First** - 最少代码解决问题
3. **Surgical Changes** - 只改需要的，清理自己的垃圾
4. **Goal-Driven Execution** - 定义可验证的目标，用测试确认

---

## 常见问题

### Q: 为什么 tools 没有传递给 LLM？

检查 `openai_provider.py` 中是否手动将 tools 添加到 payload：
```python
payload["tools"] = tools_list
```

### Q: 为什么 tool_calls 被清空了？

检查 `openai_provider.py` 中是否有这段错误代码：
```python
# 错误：会清空 tool_calls
if not msg_dict.get("content") and msg_dict.get("tool_calls"):
    msg_dict["tool_calls"] = []  # 不要这样做！
```

### Q: 为什么 reasoning_content 缺失？

Kimi k2.5 启用思考模式时，带 tool_calls 的 assistant 消息必须包含 reasoning_content。使用 `_inject_reasoning_content()` 方法注入。

### Q: 如何添加新工具？

1. 在 `core/base/tools/` 创建工具文件
2. 在 `agent_config.json` 的 `tools` 数组中添加配置
3. 工具类需要实现 `@tool` 装饰器
