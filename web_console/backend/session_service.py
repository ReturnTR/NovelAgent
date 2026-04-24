"""Session service - delegates to core.session.manager"""
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional

from web_console.backend.config import PROJECT_ROOT, SESSION_DIR

# Ensure core module is importable
sys.path.insert(0, str(PROJECT_ROOT))
from core.session.manager import SessionManager as CoreSessionManager


class SessionService:
    """Session service - thin wrapper around core SessionManager"""

    def __init__(self, base_dir: Path, logger):
        self.base_dir = base_dir
        session_dir = base_dir / "web_console" / "backend" / "sessions"
        self._manager = CoreSessionManager(base_dir=str(session_dir))
        self._manager.migrate_sessions()
        self._setup_logger(logger)

    def _setup_logger(self, logger):
        """Set up logging"""
        import logging
        self.logger = logger

    def list_sessions(self, agent_type: str = None, status: str = None) -> List[Dict[str, Any]]:
        """List all sessions, optionally filtered"""
        return self._manager.list_sessions(agent_type=agent_type, status=status)

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session by ID"""
        return self._manager.get_session(session_id)

    def get_session_by_id(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session by ID (alias)"""
        return self._manager.get_session(session_id)

    def create_session(self, agent_type: str, agent_name: str) -> str:
        """Create new session"""
        return self._manager.create_session(agent_type, agent_name)

    def update_session_port_pid(self, session_id: str, port: int, pid: int):
        """Update session port and pid"""
        self._manager.update_session_port_pid(session_id, port, pid)

    def update_session_status(self, session_id: str, status: str):
        """Update session status"""
        self._manager.update_session_status(session_id, status)

    def update_session_agent_name(self, session_id: str, name: str):
        """Update session agent name"""
        self._manager.update_session_agent_name(session_id, name)

    def get_session_messages(self, session_id: str) -> List[Dict[str, Any]]:
        """Get session message history"""
        return self._manager.get_session_messages(session_id)

    def append_message(self, session_id: str, role: str, content: str,
                       tool_calls: Optional[List] = None,
                       tool_results: Optional[List] = None,
                       reasoning_content: Optional[str] = None,
                       tool_call_id: Optional[str] = None):
        """Append message to session"""
        self._manager.append_message(session_id, role, content, tool_calls, tool_results, tool_call_id, reasoning_content)

    def _load_index(self) -> Dict[str, Any]:
        """Load index (delegated for process_manager)"""
        return self._manager._load_index()

    def _save_index(self, index_data: Dict[str, Any]):
        """Save index (delegated for process_manager)"""
        self._manager._save_index(index_data)

    def append_agent_message(self, session_id: str, role: str, content: str,
                            source_agent_id: str = "", target_agent_id: str = "",
                            event_id: Optional[str] = None, task_id: Optional[str] = None):
        """Append agent-to-agent message"""
        self._manager.append_agent_message(session_id, role, content, source_agent_id,
                                           target_agent_id, event_id, task_id)

    def delete_message_by_index(self, session_id: str, message_index: int):
        """Delete message by index"""
        self._manager.delete_message_by_index(session_id, message_index)

    def delete_session(self, session_id: str):
        """Delete session"""
        self._manager.delete_session(session_id)

    def sync_sessions_status(self, running_pids: List[int]):
        """Sync session status with running PIDs"""
        self._manager.sync_sessions_status(running_pids)

    def get_agent_id(self, session_id: str) -> Optional[str]:
        """Get agent ID for session"""
        return self._manager.get_agent_id(session_id)