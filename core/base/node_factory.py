"""
LangGraph 节点工厂

创建标准的三节点结构：
- model: LLM 调用节点
- tool_node: 工具执行节点
"""

from typing import Dict, List, Any, Callable, Annotated, TypedDict, TYPE_CHECKING

from langgraph.graph.message import add_messages
from langchain_core.messages import (
    BaseMessage,
    ToolMessage,
)
from .context_manager import ContextManager

if TYPE_CHECKING:
    from langchain_core.tools import BaseTool


class AgentState(TypedDict):
    """
    LangGraph 状态定义

    - messages: 对话消息列表
    - current_task: 当前任务描述
    - context: 任务上下文数据
    - received_events: 接收到的 A2A 事件列表
    """
    messages: Annotated[List[BaseMessage], add_messages]
    current_task: str
    context: Dict[str, Any]
    received_events: List[Dict[str, Any]]


class NodeFactory:
    """
    LangGraph 节点工厂
    """

    @staticmethod
    def create_model_node(
        llm: Any,
        skills: List,
        system_prompt: str
    ) -> Callable:
        """
        创建模型节点

        职责：
        1. 加载 system prompt
        2. 注入可用技能列表
        3. 注入收到的 A2A 事件
        4. 调用 LLM 生成响应

        Args:
            llm: LLM 实例
            skills: 可用技能列表
            system_prompt: system prompt 内容

        Returns:
            模型节点函数
        """

        def model_node(state: AgentState) -> AgentState:

            # 构建消息：system prompt + skills + A2A events
            messages = ContextManager.build_system_message(
                system_prompt,
                skills,
                state.get("received_events")
            )
            messages.extend(state["messages"])

            # 检查工具状态
            has_tool_results = ContextManager.has_tool_results(messages)
            has_valid_tc = ContextManager.has_valid_tool_calls(messages)

            # 工具结果已返回，没有新 tool_calls → 生成最终回复
            if has_tool_results and not has_valid_tc:
                pass  # 继续调用 LLM

            # 有工具结果但 LLM 又生成了 tool_calls（没理解结果）→ 让 LLM 重新处理
            elif has_tool_results and has_valid_tc:
                pass  # 继续调用 LLM 生成新回复

            # 没有工具结果，有 tool_calls → 生成工具调用（正常流程）
            elif not has_tool_results and has_valid_tc:
                pass  # 继续调用 LLM 生成 tool_calls

            # 过滤空消息
            messages = ContextManager.filter_empty_messages(messages)

            if not messages:
                return {
                    "messages": [],
                    "current_task": state["current_task"],
                    "context": state.get("context", {}),
                    "received_events": []
                }

            response = llm.invoke(messages)

            # Extract message from ChatResult
            generation = response.generations[0] if response.generations else None
            message = generation.message if generation else None

            return {
                "messages": [message] if message else [],
                "current_task": state["current_task"],
                "context": state.get("context", {}),
                "received_events": []
            }

        return model_node

    @staticmethod
    def create_tool_node(tools: List["BaseTool"]) -> Callable:
        """
        创建工具执行节点

        遍历 last_message 中的 tool_calls，执行对应工具

        Args:
            tools: 可用工具列表

        Returns:
            工具节点函数
        """

        def tool_node(state: AgentState) -> AgentState:
            import json
            last_message = state["messages"][-1]

            if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
                return state

            tool_messages = []
            for tool_call in last_message.tool_calls:
                if isinstance(tool_call, dict):
                    tool_name = tool_call.get("name")
                    tool_args = tool_call.get("args", tool_call.get("arguments", {}))
                    tool_call_id = tool_call.get("id")
                else:
                    tool_name = tool_call.name
                    tool_args = tool_call.args
                    tool_call_id = tool_call.id

                for tool in tools:
                    if tool.name == tool_name:
                        try:
                            result = tool.invoke(tool_args)
                        except Exception as e:
                            result = {"error": str(e)}

                        tool_messages.append(
                            ToolMessage(
                                content=json.dumps(result, ensure_ascii=False),
                                tool_call_id=tool_call_id
                            )
                        )
                        break

            return {
                "messages": tool_messages,
                "current_task": state["current_task"],
                "context": state.get("context", {}),
                "received_events": state.get("received_events", [])
            }

        return tool_node

    @staticmethod
    def create_tools_condition(tools: List["BaseTool"]) -> Callable:
        """
        创建工具调用条件判断函数

        决定下一步走 tool_node 还是 end

        Args:
            tools: 可用工具列表

        Returns:
            条件判断函数
        """

        def tools_condition(state: AgentState) -> str:
            if not tools:
                return "end"

            last_message = state["messages"][-1] if state["messages"] else None
            tc = getattr(last_message, "tool_calls", None) if last_message else None

            if not tc or not last_message:
                return "end"

            # 收集已有 tool results 的 id
            executed_ids = set()
            for msg in state["messages"]:
                if isinstance(msg, ToolMessage) and msg.tool_call_id:
                    executed_ids.add(msg.tool_call_id)

            # 检查是否有未执行的 tool_calls
            has_unexecuted_tc = False
            for t in last_message.tool_calls:
                tc_id = t.get("id") if isinstance(t, dict) else getattr(t, "id", None)
                if tc_id and tc_id not in executed_ids:
                    has_unexecuted_tc = True
                    break

            if has_unexecuted_tc:
                return "tool_node"
            return "end"

        return tools_condition
