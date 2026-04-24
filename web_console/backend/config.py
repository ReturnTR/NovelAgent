"""Shared configuration for web console backend"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
PROJECT_ROOT = BASE_DIR

# Agent entry points
AGENT_MAIN_FILES = {
    "supervisor": "agents/supervisor_agent/main.py",
    "character": "agents/character_agent/main.py",
}

# Port configuration
PORT_BASE = 8001
MAX_PORT = 9000

# Session directory
SESSION_DIR = BASE_DIR / "web_console" / "backend" / "sessions"

# Core module paths
CORE_ROOT = PROJECT_ROOT / "core"
AGENTS_ROOT = PROJECT_ROOT / "agents"

# Ensure Python path includes project root
def ensure_python_path():
    import sys
    for path in [str(PROJECT_ROOT), str(CORE_ROOT), str(AGENTS_ROOT)]:
        if path not in sys.path:
            sys.path.insert(0, path)

ensure_python_path()