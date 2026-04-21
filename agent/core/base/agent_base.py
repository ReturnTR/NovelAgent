"""
BaseAgent - 所有 Agent 的基类

基于 LangGraph 架构构建，支持：
1. A2A 通信：每个 Agent 既是客户端也是服务端
2. 工具调用：可调用自定义工具和 A2A 工具
3. 技能管理：支持渐进式技能披露
4. 事件驱动：可接收并处理来自其他 Agent 的事件

核心流程：
1. Agent 初始化时创建 AgentCard、A2AClient、A2AEventServer
2. 处理任务时执行 LangGraph 循环
3. 收到的 A2A 事件存入 pending_events，下次处理时注入上下文
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, TypedDict, Annotated, Callable, AsyncIterator
from pathlib import Path
import json
import os
import uuid
from dotenv import load_dotenv
from dataclasses import dataclass
from datetime import datetime, timezone

import frontmatter

load_dotenv()

from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, BaseMessage, ToolMessage, AIMessageChunk
from langchain_core.tools import BaseTool, tool
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from langchain_core.callbacks import AsyncCallbackManagerForLLMRun, CallbackManagerForLLMRun
import openai

from agent.core.a2a import (
    AgentCapability,
    AgentCard,
    init_a2a_client,
    get_a2a_client,
    create_a2a_tools
)


# ============================================================================
# 状态定义
# ============================================================================

class AgentState(TypedDict):
    """
    LangGraph 状态定义

    - messages: 对话消息列表
    - current_task: 当前任务描述
    - context: 任务上下文数据
    - skills_used: 已使用的技能列表
    - received_events: 接收到的 A2A 事件列表
    """
    messages: Annotated[List[BaseMessage], add_messages]
    current_task: str
    context: Dict[str, Any]
    skills_used: List[str]
    received_events: List[Dict[str, Any]]


# ============================================================================
# 技能管理
# ============================================================================

@dataclass
class SkillMetadata:
    """技能元数据"""
    name: str  # 技能名称
    description: str  # 技能描述
    license: Optional[str] = None  # 许可证
    allowed_tools: Optional[List[str]] = None  # 允许使用的工具


class SkillManager:
    """
    Skill 管理器 - 支持渐进式披露

    技能存储在 agent_dir/skills/ 目录下，每个技能一个子目录：
    - SKILL.md: 包含 frontmatter 元数据和正文
    """

    @staticmethod
    def parse_skill_metadata(skill_md_path: Path) -> tuple[SkillMetadata, str]:
        """
        解析 SKILL.md，返回 (元数据, 正文内容)

        Args:
            skill_md_path: SKILL.md 文件路径

        Returns:
            (SkillMetadata, 正文内容) 元组
        """
        post = frontmatter.load(skill_md_path)
        metadata = SkillMetadata(
            name=post.metadata.get('name', ''),
            description=post.metadata.get('description', ''),
            license=post.metadata.get('license'),
            allowed_tools=post.metadata.get('allowed_tools')
        )
        return metadata, post.content

    @staticmethod
    def load_all_skills(skills_dir: Path) -> Dict[str, tuple[SkillMetadata, str]]:
        """
        加载所有技能

        Args:
            skills_dir: skills 目录路径

        Returns:
            {skill_name: (metadata, content)} 字典
        """
        skills = {}
        if skills_dir.exists():
            for skill_dir in skills_dir.iterdir():
                if skill_dir.is_dir():
                    skill_file = skill_dir / "SKILL.md"
                    if skill_file.exists():
                        try:
                            metadata, content = SkillManager.parse_skill_metadata(skill_file)
                            skills[skill_dir.name] = (metadata, content)
                        except Exception as e:
                            print(f"加载 Skill 失败 {skill_file}: {e}")
        return skills


# ============================================================================
# 支持思考模式的 LLM 包装类
# ============================================================================

class ReasoningChatOpenAI(ChatOpenAI):
    """
    支持 reasoning_content 的 ChatOpenAI 包装类

    用于 Kimi k2.5 等支持思考模式的模型。
    通过重写 _generate 和 _agenerate 方法来提取 reasoning_content。
    """

    def _generate(
        self,
        messages: list,
        stop: Optional[list] = None,
        run_manager: Optional["CallbackManagerForLLMRun"] = None,
        **kwargs
    ) -> ChatResult:
        """
        重写 _generate 方法，提取 reasoning_content

        Args:
            messages: 输入消息列表
            stop: 停止词
            run_manager: 回调管理器

        Returns:
            ChatResult
        """
        self._ensure_sync_client_available()
        payload = self._get_request_payload(messages, stop=stop, **kwargs)
        # 注入 reasoning_content（LangChain 的 _convert_message_to_dict 不处理此字段）
        for i, msg_dict in enumerate(payload.get("messages", [])):
            if i < len(messages):
                msg = messages[i]
                rc = getattr(msg, "reasoning_content", None) or msg.additional_kwargs.get("reasoning_content", None)
                if rc:
                    msg_dict["reasoning_content"] = rc
                # 修复：content 为空的 assistant 消息，如果同时有 tool_calls 但没有对应响应，API 会报错
                # 这种消息来自 context 重建，我们将其 tool_calls 清空，避免 API 报错
                if msg_dict.get("role") == "assistant" and not msg_dict.get("content") and msg_dict.get("tool_calls"):
                    msg_dict["tool_calls"] = []
        generation_info = None
        raw_response = None

        try:
            raw_response = self.client.with_raw_response.create(**payload)
            response = raw_response.parse()
        except openai.BadRequestError as e:
            raise ValueError(f"OpenAI BadRequestError: {e}") from e
        except openai.APIError as e:
            raise ValueError(f"OpenAI APIError: {e}") from e
        except Exception as e:
            if raw_response is not None and hasattr(raw_response, "http_response"):
                e.response = raw_response.http_response
            raise e

        if self.include_response_headers and raw_response is not None:
            if hasattr(raw_response, "headers"):
                generation_info = {"headers": dict(raw_response.headers)}

        result = self._create_chat_result(response, generation_info)

        for i, generation in enumerate(result.generations):
            if isinstance(generation, ChatGeneration):
                if i < len(response.choices):
                    reasoning_content = getattr(response.choices[i].message, "reasoning_content", None)
                    if reasoning_content:
                        generation.message.additional_kwargs["reasoning_content"] = reasoning_content

        return result

    async def _agenerate(
        self,
        messages: list,
        stop: Optional[list] = None,
        run_manager: Optional["CallbackManagerForLLMRun"] = None,
        **kwargs
    ) -> ChatResult:
        """
        异步版本的 _generate，提取 reasoning_content

        Args:
            messages: 输入消息列表
            stop: 停止词
            run_manager: 回调管理器

        Returns:
            ChatResult
        """
        await self._ensure_async_client_available()
        payload = self._get_request_payload(messages, stop=stop, **kwargs)
        # 注入 reasoning_content
        for i, msg_dict in enumerate(payload.get("messages", [])):
            if i < len(messages):
                msg = messages[i]
                rc = getattr(msg, "reasoning_content", None) or msg.additional_kwargs.get("reasoning_content", None)
                if rc:
                    msg_dict["reasoning_content"] = rc
        generation_info = None
        raw_response = None

        try:
            raw_response = await self.async_client.with_raw_response.create(**payload)
            response = raw_response.parse()
        except openai.BadRequestError as e:
            raise ValueError(f"OpenAI BadRequestError: {e}") from e
        except openai.APIError as e:
            raise ValueError(f"OpenAI APIError: {e}") from e
        except Exception as e:
            if raw_response is not None and hasattr(raw_response, "http_response"):
                e.response = raw_response.http_response
            raise e

        if self.include_response_headers and raw_response is not None:
            if hasattr(raw_response, "headers"):
                generation_info = {"headers": dict(raw_response.headers)}

        result = self._create_chat_result(response, generation_info)

        for i, generation in enumerate(result.generations):
            if isinstance(generation, ChatGeneration):
                if i < len(response.choices):
                    reasoning_content = getattr(response.choices[i].message, "reasoning_content", None)
                    if reasoning_content:
                        generation.message.additional_kwargs["reasoning_content"] = reasoning_content

        return result

    def _inject_reasoning_content(self, payload: dict, messages: list) -> None:
        """将 reasoning_content 注入到 payload 的每条消息中"""
        for i, msg_dict in enumerate(payload.get("messages", [])):
            if i < len(messages):
                msg = messages[i]
                rc = getattr(msg, "reasoning_content", None) or msg.additional_kwargs.get("reasoning_content", None)
                if rc:
                    msg_dict["reasoning_content"] = rc

# ============================================================================
# LangGraph 节点工厂
# ============================================================================

class NodeFactory:
    """
    LangGraph 节点工厂

    创建标准的三节点结构：
    - model: LLM 调用节点
    - tool_node: 工具执行节点
    """

    @staticmethod
    def create_model_node(
        llm: ChatOpenAI,
        load_skills_metadata_fn: Callable,
        load_prompt_fn: Callable
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
            load_skills_metadata_fn: 加载技能元数据的函数
            load_prompt_fn: 加载 prompt 的函数

        Returns:
            模型节点函数
        """

        def model_node(state: AgentState) -> AgentState:
            # 获取技能元数据
            skills_metadata = load_skills_metadata_fn()

            messages = []
            system_prompt = load_prompt_fn("system_prompt")

            if system_prompt:
                if skills_metadata:
                    # 构建技能列表
                    skill_intro = "\n".join([f"- **{m.name}**: {m.description}" for m in skills_metadata])
                    system_content = system_prompt + "\n\n可用技能:\n" + skill_intro
                else:
                    system_content = system_prompt
                messages.append(SystemMessage(content=system_content))

            # 注入收到的 A2A 事件
            if state.get("received_events"):
                events_summary = "\n".join([
                    f"- [{e.get('event_type')}] from {e.get('source')}: {e.get('content', '')}"
                    for e in state["received_events"]
                ])
                events_msg = f"\n\n最近收到的 Agent 事件:\n{events_summary}"
                if messages and isinstance(messages[0], SystemMessage):
                    messages[0] = SystemMessage(content=messages[0].content + events_msg)
                else:
                    messages.append(SystemMessage(content=events_msg))

            # 添加用户消息
            messages.extend(state["messages"])

            # 检查是否只需要执行工具而不需要 LLM 再次调用
            # 如果状态中包含 ToolMessage（工具已执行），且 AIMessage 也有有效 tool_calls
            has_tool_results = any(isinstance(m, ToolMessage) for m in messages)
            has_valid_tc_in_state = any(
                isinstance(m, AIMessage) and getattr(m, "tool_calls", None) and any(
                    (isinstance(t, dict) and t.get("id")) or (hasattr(t, "id") and t.id)
                    for t in getattr(m, "tool_calls", [])
                )
                for m in messages
            )
            # 如果有工具结果但没有有效的 tool_calls，说明工具已执行完，需要 LLM 生成最终回复
            if has_tool_results and not has_valid_tc_in_state:
                # 只有工具结果，让 LLM 处理生成最终回复
                pass  # 继续调用 LLM
            elif has_tool_results and has_valid_tc_in_state:
                # 有工具结果且有有效 tool_calls，说明刚进入 graph，需要执行工具
                return {
                    "messages": messages,
                    "current_task": state["current_task"],
                    "context": state.get("context", {}),
                    "skills_used": [],
                    "received_events": state.get("received_events", [])
                }

            # 过滤掉空消息（content 为空且没有有效 tool_calls 的 assistant 消息会导致 API 错误）
            filtered = []
            for m in messages:
                if isinstance(m, AIMessage):
                    has_content = bool(m.content)
                    has_tc = getattr(m, "tool_calls", None)
                    has_valid_tc = has_tc and any(
                        (isinstance(t, dict) and t.get("id")) or (hasattr(t, "id") and t.id)
                        for t in has_tc
                    ) if has_tc else False
                    if not has_content and not has_valid_tc:
                        continue
                filtered.append(m)
            messages = filtered

            # 如果过滤后消息为空，且最后的 assistant 消息是空的 tool_call 占位，直接返回空响应
            if not messages:
                return {
                    "messages": [],
                    "current_task": state["current_task"],
                    "context": state.get("context", {}),
                    "skills_used": [],
                    "received_events": []
                }

            # 调用 LLM（非流式，用于状态更新）
            response = llm.invoke(messages)

            return {
                "messages": [response],  # 只返回新响应，不累积旧消息
                "current_task": state["current_task"],
                "context": state.get("context", {}),
                "skills_used": [],
                "received_events": []  # 清空已处理的事件
            }

        async def model_node_streaming(state: AgentState):
            """流式版本的 model_node，每个 token 实时 yield"""
            # 获取技能元数据
            skills_metadata = load_skills_metadata_fn()

            messages = []
            system_prompt = load_prompt_fn("system_prompt")

            if system_prompt:
                if skills_metadata:
                    skill_intro = "\n".join([f"- **{m.name}**: {m.description}" for m in skills_metadata])
                    system_content = system_prompt + "\n\n可用技能:\n" + skill_intro
                else:
                    system_content = system_prompt
                messages.append(SystemMessage(content=system_content))

            # 注入收到的 A2A 事件
            if state.get("received_events"):
                events_summary = "\n".join([
                    f"- [{e.get('event_type')}] from {e.get('source')}: {e.get('content', '')}"
                    for e in state["received_events"]
                ])
                events_msg = f"\n\n最近收到的 Agent 事件:\n{events_summary}"
                if messages and isinstance(messages[0], SystemMessage):
                    messages[0] = SystemMessage(content=messages[0].content + events_msg)
                else:
                    messages.append(SystemMessage(content=events_msg))

            # 添加用户消息
            messages.extend(state["messages"])

        return model_node

    @staticmethod
    def create_tool_node(tools: List[BaseTool]) -> Callable:
        """
        创建工具执行节点

        遍历 last_message 中的 tool_calls，执行对应工具

        Args:
            tools: 可用工具列表

        Returns:
            工具节点函数
        """

        def tool_node(state: AgentState) -> AgentState:
            last_message = state["messages"][-1]

            # 没有工具调用，直接返回
            if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
                return state

            tool_messages = []
            for tool_call in last_message.tool_calls:
                # 兼容 dict 和对象两种格式
                if isinstance(tool_call, dict):
                    tool_name = tool_call.get("name")
                    tool_args = tool_call.get("args", tool_call.get("arguments", {}))
                    tool_call_id = tool_call.get("id")
                else:
                    tool_name = tool_call.name
                    tool_args = tool_call.args
                    tool_call_id = tool_call.id

                # 查找并执行工具
                for tool in tools:
                    if tool.name == tool_name:
                        try:
                            result = tool.invoke(tool_args)
                        except Exception as e:
                            result = {"error": str(e)}

                        # 将工具结果作为 ToolMessage 添加
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
                "skills_used": state.get("skills_used", []),
                "received_events": state.get("received_events", [])
            }

        return tool_node

    @staticmethod
    def create_tools_condition(tools: List[BaseTool]) -> Callable:
        """
        创建工具调用条件判断函数

        决定下一步走 tool_node 还是 end

        Args:
            tools: 可用工具列表

        Returns:
            条件判断函数
        """

        def tools_condition(state: AgentState) -> str:
            last_message = state["messages"][-1] if state["messages"] else None
            tc = getattr(last_message, "tool_calls", None) if last_message else None
            has_tool_result = any(isinstance(m, ToolMessage) for m in state["messages"])

            if not tools:
                return "end"

            # 检查 tool_calls 是否有实际内容（有 id 的才算是有效的工具调用）
            has_valid_tc = False
            if tc and last_message and hasattr(last_message, "tool_calls") and last_message.tool_calls:
                for t in last_message.tool_calls:
                    tc_id = t.get("id") if isinstance(t, dict) else getattr(t, "id", None)
                    if tc_id:
                        has_valid_tc = True
                        break

            # 如果已有 ToolMessage 且没有有效 tool_calls，说明工具已执行完
            if has_tool_result and not has_valid_tc:
                return "end"
            # 如果已有 ToolMessage 且有有效 tool_calls，说明是第一轮或需要重新执行
            if has_tool_result and has_valid_tc:
                return "end"  # 工具已执行过，不再重复执行
            if has_valid_tc:
                return "tool_node"
            return "end"

        return tools_condition


