"""
Unit tests for A2A data types.
Tests: AgentCard, A2AEvent, EventType, SendMessageMode Pydantic models.
"""
from core.a2a.types import (
    AgentCard,
    AgentCapability,
    A2AEvent,
    EventType,
    SendMessageMode,
)


def test_agent_card_default_values():
    """status defaults to 'active', version defaults to '1.0.0'."""
    card = AgentCard(
        agent_id="test-001",
        agent_name="Test Agent",
        agent_type="supervisor",
        endpoint="http://localhost:8001",
    )
    assert card.status == "active"
    assert card.version == "1.0.0"
    assert card.capabilities == []


def test_agent_card_full_construction():
    """All fields are correctly assigned on construction."""
    cap = AgentCapability(name="create_character", description="Creates a character")
    card = AgentCard(
        agent_id="sup-001",
        agent_name="Supervisor",
        agent_type="supervisor",
        endpoint="http://localhost:8001",
        version="2.0.0",
        description="Main controller",
        capabilities=[cap],
        status="active",
    )
    assert card.agent_id == "sup-001"
    assert card.agent_name == "Supervisor"
    assert card.agent_type == "supervisor"
    assert card.endpoint == "http://localhost:8001"
    assert card.version == "2.0.0"
    assert card.description == "Main controller"
    assert len(card.capabilities) == 1
    assert card.capabilities[0].name == "create_character"


def test_a2a_event_construction():
    """All fields are correctly assigned."""
    event = A2AEvent(
        event_id="evt-abc123",
        event_type=EventType.TASK_REQUEST,
        source="sup-001",
        target="char-001",
        task_id="task-xyz",
        content={"task": "create a hero", "context": {}},
    )
    assert event.event_id == "evt-abc123"
    assert event.event_type == EventType.TASK_REQUEST
    assert event.source == "sup-001"
    assert event.target == "char-001"
    assert event.task_id == "task-xyz"
    assert event.content["task"] == "create a hero"


def test_a2a_event_optional_target_is_none_by_default():
    """target is Optional[str] and defaults to None (broadcast)."""
    event = A2AEvent(
        event_id="evt-001",
        event_type=EventType.TASK_REQUEST,
        source="agent-001",
    )
    assert event.target is None
    assert event.task_id is None


def test_all_event_types_exist():
    """All event types are present in the enum."""
    expected = [
        "task_request",
        "task_response",
        "user_message",
    ]
    actual = [e.value for e in EventType]
    for e in expected:
        assert e in actual, f"EventType.{e} is missing, got {actual}"


def test_user_message_event_type():
    """USER_MESSAGE event type exists and has correct value."""
    assert EventType.USER_MESSAGE.value == "user_message"


def test_sync_and_async_modes_exist():
    """Both SYNC and ASYNC modes are present."""
    assert SendMessageMode.SYNC.value == "sync"
    assert SendMessageMode.ASYNC.value == "async"


def test_a2a_event_user_message():
    """A2AEvent can be constructed with USER_MESSAGE type."""
    event = A2AEvent(
        event_id="evt-user-001",
        event_type=EventType.USER_MESSAGE,
        source="web-console",
        content={
            "task": "Hello agent",
            "session_id": "session-123"
        }
    )
    assert event.event_type == EventType.USER_MESSAGE
    assert event.content["task"] == "Hello agent"
    assert event.content["session_id"] == "session-123"
