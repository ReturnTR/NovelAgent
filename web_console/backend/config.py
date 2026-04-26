"""Shared configuration for web console backend"""
import os
import json
import threading
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
PROJECT_ROOT = BASE_DIR

# Agent config file
AGENTS_CONFIG_FILE = Path(__file__).resolve().parent / "agents_config.json"


def load_agents_config() -> list:
    """Load agent configurations from JSON file"""
    if AGENTS_CONFIG_FILE.exists():
        with open(AGENTS_CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []


def save_agents_config(agents: list):
    """Save agent configurations to JSON file"""
    with open(AGENTS_CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(agents, f, ensure_ascii=False, indent=2)


class AgentState:
    """Thread-safe agent runtime state manager"""

    def __init__(self):
        self._lock = threading.Lock()
        self._agents = load_agents_config()
        # Initialize runtime fields
        for agent in self._agents:
            agent.setdefault("pid", None)
            agent.setdefault("status", "inactive")

    def get_all(self) -> list:
        with self._lock:
            return self._agents.copy()

    def get_by_id(self, agent_id: str) -> dict | None:
        with self._lock:
            for agent in self._agents:
                if agent["agent_id"] == agent_id:
                    return agent.copy()
            return None

    def update(self, agent_id: str, updates: dict):
        with self._lock:
            for agent in self._agents:
                if agent["agent_id"] == agent_id:
                    agent.update(updates)
                    break
            save_agents_config(self._agents)

    def get_pid(self, agent_id: str) -> int | None:
        agent = self.get_by_id(agent_id)
        return agent.get("pid") if agent else None

    def get_status(self, agent_id: str) -> str:
        agent = self.get_by_id(agent_id)
        return agent.get("status", "inactive") if agent else "inactive"

    def set_active(self, agent_id: str, pid: int, port: int):
        self.update(agent_id, {"pid": pid, "port": port, "status": "active"})

    def set_inactive(self, agent_id: str):
        self.update(agent_id, {"pid": None, "status": "inactive"})


# Global agent state instance
agent_state = AgentState()

# Load fixed agents from config file (static config only)
FIXED_AGENTS = load_agents_config()

# Port configuration
PORT_BASE = 8001
MAX_PORT = 9000

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
