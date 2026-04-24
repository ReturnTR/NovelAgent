"""Pytest configuration for web console tests"""
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from web_console.backend.config import BASE_DIR


@pytest.fixture
def project_root():
    """Project root directory"""
    return PROJECT_ROOT


@pytest.fixture
def web_console_root():
    """Web console backend directory"""
    return BASE_DIR / "web_console"


@pytest.fixture
def sessions_dir(web_console_root):
    """Sessions directory for tests"""
    sessions = web_console_root / "backend" / "sessions"
    sessions.mkdir(exist_ok=True, parents=True)
    return sessions


@pytest.fixture
def temp_session_dir(tmp_path):
    """Temporary session directory for isolated tests

    SessionService creates sessions at: base_dir / "web_console" / "backend" / "sessions"
    So we need to provide a structure where the parent exists.
    """
    # Create the full path that SessionService expects
    session_dir = tmp_path / "web_console" / "backend" / "sessions"
    session_dir.mkdir(parents=True)
    return tmp_path  # Return parent, SessionService will append the rest
