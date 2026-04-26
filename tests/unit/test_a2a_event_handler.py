"""
Unit tests for A2AEventServer class.
Tests session management, event handling, and message processing.
"""
import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from core.a2a.types import A2AEvent, EventType
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
        yield {"type": "assistant", "content": "Hello!"}
        yield {"type": "done"}


class TestA2AEventServer:
    """Test suite for A2AEventServer."""

    @pytest.fixture
    def mock_agent_class(self):
        """Return MockAgent class for agent_class parameter"""
        return MockAgent

    @pytest.fixture
    def server(self, mock_agent_class, isolated_session_dir):
        """Create an A2AEventServer with mock agent and isolated session dir."""
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

    def test_handler_initialization(self, server, isolated_session_dir):
        """Server initializes correctly with agent and session_dir."""
        assert server.agent_id == "test-agent-001"
        assert server.session_manager.session_dir == Path(isolated_session_dir)
        assert server.session_manager.session_index_file.exists()

    def test_session_index_created(self, server):
        """Session index file is created on initialization."""
        with open(server.session_manager.session_index_file) as f:
            index = json.load(f)
        assert "sessions" in index
        assert index["sessions"] == []

    def test_get_or_create_session_new(self, server):
        """Creating a new session adds it to the index."""
        session = server.session_manager._get_or_create_session("session-001")
        assert session["session_id"] == "session-001"
        assert session["agent_id"] == "test-agent-001"
        assert session["status"] == "active"

        # Verify it's in the index
        index = server.session_manager._load_index()
        assert len(index["sessions"]) == 1
        assert index["sessions"][0]["session_id"] == "session-001"

    def test_get_or_create_session_existing(self, server):
        """Getting an existing session returns it without duplicating."""
        session1 = server.session_manager._get_or_create_session("session-001")
        session2 = server.session_manager._get_or_create_session("session-001")

        assert session1 == session2
        index = server.session_manager._load_index()
        assert len(index["sessions"]) == 1

    def test_append_message_to_session_file(self, server):
        """Messages are appended to session JSONL file."""
        server.session_manager._get_or_create_session("session-001")
        server.session_manager._append_message_to_session_file("session-001", {
            "type": "message",
            "role": "user",
            "content": "Hello",
            "timestamp": "2024-01-01T00:00:00Z"
        })

        session_file = server.session_manager.session_dir / "session-001.jsonl"
        assert session_file.exists()

        with open(session_file) as f:
            lines = f.readlines()
        assert len(lines) == 1
        assert "Hello" in lines[0]

    def test_get_session_history_empty(self, server):
        """Getting history for non-existent session returns empty list."""
        history = server.session_manager.get_session_history("nonexistent")
        assert history == []

    def test_get_session_history_with_messages(self, server):
        """Getting history returns all messages from session file."""
        session_id = "session-002"
        server.session_manager._get_or_create_session(session_id)

        # Add user message
        server.session_manager._append_message_to_session_file(session_id, {
            "type": "message",
            "role": "user",
            "content": "Hello agent",
            "timestamp": "2024-01-01T00:00:00Z"
        })

        # Add assistant message
        server.session_manager._append_message_to_session_file(session_id, {
            "type": "message",
            "role": "assistant",
            "content": "Hello user",
            "timestamp": "2024-01-01T00:00:01Z"
        })

        history = server.session_manager.get_session_history(session_id)
        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[0]["content"] == "Hello agent"
        assert history[1]["role"] == "assistant"
        assert history[1]["content"] == "Hello user"

    def test_get_session_history_filters_metadata(self, server):
        """History only returns message and agent type events."""
        session_id = "session-003"
        server.session_manager._get_or_create_session(session_id)

        # Add various types
        server.session_manager._append_message_to_session_file(session_id, {
            "type": "message",
            "role": "user",
            "content": "Test",
            "timestamp": "2024-01-01T00:00:00Z"
        })
        server.session_manager._append_message_to_session_file(session_id, {
            "type": "session_metadata",  # Should be filtered
            "session_id": session_id
        })

        history = server.session_manager.get_session_history(session_id)
        assert len(history) == 1
        assert history[0]["type"] == "message"


class TestA2AEventServerAsync:
    """Test async methods of A2AEventServer."""

    @pytest.fixture
    def mock_agent_class(self):
        """Return MockAgent class for agent_class parameter"""
        return MockAgent

    @pytest.fixture
    def server(self, mock_agent_class, isolated_session_dir):
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
    async def test_handle_user_message_saves_user_message(self, server):
        """handle_user_message saves user message to session before processing."""
        session_id = "async-session-001"
        task = "Hello agent"

        events = []
        async for event in server.handle_user_message(task, session_id):
            events.append(event)

        # Verify user message was saved
        history = server.session_manager.get_session_history(session_id)
        assert len(history) == 3  # user + reasoning + assistant

        # Verify user message content
        user_msg = history[0]
        assert user_msg["role"] == "user"
        assert user_msg["content"] == task

    @pytest.mark.asyncio
    async def test_handle_user_message_yields_events(self, server):
        """handle_user_message yields events from agent processing."""
        session_id = "async-session-002"
        task = "Test task"

        events = []
        async for event in server.handle_user_message(task, session_id):
            events.append(event)

        assert len(events) == 3
        assert events[0]["type"] == "reasoning"
        assert events[1]["type"] == "assistant"
        assert events[2]["type"] == "done"

    @pytest.mark.asyncio
    async def test_handle_event_processes_task_request(self, server):
        """handle_event processes A2A TASK_REQUEST events."""
        event = A2AEvent(
            event_id="evt-001",
            event_type=EventType.TASK_REQUEST,
            source="other-agent",
            target="test-agent-001",
            task_id="task-001",
            content={
                "task": "Process this task",
                "context": []
            }
        )

        events = []
        async for evt in server.handle_event(event):
            events.append(evt)

        assert len(events) == 3
        assert events[0]["type"] == "reasoning"
