"""Tests for config module"""
import pytest
from web_console.backend.config import (
    BASE_DIR,
    PROJECT_ROOT,
    FIXED_AGENTS,
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

    def test_fixed_agents_is_list(self):
        """FIXED_AGENTS should be a list"""
        assert isinstance(FIXED_AGENTS, list)

    def test_fixed_agents_has_supervisor(self):
        """FIXED_AGENTS should have supervisor entry"""
        agent_ids = [a["agent_id"] for a in FIXED_AGENTS]
        assert "supervisor-001" in agent_ids

    def test_fixed_agents_has_character(self):
        """FIXED_AGENTS should have character entry"""
        agent_ids = [a["agent_id"] for a in FIXED_AGENTS]
        assert "character-001" in agent_ids

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