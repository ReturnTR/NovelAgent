"""
Integration tests for A2AEventServer streaming endpoint.
Tests event dispatching based on event_type.
"""
import pytest
from unittest.mock import MagicMock
from httpx import ASGITransport, AsyncClient

from agent.core.a2a.types import AgentCard
from agent.core.a2a.event_server import A2AEventServer
from agent.core.a2a.event_handler import A2AEventHandler


@pytest.fixture
def mock_agent_card():
    """Create a mock AgentCard."""
    return AgentCard(
        agent_id="test-agent-001",
        agent_name="TestAgent",
        agent_type="supervisor",
        endpoint="http://localhost:9999",
        version="1.0.0",
        description="Test agent",
        capabilities=[],
        status="active"
    )


@pytest.fixture
def mock_agent():
    """Create a mock agent with async process_task_stream."""
    agent = MagicMock()
    agent.agent_id = "test-agent-001"
    agent.agent_name = "TestAgent"

    async def mock_stream(task, context):
        yield {"type": "reasoning", "content": "Thinking..."}
        yield {"type": "assistant", "content": "Hello from agent!"}
        yield {"type": "done", "skills_used": []}

    agent.process_task_stream = mock_stream
    return agent


@pytest.fixture
def event_server(mock_agent_card, mock_agent, isolated_session_dir):
    """Create A2AEventServer with mock handler."""
    handler = A2AEventHandler(
        agent=mock_agent,
        session_dir=isolated_session_dir
    )
    return A2AEventServer(
        self_agent_card=mock_agent_card,
        event_handler=handler
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
    """POST /event with USER_MESSAGE returns a response with streaming content type."""
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

        response = await client.post("/event", json=event)
        assert response.status_code == 200
        # Check it's a streaming response (SSE)
        assert "text/event-stream" in response.headers.get("content-type", "")
