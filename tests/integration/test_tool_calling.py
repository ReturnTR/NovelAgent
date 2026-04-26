"""
工具调用集成测试

测试真实的工具调用流程，包括日志和 Session 验证
"""

import pytest


@pytest.mark.asyncio
async def test_execute_bash_tool(agent_runner, session_checker):
    """
    测试 execute_bash 工具调用

    验证：
    1. LLM 能够正确调用 execute_bash 工具
    2. 事件包含正确的 tool_call 和 tool_result
    3. Session 记录包含完整的工具调用流程
    """
    session_id = "test-bash-ls"

    # 发送请求
    events = await agent_runner.chat_async(
        "当前工作空间有哪些文件？请用 ls 命令查看",
        session_id=session_id
    )

    from tests.utils.agent_runner import ChatResult
    result = ChatResult(events)

    # 1. 验证事件中有工具调用
    assert result.has_tool_call, f"Should have tool call, events: {[e.get('type') for e in events]}"
    assert result.first_tool_name == "execute_bash", f"Should call execute_bash, got {result.first_tool_name}"

    # 2. 验证工具参数
    args = result.first_tool_args
    assert "ls" in args.get("command", ""), f"Command should contain ls, got: {args}"

    # 3. 验证有工具结果
    assert len(result.tool_results) > 0, "Should have tool results"

    # 4. 验证 Session
    session = session_checker(session_id)
    session.assert_has_tool_call("execute_bash")
    session.assert_has_reasoning()
    session.assert_has_final_response()


@pytest.mark.asyncio
async def test_tool_call_without_args(agent_runner, session_checker):
    """
    测试不带参数的简单工具调用

    验证工具可以无参数调用
    """
    session_id = "test-simple-command"

    # 发送请求
    events = await agent_runner.chat_async(
        "执行 pwd 命令查看当前目录",
        session_id=session_id
    )

    from tests.utils.agent_runner import ChatResult
    result = ChatResult(events)

    # 验证工具调用
    assert result.has_tool_call, f"Should have tool call, events: {[e.get('type') for e in events]}"

    # 验证 Session
    session = session_checker(session_id)
    session.assert_has_tool_call()
    session.assert_has_reasoning()
