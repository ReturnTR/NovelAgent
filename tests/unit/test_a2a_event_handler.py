"""
Unit tests for A2AEventHandler class.
Tests session management, event handling, and message processing.
"""
import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from agent.core.a2a.types import A2AEvent, EventType
from agent.core.a2a.event_handler import A2AEventHandler


class TestA2AEventHandler:
    """Test suite for A2AEventHandler."""

    @pytest.fixture
    def mock_agent(self):
        """Create a mock BaseAgent."""
        agent = MagicMock()
        agent.agent_id = "test-agent-001"
        agent.agent_name = "TestAgent"
        agent.agent_card = MagicMock()
        return agent

    @pytest.fixture
    def handler(self, mock_agent, isolated_session_dir):
        """Create an A2AEventHandler with mock agent and isolated session dir."""
        return A2AEventHandler(
            agent=mock_agent,
            session_dir=isolated_session_dir
        )

    def test_handler_initialization(self, handler, mock_agent, isolated_session_dir):
        """Handler initializes correctly with agent and session_dir."""
        assert handler.agent == mock_agent
        assert handler.session_dir == Path(isolated_session_dir)
        assert handler.session_index_file.exists()

    def test_session_index_created(self, handler):
        """Session index file is created on initialization."""
        with open(handler.session_index_file) as f:
            index = json.load(f)
        assert "sessions" in index
        assert index["sessions"] == []

    def test_get_or_create_session_new(self, handler):
        """Creating a new session adds it to the index."""
        session = handler._get_or_create_session("session-001")
        assert session["session_id"] == "session-001"
        assert session["agent_id"] == "test-agent-001"
        assert session["status"] == "active"

        # Verify it's in the index
        index = handler._load_index()
        assert len(index["sessions"]) == 1
        assert index["sessions"][0]["session_id"] == "session-001"

    def test_get_or_create_session_existing(self, handler):
        """Getting an existing session returns it without duplicating."""
        session1 = handler._get_or_create_session("session-001")
        session2 = handler._get_or_create_session("session-001")

        assert session1 == session2
        index = handler._load_index()
        assert len(index["sessions"]) == 1

    def test_append_message_to_session_file(self, handler):
        """Messages are appended to session JSONL file."""
        handler._get_or_create_session("session-001")
        handler._append_message_to_session_file("session-001", {
            "type": "message",
            "role": "user",
            "content": "Hello",
            "timestamp": "2024-01-01T00:00:00Z"
        })

        session_file = handler.session_dir / "session-001.jsonl"
        assert session_file.exists()

        with open(session_file) as f:
            lines = f.readlines()
        assert len(lines) == 1
        assert "Hello" in lines[0]

    def test_get_session_history_empty(self, handler):
        """Getting history for non-existent session returns empty list."""
        history = handler.get_session_history("nonexistent")
        assert history == []

    def test_get_session_history_with_messages(self, handler):
        """Getting history returns all messages from session file."""
        session_id = "session-002"
        handler._get_or_create_session(session_id)

        # Add user message
        handler._append_message_to_session_file(session_id, {
            "type": "message",
            "role": "user",
            "content": "Hello agent",
            "timestamp": "2024-01-01T00:00:00Z"
        })

        # Add assistant message
        handler._append_message_to_session_file(session_id, {
            "type": "message",
            "role": "assistant",
            "content": "Hello user",
            "timestamp": "2024-01-01T00:00:01Z"
        })

        history = handler.get_session_history(session_id)
        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[0]["content"] == "Hello agent"
        assert history[1]["role"] == "assistant"
        assert history[1]["content"] == "Hello user"

    def test_get_session_history_filters_metadata(self, handler):
        """History only returns message and agent type events."""
        session_id = "session-003"
        handler._get_or_create_session(session_id)

        # Add various types
        handler._append_message_to_session_file(session_id, {
            "type": "message",
            "role": "user",
            "content": "Test",
            "timestamp": "2024-01-01T00:00:00Z"
        })
        handler._append_message_to_session_file(session_id, {
            "type": "session_metadata",  # Should be filtered
            "session_id": session_id
        })

        history = handler.get_session_history(session_id)
        assert len(history) == 1
        assert history[0]["type"] == "message"


class TestA2AEventHandlerAsync:
    """Test async methods of A2AEventHandler."""

    @pytest.fixture
    def mock_agent(self):
        """Create a mock agent with async process_task_stream."""
        agent = MagicMock()
        agent.agent_id = "test-agent-001"
        agent.agent_name = "TestAgent"

        # Mock process_task_stream as an async generator
        async def mock_stream(task, context):
            yield {"type": "reasoning", "content": "Thinking..."}
            yield {"type": "assistant", "content": "Hello!"}
            yield {"type": "done", "skills_used": []}

        agent.process_task_stream = mock_stream
        return agent

    @pytest.fixture
    def handler(self, mock_agent, isolated_session_dir):
        return A2AEventHandler(
            agent=mock_agent,
            session_dir=isolated_session_dir
        )

    @pytest.mark.asyncio
    async def test_handle_user_message_saves_user_message(self, handler):
        """handle_user_message saves user message to session before processing."""
        session_id = "async-session-001"
        task = "Hello agent"

        events = []
        async for event in handler.handle_user_message(task, session_id):
            events.append(event)

        # Verify user message was saved
        history = handler.get_session_history(session_id)
        assert len(history) == 2  # user + assistant

        # Verify user message content
        user_msg = history[0]
        assert user_msg["role"] == "user"
        assert user_msg["content"] == task

    @pytest.mark.asyncio
    async def test_handle_user_message_yields_events(self, handler):
        """handle_user_message yields events from agent processing."""
        session_id = "async-session-002"
        task = "Test task"

        events = []
        async for event in handler.handle_user_message(task, session_id):
            events.append(event)

        assert len(events) == 3
        assert events[0]["type"] == "reasoning"
        assert events[1]["type"] == "assistant"
        assert events[2]["type"] == "done"

    @pytest.mark.asyncio
    async def test_handle_event_processes_task_request(self, handler):
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
        async for evt in handler.handle_event(event):
            events.append(evt)

        assert len(events) == 3
        assert events[0]["type"] == "reasoning"
