"""
日志检查器

用于断言日志内容是否符合预期
"""

import re
from typing import List, Dict, Any, Optional


class LogChecker:
    """
    日志断言工具
    """

    def __init__(self, log_content: str):
        self.log = log_content

    def assert_contains(self, pattern: str, msg: str = ""):
        """
        断言日志包含指定内容

        Args:
            pattern: 要查找的字符串或正则表达式
            msg: 断言失败时的提示信息
        """
        if isinstance(pattern, str):
            found = pattern in self.log
        else:
            found = bool(re.search(pattern, self.log))

        assert found, f"Log does not contain: {pattern}\n{msg}\nLog preview:\n{self.log[:500]}"

    def assert_not_contains(self, pattern: str, msg: str = ""):
        """断言日志不包含指定内容"""
        found = pattern in self.log
        assert not found, f"Log contains unexpected: {pattern}\n{msg}"

    def assert_llm_request(self, msg_count: int = None):
        """断言包含 LLM 请求日志"""
        self.assert_contains("[LLM_REQUEST]", "Should have LLM request log")
        if msg_count is not None:
            pattern = f"messages={msg_count}"
            self.assert_contains(pattern, f"Should have {msg_count} messages in LLM request")

    def assert_llm_response(self, has_reasoning: bool = None, has_tool_calls: bool = None):
        """断言包含 LLM 响应日志"""
        self.assert_contains("[LLM_RESPONSE]", "Should have LLM response log")
        if has_reasoning is True:
            self.assert_contains("reasoning=True", "LLM response should have reasoning")
        if has_tool_calls is True:
            self.assert_contains("tool_calls=True", "LLM response should have tool_calls")

    def assert_tool_call(self, tool_name: str = None, args: dict = None):
        """
        断言包含工具调用日志

        Args:
            tool_name: 工具名称（如 "execute_bash"）
            args: 期望的工具参数（会转换为字符串检查）
        """
        self.assert_contains("[TOOL_CALL]", "Should have tool call log")
        if tool_name:
            self.assert_contains(f"[TOOL_CALL] {tool_name}", f"Should call tool: {tool_name}")
        if args:
            args_str = str(args)
            self.assert_contains(args_str, f"Tool args should contain: {args}")

    def assert_tool_result(self, tool_name: str = None, success: bool = True):
        """断言包含工具结果日志"""
        status = "OK" if success else "FAIL"
        self.assert_contains(f"[TOOL_RESULT:{status}]", f"Should have tool result: {status}")
        if tool_name:
            self.assert_contains(f"[TOOL_RESULT:{status}] {tool_name}", f"Should have result for: {tool_name}")

    def assert_reasoning_content(self, content: str = None):
        """
        断言包含 reasoning_content 日志

        Args:
            content: 期望的 reasoning 内容（子串）
        """
        self.assert_contains("[REASONING]", "Should have reasoning log")
        if content:
            self.assert_contains(content, f"Reasoning should contain: {content}")

    def assert_reasoning_missing(self):
        """断言存在 reasoning_content 缺失的警告"""
        self.assert_contains("[REASONING_MISSING]", "Should warn about missing reasoning_content")

    def get_matching_lines(self, pattern: str) -> List[str]:
        """获取所有匹配的行"""
        return [line for line in self.log.split('\n') if pattern in line]


class SessionChecker:
    """
    Session 断言工具
    """

    def __init__(self, messages: List[Dict[str, Any]]):
        self.messages = messages

    def assert_message_count(self, count: int):
        """断言消息数量"""
        actual = len(self.messages)
        assert actual >= count, f"Expected at least {count} messages, got {actual}"

    def assert_has_tool_call(self, tool_name: str = None):
        """断言包含工具调用"""
        tool_calls = [m for m in self.messages if m.get("tool_calls")]
        assert len(tool_calls) > 0, "Should have at least one tool call message"

        if tool_name:
            found = any(
                any(tc.get("name") == tool_name for tc in m.get("tool_calls", []))
                for m in tool_calls
            )
            assert found, f"Should have tool call for: {tool_name}"

    def assert_has_reasoning(self):
        """断言包含 reasoning_content"""
        reasoning = [m for m in self.messages if m.get("reasoning_content")]
        assert len(reasoning) > 0, "Should have at least one message with reasoning_content"

    def assert_has_final_response(self):
        """断言存在最终回复（非 tool_call、非 reasoning）"""
        # 找最后一个 role=assistant 且 content 非空的
        assistant_with_content = [
            m for m in self.messages
            if m.get("role") == "assistant" and m.get("content")
        ]
        assert len(assistant_with_content) > 0, "Should have final assistant response"

    def assert_final_response(self, contains: str = None, not_contains: str = None):
        """
        断言最终回复内容

        Args:
            contains: 应该包含的子串
            not_contains: 不应该包含的子串
        """
        # 获取最后一个 assistant 的 content
        final_content = ""
        for m in reversed(self.messages):
            if m.get("role") == "assistant" and m.get("content"):
                final_content = m.get("content", "")
                break

        assert final_content, "Should have final content"

        if contains:
            assert contains in final_content, f"Final content should contain: {contains}\nGot: {final_content[:200]}"
        if not_contains:
            assert not_contains not in final_content, f"Final content should not contain: {not_contains}"

    def assert_tool_result(self, tool_name: str = None, success: bool = None):
        """断言包含工具结果消息"""
        tool_results = [m for m in self.messages if m.get("role") == "tool"]
        assert len(tool_results) > 0, "Should have tool result messages"

        if success is not None:
            for m in tool_results:
                content = m.get("content", "")
                if success:
                    assert '"success": true' in content or '"success": true' in content.lower()
                else:
                    assert '"success": false' in content or '"success": false' in content.lower()

    def get_last_user_message(self) -> str:
        """获取最后一条用户消息"""
        for m in reversed(self.messages):
            if m.get("role") == "user":
                return m.get("content", "")
        return ""

    def get_final_assistant_content(self) -> str:
        """获取最终 assistant 回复"""
        for m in reversed(self.messages):
            if m.get("role") == "assistant" and m.get("content"):
                return m.get("content", "")
        return ""
