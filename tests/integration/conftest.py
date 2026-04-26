"""
Integration test configuration and fixtures.

这些 fixtures 用于需要真实 Agent 的集成测试。
"""
import sys
import os
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 测试 Agent 目录 - 使用 supervisor_agent（已验证可工作）
TEST_AGENT_DIR = str(PROJECT_ROOT / "agents" / "supervisor_agent")


@pytest.fixture(scope="session")
def test_agent_dir():
    """测试 Agent 目录"""
    return TEST_AGENT_DIR


@pytest.fixture(scope="function")
def agent_runner(test_agent_dir, request):
    """
    每个测试函数独立的 Agent Runner

    Args:
        test_agent_dir: Agent 目录
        request: pytest request 对象，用于获取测试名称

    Yields:
        AgentRunner 实例
    """
    from tests.utils.agent_runner import AgentRunner

    # API 凭证 - 使用硬编码的正确值，不依赖 os.getenv（会被 isolated_env 污染）
    api_key = "sk-YLiZarg7OKEjYeqMqiTr9dQ1gMlNbKUOuqBYkkT8dG5CXI7L"
    api_base = "https://api.moonshot.cn/v1"

    # 创建 Runner（会自动创建日志文件）
    runner = AgentRunner.create_for_test(
        test_name=request.node.name,
        agent_dir=test_agent_dir,
        port=9999,
        api_key=api_key,
        api_base=api_base
    )

    # 启动 Agent
    runner.start()

    yield runner

    # 清理
    runner.stop()


@pytest.fixture
def log_checker(agent_runner):
    """日志检查器 fixture"""
    from tests.utils.checkers import LogChecker

    def _create_checker():
        log_content = agent_runner.get_log_content()
        return LogChecker(log_content)

    return _create_checker


@pytest.fixture
def session_checker(agent_runner):
    """Session 检查器 fixture"""
    from tests.utils.checkers import SessionChecker

    def _create_checker(session_id: str):
        history = agent_runner.get_session_history(session_id)
        return SessionChecker(history)

    return _create_checker


@pytest.fixture
def chat_result(agent_runner):
    """
    发送聊天请求并返回 ChatResult

    用法:
        result = chat_result("你好", "my-session")
        assert result.has_tool_call
        assert "hello" in result.final_content
    """
    from tests.utils.agent_runner import ChatResult

    def _chat(task: str, session_id: str = None):
        events = agent_runner.chat(task, session_id)
        return ChatResult(events)

    return _chat