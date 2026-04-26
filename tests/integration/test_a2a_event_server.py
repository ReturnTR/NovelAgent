"""
Integration tests for A2AEventServer streaming endpoint.
Tests event dispatching based on event_type.
"""
import pytest
from pathlib import Path
from unittest.mock import MagicMock
from httpx import ASGITransport, AsyncClient

from core.a2a.event_server import A2AEventServer


class MockAgent:
    """Mock agent for testing A2AEventServer"""
    def __init__(self, config=None, agent_dir=None):
        self.agent_id = "test-agent-001"
        self.agent_name = "TestAgent"
        self.agent_type = "supervisor"
        self.port = 9999
        self.capabilities = []
        self.tools = []

    def set_a2a_server_tools(self, server):
        pass

    def add_tools_and_restart(self, tools):
        self.tools = self.tools + tools

    async def process_task_stream(self, task, context=None):
        yield {"type": "reasoning", "content": "Thinking..."}
        yield {"type": "assistant", "content": "Hello from agent!"}
        yield {"type": "done"}


@pytest.fixture
def mock_agent_class():
    """Return MockAgent class for agent_class parameter"""
    return MockAgent


@pytest.fixture
def event_server(mock_agent_class, isolated_session_dir):
    """Create A2AEventServer with mock agent class."""
    config = {
        "agent_name": "TestAgent",
        "agent_type": "supervisor",
        "capabilities": [],
    }
    return A2AEventServer(
        agent_id="test-agent-001",
        config=config,
        agent_dir=Path(isolated_session_dir),
        port=9999,
        registry_endpoint="http://localhost:8000",
        session_dir=str(isolated_session_dir),
        agent_class=mock_agent_class,
    )


@pytest.mark.asyncio
async def test_event_server_root(event_server):
    """GET / returns agent card."""
    async with AsyncClient(
        transport=ASGITransport(app=event_server.app),
        base_url="http://test"
    ) as client:
        response = await client.get("/.well-known/agent-card.json")
        assert response.status_code == 200
        data = response.json()
        assert data["agent_id"] == "test-agent-001"


@pytest.mark.asyncio
async def test_event_server_health(event_server):
    """GET /health returns health status."""
    async with AsyncClient(
        transport=ASGITransport(app=event_server.app),
        base_url="http://test"
    ) as client:
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_event_server_user_message_returns_streaming(event_server):
    """POST /a2a/event with USER_MESSAGE returns a response with streaming content type."""
    async with AsyncClient(
        transport=ASGITransport(app=event_server.app),
        base_url="http://test",
        timeout=5.0
    ) as client:
        event = {
            "event_id": "evt-user-001",
            "event_type": "user_message",
            "source": "web-console",
            "content": {
                "task": "Hello agent",
                "session_id": "test-session-001"
            }
        }

        response = await client.post("/a2a/event", json=event)
        assert response.status_code == 200
        # Check it's a streaming response (SSE)
        assert "text/event-stream" in response.headers.get("content-type", "")


@pytest.mark.asyncio
async def test_chat_stream_endpoint(event_server):
    """POST /chat/stream returns streaming response."""
    async with AsyncClient(
        transport=ASGITransport(app=event_server.app),
        base_url="http://test",
        timeout=5.0
    ) as client:
        response = await client.post(
            "/chat/stream",
            json={"task": "Hello", "session_id": "test-session"}
        )
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")
