"""
Global pytest configuration and shared fixtures.
"""
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def assert_equal(actual, expected, context=""):
    if actual != expected:
        msg = "Assertion failed"
        if context:
            msg += f"\n  Context: {context}"
        msg += f"\n  Expected: {repr(expected)}"
        msg += f"\n  Got: {repr(actual)}"
        raise AssertionError(msg)


@pytest.fixture(autouse=True)
def isolated_env(monkeypatch):
    for var in ["OPENAI_API_KEY", "OPENAI_API_BASE", "AGENT_PORT", "AGENT_SESSION_ID",
                "AGENT_NAME", "AGENT_ID", "AGENT_DIR", "PROJECT_ROOT"]:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("TESTING", "1")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-for-unit-tests")
    monkeypatch.setenv("OPENAI_API_BASE", "https://api.test.com/v1")
    monkeypatch.setenv("AGENT_PORT", "9999")
    monkeypatch.setenv("AGENT_SESSION_ID", "test-session-001")
    monkeypatch.setenv("AGENT_NAME", "TestAgent")
    monkeypatch.setenv("AGENT_ID", "test-agent-001")
    monkeypatch.setenv("AGENT_DIR", str(PROJECT_ROOT / "agents" / "supervisor_agent"))
    monkeypatch.setenv("PROJECT_ROOT", str(PROJECT_ROOT))
    yield


@pytest.fixture
def isolated_session_dir(tmp_path):
    session_root = tmp_path / "sessions"
    session_root.mkdir()
    yield str(session_root)
