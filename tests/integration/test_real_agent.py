"""
Integration tests using real Agent (not mock).
Tests actual HTTP endpoints with real session management.

Requires:
- Agent modules to be importable
- LLM API configured (MOONSHOT_API_KEY or similar)

Run with:
    pytest tests/integration/test_real_agent.py -v
"""
import pytest
import uuid
import json
import asyncio
import os
from pathlib import Path

from httpx import ASGITransport, AsyncClient


# monkeypatch 是 pytest 内置的 fixture，专门用于在测试运行时动态修改属性/环境变量。

@pytest.fixture
def project_root():
    from pathlib import Path
    return Path(__file__).parent.parent.parent


@pytest.fixture
async def real_agent_server(project_root, monkeypatch):
    """
    Create real Agent and return its A2AEventServer app.
    Uses real SupervisorAgent with actual LLM configuration.
    """
    import sys

    # Add paths needed for imports
    sys.path.insert(0, str(project_root))
    sys.path.insert(0, str(project_root / "agents" / "supervisor_agent"))

    # Set REAL API credentials (override conftest's fake values)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-YLiZarg7OKEjYeqMqiTr9dQ1gMlNbKUOuqBYkkT8dG5CXI7L")
    monkeypatch.setenv("OPENAI_API_BASE", "https://api.moonshot.cn/v1")
    monkeypatch.setenv("TESTING", "1")

    # Import real Agent
    from cores.supervisor_agent import SupervisorAgent
    from core.a2a.event_server import A2AEventServer

    # Create real agent via A2AEventServer
    agent_dir = project_root / "agents" / "supervisor_agent"
    config_path = agent_dir / "agent_config.json"
    import json
    config = json.loads(config_path.read_text())

    a2a_server = A2AEventServer(
        agent_id="test-supervisor-real",
        config=config,
        agent_dir=agent_dir,
        port=8099,
        agent_class=SupervisorAgent
    )

    # Return the app and the a2a_server instance
    return a2a_server.app, a2a_server


@pytest.fixture
def session_id():
    return f"test-{uuid.uuid4().hex[:8]}"


@pytest.mark.asyncio
async def test_real_agent_chat_stream(real_agent_server, session_id):
    """
    Test /chat/stream endpoint with real LLM.
    This is the main integration test - sends real request to real agent.
    """
    app, agent = real_agent_server

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        timeout=120.0
    ) as client:
        response = await client.post(
            "/chat/stream",
            json={"task": "你好，请回复简单的'收到'。", "session_id": session_id}
        )
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")

        # Collect events
        events = []
        async for line in response.aiter_lines():
            if line.startswith("data: "):
                event_data = json.loads(line[6:])
                events.append(event_data)
                print(f"Event: {event_data.get('type')} - {event_data.get('content', '')[:50]}...")

        # Verify we got events
        assert len(events) > 0, "Should receive at least one event"

        # Last event should be 'done'
        assert events[-1].get("type") == "done", f"Last event should be 'done', got {events[-1]}"


@pytest.mark.asyncio
async def test_real_agent_session_history(real_agent_server, session_id):
    """Test that messages are stored in session history."""
    app, agent = real_agent_server

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        timeout=60.0
    ) as client:
        # Send a message
        await client.post(
            "/chat/stream",
            json={"task": "测试消息", "session_id": session_id}
        )

    # Give it a moment to finish writing
    await asyncio.sleep(0.5)

    # Check history via endpoint
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        timeout=10.0
    ) as client:
        response = await client.get(f"/session/{session_id}/history")
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == session_id
        assert len(data["messages"]) >= 2  # at least user + assistant


@pytest.mark.asyncio
async def test_real_agent_tool_calling(real_agent_server):
    """
    Test that when real LLM calls a tool, the tool call is recorded in session.
    Uses real LLM - no mocking.
    """
    _, a2a_server = real_agent_server
    session_id = "test-tool-session"

    # 直接调用 handle_user_message，使用真实 LLM
    print("Calling handle_user_message with real LLM...")
    print(f"Agent tools: {[(t.name, type(t).__name__) for t in a2a_server.agent.tools]}")

    # 检查 bind_tools 后的 LLM
    llm_after_bind = a2a_server.agent.llm._llm
    print(f"LLM after bind type: {type(llm_after_bind)}")
    print(f"LLM after bind has tools attr: {hasattr(llm_after_bind, 'tools')}")

    # 检查 bound_tools
    bound_tools = getattr(llm_after_bind, 'bound_tools', 'N/A')
    print(f"bound_tools: {bound_tools}")
    events = []
    async for event in a2a_server.handle_user_message("当前工作空间有哪些文件？请用 ls 命令查看", session_id):
        evt_type = event.get("type")
        content = event.get("content", "")
        print(f"Event: {evt_type} - {content[:100] if content else ''}")
        events.append(event)

    print(f"\nTotal events: {len(events)}")

    # 检查是否有工具调用
    tool_calls = [e for e in events if e.get("type") == "tool_call"]
    tool_results = [e for e in events if e.get("type") == "tool_result"]

    print(f"Tool calls: {len(tool_calls)}, Tool results: {len(tool_results)}")

    if len(tool_calls) > 0:
        print(f"Tool call: {tool_calls[0]}")

    if len(tool_results) > 0:
        print(f"Tool result: {tool_results[0].get('content')[:100]}...")

    # 验证有工具调用
    assert len(tool_calls) > 0, "Real LLM should call a tool"
    assert len(tool_results) > 0, "Should have tool result"

    # 验证工具是 execute_bash
    tool_call = tool_calls[0]
    tool_name = tool_call.get("tool_calls", [{}])[0].get("name")
    tool_args = tool_call.get("tool_calls", [{}])[0].get("arguments", {})
    print(f"Tool: {tool_name}, Args: {tool_args}")

    assert tool_name == "execute_bash"
    assert "ls" in tool_args.get("command", ""), f"Command should contain ls, got: {tool_args}"

    # 检查 session 历史
    history = a2a_server.session_manager.get_session_history(session_id)
    print(f"\nSession history ({len(history)} messages):")
    for i, msg in enumerate(history):
        print(f"  {i+1}. type={msg.get('type')}, role={msg.get('role')}")
        if msg.get("tool_calls"):
            print(f"      tool_calls: {msg.get('tool_calls')}")
        if msg.get("content"):
            content = str(msg.get('content'))[:100]
            print(f"      content: {content}...")

    # 验证 session 记录
    assistant_with_tool = [m for m in history
                           if m.get("type") == "message"
                           and m.get("role") == "assistant"
                           and m.get("tool_calls")]
    tool_msgs = [m for m in history if m.get("role") == "tool"]

    assert len(assistant_with_tool) > 0, "Session should contain assistant message with tool_calls"
    assert len(tool_msgs) > 0, "Session should contain tool result messages"

    print(f"\nVerified: {len(assistant_with_tool)} assistant with tool_calls, {len(tool_msgs)} tool messages")
