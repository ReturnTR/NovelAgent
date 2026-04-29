"""
BaseAgent - Agent 核心基类

核心职责：
1. 配置访问
2. 技能管理
3. LLM 和 LangGraph 核心
4. 工具管理

网络通信由 A2AEventServer 负责
"""

from abc import ABC
from typing import Dict, List, Any, Optional
from pathlib import Path
import json
import os
import re
import logging
from dotenv import load_dotenv

load_dotenv()

# 日志配置
DEBUG_MODE = os.getenv("AGENT_DEBUG", "false").lower() == "true"
DEBUG_TOOL = os.getenv("AGENT_DEBUG_TOOL", "false").lower() == "true" or DEBUG_MODE

if DEBUG_TOOL:
    logging.basicConfig(level=logging.DEBUG, format='[%(asctime)s] %(name)s - %(levelname)s - %(message)s', datefmt='%H:%M:%S')

logger = logging.getLogger(__name__)

from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, ToolMessage
from langchain_core.tools import BaseTool

from core.base.llm.openai_provider import OpenAIReasoningProvider
from core.base.skill_manager import SkillManager, SkillMetadata
from core.base.node_factory import AgentState
from core.base.tool_manager import ToolManager
from core.base.context_manager import ContextManager


class BaseAgent(ABC):
    """
    Agent 核心基类

    专注于核心能力：
    - 配置访问
    - 技能管理
    - LLM 调用和 LangGraph 执行
    - 工具管理
    - 记忆管理（待添加）
    """

    # 默认配置值
    default_model_id = "gpt-4"
    default_temperature = 0.7
    default_max_tokens = 4000

    def __init__(self, config: Dict[str, Any], agent_dir: Path):
        """
        初始化 BaseAgent

        Args:
            config: Agent 配置字典
            agent_dir: Agent 配置目录
        """
        self.config = config
        self.agent_dir = agent_dir
        os.environ["AGENT_DIR"] = str(agent_dir.resolve())

        # step 1: 加载基础工具
        self.tools = ToolManager.load_all_tools(self.config, self.agent_dir)

        # step 2: 加载技能
        skills_dir = self.agent_dir / "skills"
        self.skills = SkillManager.load_all_skills(skills_dir)

        # step 3: 加载 system prompt
        self.system_prompt = self.load_prompt()

        # step 4: 初始化 LLM
        self.llm = self._init_llm()

        # step 5: 构建 LangGraph
        self.graph = self._build_graph()

    def add_tools_and_restart(self, tools):
        """注入 A2AEventServer 的工具并刷新初始化"""
        self.tools = self.tools + tools
        self.llm = self._init_llm()
        self.graph = self._build_graph()
        print("[BaseAgent] A2A Server Tools injected")

    def _init_llm(self) -> OpenAIReasoningProvider:
        """初始化 LLM"""
        model_config = self.config.get("model", {})

        api_key = os.getenv("OPENAI_API_KEY")
        api_base = os.getenv("OPENAI_API_BASE")
        model_id = model_config.get("model_id", self.default_model_id)
        temperature = model_config.get("temperature", self.default_temperature)
        max_tokens = model_config.get("max_tokens", self.default_max_tokens)

        # 使用已有的 tools（包括注入的 A2A tools）
        tools_to_use = getattr(self, 'tools', None) or self._base_tools

        llm = OpenAIReasoningProvider(
            api_key=api_key,
            base_url=api_base,
            model=model_id,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools_to_use if tools_to_use else None,
        )

        return llm

    def _build_graph(self) -> StateGraph:
        """构建标准Tool-Use-Loop"""
        from core.base.node_factory import NodeFactory
        from langgraph.graph import END

        tools_for_graph = self.tools if hasattr(self, 'tools') and self.tools else self._base_tools

        workflow = StateGraph(AgentState)

        model_node = NodeFactory.create_model_node(
            self.llm,
            self.skills,
            self.system_prompt
        )
        tool_node = NodeFactory.create_tool_node(tools_for_graph)
        tools_condition = NodeFactory.create_tools_condition(tools_for_graph)

        workflow.add_node("model", model_node)
        workflow.add_node("tool_node", tool_node)

        workflow.set_entry_point("model")

        workflow.add_conditional_edges(
            "model",
            tools_condition,
            {
                "tool_node": "tool_node",
                "end": END
            }
        )

        workflow.add_edge("tool_node", "model")

        return workflow.compile()

    def load_prompt(self) -> str:
        """
        加载 prompt 文件，支持 {{filename.md}} 格式的 include 指令
        递归解析所有引用的 md 文件（最多5层深度）
        Returns:
            prompt 内容
        """
        prompt_file = self.agent_dir / "prompts" / "system_prompt.md"
        if not prompt_file.exists():
            raise FileNotFoundError(f"Prompt file not found: {prompt_file}")

        with open(prompt_file, 'r', encoding='utf-8') as f:
            content = f.read()

        return self._resolve_includes(content, prompt_file.parent)

    def _resolve_includes(self, content: str, prompts_dir: Path, depth: int = 0) -> str:
        """
        递归解析 include 指令
        格式：{{filename.md}} -> 替换为对应文件内容
        """
        if depth > 5:
            raise ValueError("Include directive nesting too deep (>5)")

        include_pattern = re.compile(r'\{\{([^}]+\.md)\}\}')

        while True:
            match = include_pattern.search(content)
            if not match:
                break

            include_file = match.group(1)
            included_path = prompts_dir / include_file

            if not included_path.exists():
                raise FileNotFoundError(f"Include file not found: {included_path}")

            with open(included_path, 'r', encoding='utf-8') as f:
                included_content = f.read()

            # 递归解析被包含的文件
            included_content = self._resolve_includes(included_content, prompts_dir, depth + 1)

            # 替换 include 指令
            content = content.replace(match.group(0), included_content)

        return content

    async def process_task_stream(self, task: str, context: Optional[Dict] = None):
        """
        处理任务（流式模式）

        使用 LangGraph self.graph 执行
        """
        messages = []
        received_events_list = []
        if context and isinstance(context, list):
            messages, _ = ContextManager.format_history_to_messages(context)

        messages.append(HumanMessage(content=task))

        initial_state: AgentState = {
            "messages": messages,
            "current_task": task,
            "context": context or {},
            "received_events": received_events_list
        }

        # 使用 LangGraph stream
        async for event in self.graph.astream(initial_state):
            node_name = list(event.keys())[0] if event else None
            node_output = event.get(node_name, {}) if node_name else {}

            if node_name == "model":
                output_messages = node_output.get("messages", [])
                for msg in output_messages:
                    if isinstance(msg, AIMessage):
                        if hasattr(msg, "additional_kwargs"):
                            rc = msg.additional_kwargs.get("reasoning_content", "")
                            if rc:
                                yield {"type": "reasoning", "content": rc}

                        if hasattr(msg, "tool_calls") and msg.tool_calls:
                            for tc in msg.tool_calls:
                                if isinstance(tc, dict):
                                    yield {
                                        "type": "tool_call",
                                        "tool_calls": [{
                                            "id": tc.get("id"),
                                            "name": tc.get("name"),
                                            "arguments": tc.get("args", tc.get("arguments", {}))
                                        }]
                                    }
                                else:
                                    yield {"type": "tool_call", "tool_calls": [tc]}
                        elif msg.content:
                            yield {"type": "assistant", "content": msg.content}

            elif node_name == "tool_node":
                output_messages = node_output.get("messages", [])
                for msg in output_messages:
                    if isinstance(msg, ToolMessage):
                        if DEBUG_TOOL:
                            try:
                                content = json.loads(msg.content)
                                success = content.get("success", False)
                            except:
                                success = False
                            status = "OK" if success else "FAIL"
                            logger.debug(f"[TOOL_RESULT:{status}] tool_call_id={msg.tool_call_id}")

                        yield {
                            "type": "tool_result",
                            "tool_call_id": msg.tool_call_id,
                            "content": msg.content
                        }

        yield {"type": "done"}
