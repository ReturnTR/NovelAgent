"""Tests for config module"""
import pytest
from web_console.backend.config import (
    BASE_DIR,
    PROJECT_ROOT,
    AGENT_MAIN_FILES,
    PORT_BASE,
    MAX_PORT,
    SESSION_DIR,
    CORE_ROOT,
    AGENTS_ROOT,
    ensure_python_path,
)


class TestConfig:
    """Test configuration module"""

    def test_base_dir_is_path(self):
        """BASE_DIR should be a Path object"""
        from pathlib import Path
        assert isinstance(BASE_DIR, Path)

    def test_project_root_equals_base_dir(self):
        """PROJECT_ROOT should equal BASE_DIR"""
        assert PROJECT_ROOT == BASE_DIR

    def test_agent_main_files_contains_supervisor(self):
        """AGENT_MAIN_FILES should contain supervisor entry"""
        assert "supervisor" in AGENT_MAIN_FILES
        assert AGENT_MAIN_FILES["supervisor"] == "agents/supervisor_agent/main.py"

    def test_agent_main_files_contains_character(self):
        """AGENT_MAIN_FILES should contain character entry"""
        assert "character" in AGENT_MAIN_FILES
        assert AGENT_MAIN_FILES["character"] == "agents/character_agent/main.py"

    def test_port_base_is_8001(self):
        """PORT_BASE should be 8001"""
        assert PORT_BASE == 8001

    def test_max_port_is_9000(self):
        """MAX_PORT should be 9000"""
        assert MAX_PORT == 9000

    def test_session_dir_path(self):
        """SESSION_DIR should point to web_console/backend/sessions"""
        assert SESSION_DIR == BASE_DIR / "web_console" / "backend" / "sessions"

    def test_core_root_path(self):
        """CORE_ROOT should point to core directory"""
        assert CORE_ROOT == PROJECT_ROOT / "core"

    def test_agents_root_path(self):
        """AGENTS_ROOT should point to agents directory"""
        assert AGENTS_ROOT == PROJECT_ROOT / "agents"

    def test_ensure_python_path_adds_paths(self):
        """ensure_python_path should add paths to sys.path"""
        import sys
        original_paths = set(sys.path)

        ensure_python_path()

        assert str(PROJECT_ROOT) in sys.path
        assert str(CORE_ROOT) in sys.path
        assert str(AGENTS_ROOT) in sys.path
