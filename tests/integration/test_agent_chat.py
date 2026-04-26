"""
Integration tests for Agent chat streaming endpoint.
Tests session management with mock LLM.
"""
import pytest
import uuid
import json
from pathlib import Path
from unittest.mock import MagicMock

from httpx import ASGITransport, AsyncClient


@pytest.fixture
def session_id():
    """Generate UUID format session_id matching web_console sessions format."""
    return str(uuid.uuid4())


@pytest.fixture
def mock_agent():
    """Create a mock agent with async process_task_stream."""
    agent = MagicMock()
    agent.agent_id = "test-supervisor-001"
    agent.agent_name = "TestSupervisor"
    agent.agent_type = "supervisor"
    agent.tools = []

    async def mock_stream(task, context):
        yield {"type": "reasoning", "content": "Thinking..."}
        yield {"type": "assistant", "content": f"Response to: {task}"}
        yield {"type": "done"}

    agent.process_task_stream = mock_stream
    agent.add_tools_and_restart = lambda tools: setattr(agent, 'tools', agent.tools + tools)
    return agent


@pytest.fixture
def agent_app(mock_agent, tmp_path):
    """Create A2AEventServer app for testing."""
    from core.a2a import A2AEventServer

    session_dir = tmp_path / "sessions"
    session_dir.mkdir(exist_ok=True)

    a2a_server = A2AEventServer(
        agent_id="test-supervisor-001",
        config={"agent_name": "TestSupervisor", "agent_type": "supervisor", "capabilities": []},
        agent_dir=Path("/tmp"),
        port=8001,
        registry_endpoint="http://localhost:8000",
        session_dir=str(session_dir),
        agent_class=mock_agent,
    )

    return a2a_server.app, a2a_server, session_dir


@pytest.mark.asyncio
async def test_chat_stream_returns_streaming(agent_app, session_id):
    """POST /chat/stream returns streaming response."""
    app, _, _ = agent_app

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        timeout=30.0
    ) as client:
        response = await client.post(
            "/chat/stream",
            json={"task": "你好", "session_id": session_id}
        )
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")


@pytest.mark.asyncio
async def test_chat_stream_yields_events(agent_app, session_id):
    """POST /chat/stream yields events from mock agent."""
    app, _, _ = agent_app

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        timeout=30.0
    ) as client:
        response = await client.post(
            "/chat/stream",
            json={"task": "hello", "session_id": session_id}
        )

        events = []
        async for line in response.aiter_lines():
            if line.startswith("data: "):
                event_data = json.loads(line[6:])
                events.append(event_data)

        assert len(events) == 3
        assert events[0]["type"] == "reasoning"
        assert events[1]["type"] == "assistant"
        assert events[2]["type"] == "done"


@pytest.mark.asyncio
async def test_session_history_stored(agent_app, session_id):
    """Session messages are stored and retrievable."""
    app, a2a_server, _ = agent_app

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        timeout=30.0
    ) as client:
        # Send a message
        await client.post(
            "/chat/stream",
            json={"task": "测试消息", "session_id": session_id}
        )

        # Verify via endpoint
        response = await client.get(f"/session/{session_id}/history")
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == session_id
        assert len(data["messages"]) >= 2


@pytest.mark.asyncio
async def test_session_index_created(agent_app, session_id):
    """Session index file is created."""
    app, _, session_dir = agent_app

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        timeout=30.0
    ) as client:
        await client.post(
            "/chat/stream",
            json={"task": "test", "session_id": session_id}
        )

    # Check index file exists
    index_file = session_dir / "sessions_index.json"
    assert index_file.exists()

    with open(index_file) as f:
        index = json.load(f)
    assert "sessions" in index
    assert len(index["sessions"]) == 1
    assert index["sessions"][0]["session_id"] == session_id


@pytest.mark.asyncio
async def test_a2a_event_endpoint(agent_app, session_id):
    """POST /a2a/event with USER_MESSAGE works."""
    app, _, _ = agent_app

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        timeout=30.0
    ) as client:
        event = {
            "event_id": "evt-test-001",
            "event_type": "user_message",
            "source": "test-client",
            "content": {
                "task": "A2A test message",
                "session_id": session_id
            }
        }

        response = await client.post("/a2a/event", json=event)
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")


@pytest.mark.asyncio
async def test_agent_card_endpoint(agent_app):
    """GET /.well-known/agent-card.json returns agent card."""
    app, _, _ = agent_app

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        timeout=5.0
    ) as client:
        response = await client.get("/.well-known/agent-card.json")
        assert response.status_code == 200
        data = response.json()
        assert data["agent_id"] == "test-supervisor-001"


@pytest.mark.asyncio
async def test_health_endpoint(agent_app):
    """GET /health returns health status."""
    app, _, _ = agent_app

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        timeout=5.0
    ) as client:
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_multiple_sessions(agent_app):
    """Multiple sessions are tracked independently."""
    app, a2a_server, _ = agent_app

    session1 = str(uuid.uuid4())
    session2 = str(uuid.uuid4())

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        timeout=30.0
    ) as client:
        await client.post("/chat/stream", json={"task": "msg1", "session_id": session1})
        await client.post("/chat/stream", json={"task": "msg2", "session_id": session2})

    # Check sessions are independent
    history1 = a2a_server.session_manager.get_session_history(session1)
    history2 = a2a_server.session_manager.get_session_history(session2)

    assert len(history1) >= 2  # at least user + assistant
    assert len(history2) >= 2
    assert history1[0]["content"] == "msg1"
    assert history2[0]["content"] == "msg2"