# ============================================================================
# BaseAgent
# ============================================================================

class BaseAgent(ABC):
    """
    所有 Agent 的基类

    基于 LangGraph 架构，集成 A2A 通信能力：
    - 每个 Agent 有唯一的 AgentCard
    - 内置 A2AClient 用于发送消息
    - 内置 A2AEventServer 用于接收消息
    - 收到的消息存入 pending_events，下一轮处理时注入
    """

    def __init__(self, agent_dir: str, agent_id: Optional[str] = None, port: int = 8001):
        """
        初始化 BaseAgent

        Args:
            agent_dir: Agent 配置目录
            agent_id: Agent ID（不提供则自动生成）
            port: Agent 服务端口
        """
        self.agent_dir = Path(agent_dir)
        os.environ["AGENT_DIR"] = str(self.agent_dir.resolve())
        
        self.config = self._load_config()
        self.agent_type = self.config["agent_type"]
        self.agent_name = self.config["agent_name"]
        self.capabilities = self.config.get("capabilities", [])
        self.skills = self._load_skills()
        
        os.environ["AGENT_SKILLS_DIR"] = str((self.agent_dir / "skills").resolve())

        # A2A 相关
        self.agent_id = agent_id or f"{self.agent_type}-{str(uuid.uuid4())[:8]}"
        self.port = port
        self.endpoint = f"http://localhost:{port}"
        self.agent_card = self._build_agent_card()

        # A2A 客户端初始化
        self._init_a2a_client()

        # 加载工具
        self.tools = self._load_tools()

        # LangGraph
        self.llm = self._init_llm()
        self.graph = self._build_graph()

    def _build_agent_card(self) -> AgentCard:
        """
        构建 AgentCard

        根据配置构建当前 Agent 的 AgentCard

        Returns:
            AgentCard 实例
        """
        capabilities_list = [
            AgentCapability(
                name=cap.get("name", ""),
                description=cap.get("description", ""),
                parameters=cap.get("parameters", {})
            )
            for cap in self.capabilities
        ]

        return AgentCard(
            agent_id=self.agent_id,
            agent_name=self.agent_name,
            agent_type=self.agent_type,
            endpoint=self.endpoint,
            version=self.config.get("version", "1.0.0"),
            description=self.config.get("description", ""),
            capabilities=capabilities_list,
            status="active",
            created_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        )

    def _init_a2a_client(self):
        """
        初始化 A2A 客户端

        创建全局 A2AClient 实例，用于发现和发送消息
        """
        init_a2a_client(
            self_agent_id=self.agent_id,
            registry_endpoint="http://localhost:8000"
        )
        print(f"[BaseAgent] A2A Client initialized for {self.agent_id}")

    def _load_config(self) -> Dict[str, Any]:
        """
        加载 Agent 配置文件

        Returns:
            配置字典
        """
        config_file = self.agent_dir / "agent_config.json"
        if not config_file.exists():
            raise FileNotFoundError(f"配置文件不存在: {config_file}")

        with open(config_file, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _load_tools(self) -> List[BaseTool]:
        """
        加载工具

        1. 从配置文件的 tools 列表加载集中管理的工具
        2. 从 agent_dir/tools/ 目录加载额外工具（可选）
        3. 添加 A2A 工具

        Returns:
            工具列表
        """
        tools = []
        
        # 1. 从配置文件加载集中管理的工具
        tools_config = self.config.get("tools", [])
        for tool_config in tools_config:
            module_name = tool_config.get("module")
            if not module_name:
                continue
            try:
                import importlib
                module = importlib.import_module(module_name)
                if hasattr(module, "tools"):
                    for func in module.tools:
                        tools.append(func)
                print(f"[BaseAgent] Loaded tool from {module_name}")
            except Exception as e:
                print(f"[BaseAgent] Failed to load tool from {module_name}: {e}")
        
        # 2. 从 agent_dir/tools/ 目录加载额外工具（可选，向后兼容）
        tools_dir = self.agent_dir / "tools"
        if tools_dir.exists():
            for tool_file in tools_dir.glob("*.py"):
                if tool_file.name != "__init__.py":
                    try:
                        import importlib.util
                        spec = importlib.util.spec_from_file_location(
                            f"tools.{tool_file.stem}",
                            tool_file
                        )
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                        if hasattr(module, "tools"):
                            for func in module.tools:
                                tools.append(func)
                    except Exception as e:
                        print(f"[BaseAgent] Failed to load local tool {tool_file}: {e}")

        # 3. 添加 A2A 工具
        try:
            a2a_tools = create_a2a_tools()
            tools.extend(a2a_tools)
            print(f"[BaseAgent] Added {len(a2a_tools)} A2A tools")
        except Exception as e:
            print(f"[BaseAgent] Failed to load A2A tools: {e}")

        return tools

    def _load_skills(self) -> Dict[str, tuple[SkillMetadata, str]]:
        """
        加载技能

        Returns:
            {skill_name: (metadata, content)} 字典
        """
        skills_dir = self.agent_dir / "skills"
        return SkillManager.load_all_skills(skills_dir)

    def _init_llm(self) -> ChatOpenAI:
        """
        初始化 LLM

        Returns:
            ReasoningChatOpenAI 实例
        """
        model_config = self.config.get("model", {})

        api_key = os.getenv("OPENAI_API_KEY")
        api_base = os.getenv("OPENAI_API_BASE")
        model_id = model_config.get("model_id", "gpt-4")
        temperature = model_config.get("temperature", 0.7)
        max_tokens = model_config.get("max_tokens", 4000)

        llm = ReasoningChatOpenAI(
            api_key=api_key,
            base_url=api_base,
            model=model_id,
            temperature=temperature,
            max_tokens=max_tokens
        )

        # 绑定工具
        if self.tools:
            llm = llm.bind_tools(self.tools)

        return llm

    def _build_graph(self) -> StateGraph:
        """
        构建 LangGraph

        默认构建标准的三节点结构

        Returns:
            编译后的 StateGraph
        """
        return self._build_standard_graph()

    def _build_standard_graph(self) -> StateGraph:
        """
        构建标准的 Agent 图结构（Tool-Use Loop 模式）

        图结构：
        entry -> model -> (tool_node -> model) -> end

        Returns:
            编译后的 StateGraph
        """
        workflow = StateGraph(AgentState)

        model_node = NodeFactory.create_model_node(
            self.llm,
            self.get_all_skills_metadata,
            self.load_prompt
        )

        tool_node = NodeFactory.create_tool_node(self.tools)
        tools_condition = NodeFactory.create_tools_condition(self.tools)

        workflow.add_node("model", model_node)
        workflow.add_node("tool_node", tool_node)

        # 入口点
        workflow.set_entry_point("model")

        # 条件边：判断是否需要调用工具
        workflow.add_conditional_edges(
            "model",
            tools_condition,
            {
                "tool_node": "tool_node",
                "end": END
            }
        )

        # 工具执行完后回到 model
        workflow.add_edge("tool_node", "model")

        return workflow.compile()

    def get_all_skills_metadata(self) -> List[SkillMetadata]:
        """
        获取所有技能元数据

        Returns:
            SkillMetadata 列表
        """
        return [metadata for metadata, _ in self.skills.values()]

    def load_prompt(self, prompt_name: str) -> str:
        """
        加载 prompt 文件

        支持 .md 和 .txt 格式

        Args:
            prompt_name: prompt 文件名（不含扩展名）

        Returns:
            prompt 内容
        """
        # 尝试 .md 格式
        prompt_file = self.agent_dir / "prompts" / f"{prompt_name}.md"
        if prompt_file.exists():
            with open(prompt_file, 'r', encoding='utf-8') as f:
                return f.read()
        # 尝试 .txt 格式
        prompt_file_txt = self.agent_dir / "prompts" / f"{prompt_name}.txt"
        if prompt_file_txt.exists():
            with open(prompt_file_txt, 'r', encoding='utf-8') as f:
                return f.read()
        return ""

    async def register_with_registry(self):
        """
        将当前 Agent 注册到注册中心

        通常在 Agent 启动时调用
        """
        import aiohttp
        
        try:
            # 通过 HTTP API 调用 Web Console Backend 的注册接口
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "http://localhost:8000/api/registry/register",
                    json=self.agent_card.model_dump()
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        print(f"[BaseAgent] Agent registered: {self.agent_id} - {data.get('message')}")
                    else:
                        print(f"[BaseAgent] Failed to register agent: {self.agent_id} - Status: {response.status}")
        except Exception as e:
            print(f"[BaseAgent] Error registering agent: {self.agent_id} - {e}")

    async def process_task(self, task: str, context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        处理任务（同步模式）

        流程：
        1. 执行 LangGraph
        2. 返回结果

        Args:
            task: 任务描述
            context: 上下文数据

        Returns:
            处理结果字典
        """
        # 构建初始状态
        received_events_list = []

        initial_state: AgentState = {
            "messages": [HumanMessage(content=task)],
            "current_task": task,
            "context": context or {},
            "skills_used": [],
            "received_events": received_events_list
        }

        # 执行图
        result = await self.graph.ainvoke(initial_state)

        final_message = result["messages"][-1].content if result["messages"] else ""

        return {
            "task": task,
            "skills_used": result.get("skills_used", []),
            "status": "processed",
            "message": final_message,
            "messages": self._messages_to_dict(result["messages"])
        }

    async def process_task_stream(self, task: str, context: Optional[Dict] = None):
        """
        处理任务（流式模式）

        通过生成器逐个产出处理过程中的事件

        Args:
            task: 任务描述
            context: 上下文数据

        Yields:
            处理过程中的事件
        """
        try:
            from langgraph.types import StreamMode
            stream_mode = StreamMode.VALUES
        except (ImportError, AttributeError):
            stream_mode = "values"

        # 构建消息列表
        messages = []
        received_events_list = []
        if context and isinstance(context, list):
            for msg in context:
                if msg.get("role") == "user":
                    messages.append(HumanMessage(content=msg.get("content", "")))
                elif msg.get("role") == "assistant":
                    content = msg.get("content", "")
                    tool_calls = msg.get("tool_calls", [])
                    # 收集已有 tool 响应
                    existing_tool_ids = set()
                    for m in context:
                        if m.get("role") == "tool":
                            existing_tool_ids.add(m.get("tool_call_id"))
                    # 过滤出已有响应的 tool_calls
                    valid_tool_calls = []
                    for tc in tool_calls:
                        if isinstance(tc, dict):
                            tc_id = tc.get("id")
                            if tc_id and tc_id in existing_tool_ids:
                                # 规范化为 {id, name, args}，去掉 arguments 避免 LangChain 报错
                                valid_tool_calls.append({
                                    "id": tc_id,
                                    "name": tc.get("name", ""),
                                    "args": tc.get("args", tc.get("arguments", {}))
                                })
                        elif tc and tc in existing_tool_ids:
                            valid_tool_calls.append({
                                "id": tc,
                                "name": "",
                                "args": {}
                            })
                    # 跳过空消息（没有有效内容也没有有效工具调用）
                    if not content and not valid_tool_calls:
                        continue
                    messages.append(AIMessage(
                        content=content or "tool call",
                        tool_calls=valid_tool_calls,
                        reasoning_content=msg.get("reasoning_content") or ""
                    ))
                elif msg.get("role") == "tool":
                    tool_call_id = msg.get("tool_call_id")
                    if tool_call_id:
                        messages.append(ToolMessage(
                            content=msg.get("content", ""),
                            tool_call_id=tool_call_id,
                            additional_kwargs={"reasoning_content": ""}
                        ))

        messages.append(HumanMessage(content=task))

        initial_state: AgentState = {
            "messages": messages,
            "current_task": task,
            "context": context or {},
            "skills_used": [],
            "received_events": received_events_list
        }

        # ========== 第一步：LLM 生成 + 实时流式输出 ==========
        # 加载技能元数据
        skills_metadata = self.get_all_skills_metadata()
        system_prompt = self.load_prompt("system_prompt")
        if system_prompt:
            if skills_metadata:
                skill_intro = "\n".join([f"- **{m.name}**: {m.description}" for m in skills_metadata])
                system_content = system_prompt + "\n\n可用技能:\n" + skill_intro
            else:
                system_content = system_prompt
            messages.insert(0, SystemMessage(content=system_content))

        # 注入 A2A 事件
        if received_events_list:
            events_summary = "\n".join([
                f"- [{e.get('event_type')}] from {e.get('source')}: {e.get('content', '')}"
                for e in received_events_list
            ])
            events_msg = f"\n\n最近收到的 Agent 事件:\n{events_summary}"
            if messages and isinstance(messages[0], SystemMessage):
                messages[0] = SystemMessage(content=messages[0].content + events_msg)

        # 调用 LLM（非流式，等待完整响应）
        response = self.llm.invoke(messages)
        reasoning_content = getattr(response, "reasoning_content", None) or \
            (response.additional_kwargs.get("reasoning_content") if hasattr(response, "additional_kwargs") else None) or ""

        if reasoning_content:
            yield {"type": "reasoning", "content": reasoning_content}

        final_content = response.content or ""
        # 如果 LLM 没有产生 tool_calls，进入 done
        has_tool_calls = (hasattr(response, "tool_calls") and response.tool_calls) if response else False
        if not has_tool_calls:
            if final_content:
                yield {"type": "assistant", "content": final_content}
            yield {"type": "done", "skills_used": []}
            return

        # 输出 tool_call 事件（让前端能记录到 session）
        for tc in response.tool_calls:
            if isinstance(tc, dict):
                # 转换为 session 格式（使用 arguments 而不是 args）
                tc_dict = {
                    "id": tc.get("id"),
                    "name": tc.get("name"),
                    "arguments": tc.get("args", tc.get("arguments", {}))
                }
                yield {"type": "tool_call", "tool_calls": [tc_dict]}
            else:
                yield {"type": "tool_call", "tool_calls": [tc]}

        # ========== 第二步：直接执行工具，不经过 graph ==========
        # 直接调用 tool_node 执行工具，避免 model_node 的重复调用问题
        tool_call_entries = []
        for tc in (response.tool_calls if hasattr(response, 'tool_calls') and response.tool_calls else []):
            tc_id = tc.get("id")
            if tc_id:
                tool_call_entries.append({
                    "id": tc_id,
                    "name": tc.get("name"),
                    "args": tc.get("args", tc.get("arguments", {}))
                })

        if not tool_call_entries:
            if final_content:
                yield {"type": "assistant", "content": final_content}
            yield {"type": "done", "skills_used": []}
            return

        # 构建 tool_state 传给 tool_node
        tool_state: AgentState = {
            "messages": [AIMessage(content="", tool_calls=tool_call_entries)],
            "current_task": task,
            "context": context or {},
            "skills_used": [],
            "received_events": []
        }

        # 直接调用 tool_node 执行工具
        tool_result_state = NodeFactory.create_tool_node(self.tools)(tool_state)

        # 输出 tool_results
        for msg in tool_result_state.get("messages", []):
            if isinstance(msg, ToolMessage):
                yield {
                    "type": "tool_result",
                    "tool_call_id": msg.tool_call_id,
                    "content": msg.content
                }

        # ========== 第三步：输出最终的 assistant content ==========
        if final_content:
            yield {"type": "assistant", "content": final_content}

        yield {"type": "done", "skills_used": []}

    def _messages_to_dict(self, messages: List[BaseMessage]) -> List[Dict[str, Any]]:
        """
        将消息对象转换为字典格式

        用于序列化和存储

        Args:
            messages: 消息列表

        Returns:
            字典列表
        """
        result = []
        for msg in messages:
            msg_dict = {"role": "", "content": msg.content or ""}

            if isinstance(msg, HumanMessage):
                msg_dict["role"] = "user"
            elif isinstance(msg, AIMessage):
                msg_dict["role"] = "assistant"
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    tool_calls_list = []
                    for tc in msg.tool_calls:
                        if isinstance(tc, dict):
                            tool_calls_list.append({
                                "id": tc.get("id"),
                                "name": tc.get("name"),
                                "arguments": tc.get("args", tc.get("arguments", {}))
                            })
                        else:
                            tool_calls_list.append({
                                "id": tc.id,
                                "name": tc.name,
                                "arguments": tc.args
                            })
                    msg_dict["tool_calls"] = tool_calls_list
            elif isinstance(msg, ToolMessage):
                msg_dict["role"] = "tool"
                msg_dict["tool_call_id"] = msg.tool_call_id

            result.append(msg_dict)

        return result

    def get_a2a_app(self):
        """
        获取基础 FastAPI 应用（仅包含 AgentCard 和 Health 端点）

        完整路由由 main.py 在创建 A2AEventHandler 后挂载

        Returns:
            FastAPI 应用实例
        """
        from fastapi import FastAPI
        from fastapi.responses import JSONResponse

        app = FastAPI(title=f"{self.agent_name} A2A Server")

        @app.get("/.well-known/agent-card.json")
        async def get_agent_card():
            return JSONResponse(content=self.agent_card.model_dump())

        @app.get("/health")
        async def health_check():
            return {"status": "healthy", "agent_id": self.agent_id}

        return app
