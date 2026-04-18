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
from typing import Dict, List, Any, Optional, TypedDict, Annotated, Callable
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
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, BaseMessage, ToolMessage
from langchain_core.tools import BaseTool, tool

from agent.core.a2a import (
    AgentCapability,
    AgentCard,
    A2AEvent,
    EventType,
    init_a2a_client,
    get_a2a_client,
    create_a2a_tools,
    A2AEventServer
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

            # 调用 LLM
            response = llm.invoke(messages)

            return {
                "messages": [response],
                "current_task": state["current_task"],
                "context": state.get("context", {}),
                "skills_used": [],
                "received_events": []  # 清空已处理的事件
            }

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
            if not tools:
                return "end"

            last_message = state["messages"][-1] if state["messages"] else None
            if last_message and hasattr(last_message, "tool_calls") and last_message.tool_calls:
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
        self.config = self._load_config()
        self.agent_type = self.config["agent_type"]
        self.agent_name = self.config["agent_name"]
        self.capabilities = self.config.get("capabilities", [])
        self.skills = self._load_skills()

        # A2A 相关
        self.agent_id = agent_id or f"{self.agent_type}-{str(uuid.uuid4())[:8]}"
        self.port = port
        self.endpoint = f"http://localhost:{port}"
        self.agent_card = self._build_agent_card()

        # Session 相关
        self.session_id = os.getenv("AGENT_SESSION_ID")
        self.registry_endpoint = "http://localhost:8000"

        # A2A 初始化（先初始化，再加载工具）
        self._init_a2a_client()
        self._init_a2a_event_server()

        # 加载工具（需要A2A客户端）
        self.tools = self._load_tools()

        # LangGraph
        self.llm = self._init_llm()
        self.graph = self._build_graph()

        # 待处理的 A2A 事件
        self.pending_events: List[A2AEvent] = []

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

    def _init_a2a_event_server(self):
        """
        初始化 A2A 事件服务器

        创建 A2AEventServer 实例，用于接收消息
        """
        self.event_server = A2AEventServer(
            self_agent_card=self.agent_card,
            on_event_received=self._on_event_received,
            on_task_request=self._on_task_request
        )
        print(f"[BaseAgent] A2A Event Server initialized for {self.agent_id}")

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

        从 tools/ 目录加载自定义工具，并添加 A2A 工具

        Returns:
            工具列表
        """
        tools = []
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
                        print(f"加载工具失败 {tool_file}: {e}")

        # 添加 A2A 工具
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
            ChatOpenAI 实例
        """
        model_config = self.config.get("model", {})

        api_key = os.getenv("OPENAI_API_KEY")
        api_base = os.getenv("OPENAI_API_BASE")
        model_id = model_config.get("model_id", "gpt-4")
        temperature = model_config.get("temperature", 0.7)
        max_tokens = model_config.get("max_tokens", 4000)

        llm = ChatOpenAI(
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

    def _get_session_messages(self) -> List[Dict]:
        """
        从Session中获取所有消息（包括用户消息和Agent间消息）

        通过HTTP调用Web Console Backend的API接口

        Returns:
            消息列表
        """
        if not self.session_id:
            print(f"[BaseAgent] No session_id, returning empty messages")
            return []

        try:
            import requests
            url = f"{self.registry_endpoint}/api/sessions/{self.session_id}/messages"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                return data.get("messages", [])
            else:
                print(f"[BaseAgent] Failed to get session messages: {response.status_code} - {response.text}")
                return []
        except Exception as e:
            print(f"[BaseAgent] Error getting session messages: {e}")
            return []

    def _append_agent_message_to_session(self, role: str, content: str, source_agent_id: str, target_agent_id: str, event_id: Optional[str] = None, task_id: Optional[str] = None):
        """
        将Agent间通信消息记录到Session中

        通过HTTP调用Web Console Backend的API接口

        Args:
            role: 消息角色（user/assistant）
            content: 消息内容
            source_agent_id: 发送者Agent ID
            target_agent_id: 接收者Agent ID
            event_id: 事件ID（可选）
            task_id: 任务ID（可选）
        """
        if not self.session_id:
            print(f"[BaseAgent] No session_id, skipping agent message recording")
            return

        try:
            import requests
            url = f"{self.registry_endpoint}/api/sessions/{self.session_id}/agent-message"
            data = {
                "role": role,
                "content": content,
                "source_agent_id": source_agent_id,
                "target_agent_id": target_agent_id
            }
            if event_id:
                data["event_id"] = event_id
            if task_id:
                data["task_id"] = task_id
            
            response = requests.post(url, json=data, timeout=5)
            if response.status_code == 200:
                print(f"[BaseAgent] Agent message recorded to session: {self.session_id}")
            else:
                print(f"[BaseAgent] Failed to record agent message: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"[BaseAgent] Error recording agent message: {e}")

    def _on_event_received(self, event: A2AEvent):
        """
        收到 A2A 事件的回调

        将事件存入 pending_events 队列，并记录到Session中

        Args:
            event: 收到的事件
        """
        print(f"[BaseAgent] Received event: {event.event_id} type={event.event_type}")
        self.pending_events.append(event)

        # 如果是TASK_REQUEST事件，将消息记录到Session中
        if event.event_type == EventType.TASK_REQUEST:
            task = event.content.get("task", "")
            self._append_agent_message_to_session(
                role="user",
                content=task,
                source_agent_id=event.source,
                target_agent_id=event.target,
                event_id=event.event_id,
                task_id=event.task_id
            )

    async def _on_task_request(self, event: A2AEvent) -> Any:
        """
        收到任务请求的回调

        Args:
            event: TASK_REQUEST 事件

        Returns:
            任务处理结果
        """
        print(f"[BaseAgent] Handling task request: {event.event_id}")
        task = event.content.get("task", "")
        
        # 从Session中获取完整的上下文（包括用户消息和Agent间消息）
        session_messages = self._get_session_messages()
        
        result = await self.process_task(task, {"session_messages": session_messages})
        
        # 将响应消息也记录到Session中
        result_content = result.get("message", "")
        self._append_agent_message_to_session(
            role="assistant",
            content=result_content,
            source_agent_id=self.agent_id,
            target_agent_id=event.source,
            event_id=event.event_id,
            task_id=event.task_id
        )
        
        return result

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
        1. 从 pending_events 取出事件加入状态
        2. 执行 LangGraph
        3. 返回结果

        Args:
            task: 任务描述
            context: 上下文数据

        Returns:
            处理结果字典
        """
        # 取出待处理的事件
        received_events_list = []
        while self.pending_events:
            event = self.pending_events.pop(0)
            received_events_list.append({
                "event_id": event.event_id,
                "event_type": event.event_type,
                "source": event.source,
                "content": event.content
            })

        # 构建初始状态
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

        # 取出待处理的事件
        received_events_list = []
        while self.pending_events:
            event = self.pending_events.pop(0)
            received_events_list.append({
                "event_id": event.event_id,
                "event_type": event.event_type,
                "source": event.source,
                "content": event.content
            })

        # 构建消息列表
        messages = []
        if context and isinstance(context, list):
            for msg in context:
                if msg.get("role") == "user":
                    messages.append(HumanMessage(content=msg.get("content", "")))
                elif msg.get("role") == "assistant":
                    content = msg.get("content", "")
                    tool_calls = msg.get("tool_calls", [])
                    tool_calls_objects = []
                    for tc in tool_calls:
                        if isinstance(tc, dict):
                            tool_calls_objects.append({
                                "id": tc.get("id"),
                                "name": tc.get("name"),
                                "args": tc.get("arguments", tc.get("args", {}))
                            })
                    messages.append(AIMessage(
                        content=content,
                        tool_calls=tool_calls_objects if tool_calls_objects else []
                    ))
                elif msg.get("role") == "tool":
                    tool_call_id = msg.get("tool_call_id")
                    if tool_call_id:
                        messages.append(ToolMessage(
                            content=msg.get("content", ""),
                            tool_call_id=tool_call_id
                        ))

        messages.append(HumanMessage(content=task))

        initial_state: AgentState = {
            "messages": messages,
            "current_task": task,
            "context": context or {},
            "skills_used": [],
            "received_events": received_events_list
        }

        # 流式执行
        last_event = None
        async for event in self.graph.astream(initial_state, stream_mode=stream_mode):
            last_event = event
            messages = event.get("messages", [])
            if not messages:
                continue

            last_message = messages[-1]

            # 根据消息类型生成事件
            if isinstance(last_message, AIMessage):
                if hasattr(last_message, "tool_calls") and last_message.tool_calls:
                    tool_calls_list = []
                    for tc in last_message.tool_calls:
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
                    yield {
                        "type": "tool_call",
                        "content": last_message.content or "",
                        "tool_calls": tool_calls_list
                    }
                else:
                    yield {
                        "type": "assistant",
                        "content": last_message.content or ""
                    }
            elif isinstance(last_message, ToolMessage):
                yield {
                    "type": "tool_result",
                    "tool_call_id": last_message.tool_call_id,
                    "content": last_message.content
                }
            elif isinstance(last_message, HumanMessage):
                pass

        # 完成事件
        if last_event:
            yield {
                "type": "done",
                "skills_used": last_event.get("skills_used", [])
            }
        else:
            yield {
                "type": "done",
                "skills_used": []
            }

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
        获取 A2A FastAPI 应用

        用于挂载到主应用

        Returns:
            FastAPI 应用实例
        """
        return self.event_server.get_app()
