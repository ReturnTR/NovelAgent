"""Tests for session_service module"""
import pytest
from unittest.mock import MagicMock

from web_console.backend.session_service import SessionService


class TestSessionService:
    """Test SessionService delegation to core SessionManager"""

    @pytest.fixture
    def mock_logger(self):
        """Mock logger"""
        logger = MagicMock()
        return logger

    @pytest.fixture
    def session_service(self, temp_session_dir, mock_logger):
        """Create SessionService with temp directory"""
        from web_console.backend.config import PROJECT_ROOT
        import sys
        sys.path.insert(0, str(PROJECT_ROOT))

        # SessionService expects base_dir, it will create sessions under base_dir/web_console/backend/sessions
        # temp_session_dir is already set up with that structure
        service = SessionService(temp_session_dir, mock_logger)
        return service

    def test_list_sessions_returns_list(self, session_service):
        """list_sessions should return a list"""
        result = session_service.list_sessions()
        assert isinstance(result, list)

    def test_create_session_returns_string(self, session_service):
        """create_session should return a session_id string"""
        session_id = session_service.create_session("supervisor", "Test Agent")
        assert isinstance(session_id, str)
        assert len(session_id) > 0

    def test_get_session_returns_none_for_nonexistent(self, session_service):
        """get_session should return None for nonexistent session"""
        result = session_service.get_session("nonexistent-id")
        assert result is None

    def test_get_session_by_id_returns_none_for_nonexistent(self, session_service):
        """get_session_by_id should return None for nonexistent session"""
        result = session_service.get_session_by_id("nonexistent-id")
        assert result is None

    def test_append_message_creates_file(self, session_service):
        """append_message should create session file"""
        session_id = session_service.create_session("supervisor", "Test Agent")
        session_service.append_message(session_id, "user", "Hello")

        messages = session_service.get_session_messages(session_id)
        assert len(messages) >= 1

    def test_append_message_with_reasoning(self, session_service):
        """append_message should handle reasoning_content"""
        session_id = session_service.create_session("supervisor", "Test Agent")
        session_service.append_message(session_id, "user", "Hello", reasoning_content="Thinking...")

        # Should not raise
        messages = session_service.get_session_messages(session_id)

    def test_delete_session_removes_session(self, session_service):
        """delete_session should remove the session"""
        session_id = session_service.create_session("supervisor", "Test Agent")
        session_service.delete_session(session_id)

        result = session_service.get_session_by_id(session_id)
        assert result is None

    def test_get_agent_id_returns_none_for_nonexistent(self, session_service):
        """get_agent_id should return None for nonexistent session"""
        result = session_service.get_agent_id("nonexistent-id")
        assert result is None

    def test_get_agent_id_returns_id_for_existing(self, session_service):
        """get_agent_id should return agent_id for existing session"""
        session_id = session_service.create_session("supervisor", "Test Agent")
        agent_id = session_service.get_agent_id(session_id)
        assert agent_id is not None
        assert isinstance(agent_id, str)

    def test_sync_sessions_status(self, session_service):
        """sync_sessions_status should not raise"""
        session_id = session_service.create_session("supervisor", "Test Agent")
        # Should not raise with empty list
        session_service.sync_sessions_status([])

    def test_load_index_and_save_index(self, temp_session_dir, mock_logger):
        """_load_index and _save_index should work"""
        from web_console.backend.config import PROJECT_ROOT
        import sys
        sys.path.insert(0, str(PROJECT_ROOT))

        service = SessionService(temp_session_dir, mock_logger)

        # Load should return structure with sessions
        index = service._load_index()
        assert "sessions" in index

        # Save and load should persist (note: _load_index adds port/pid fields)
        test_data = {"sessions": [{"test": "data"}]}
        service._save_index(test_data)

        loaded = service._load_index()
        # Core SessionManager adds port/pid to each session
        assert loaded["sessions"][0].get("test") == "data"
