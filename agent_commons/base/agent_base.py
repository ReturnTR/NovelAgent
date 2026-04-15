from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, TypedDict, Annotated, Callable
from pathlib import Path
import json
import os
from dotenv import load_dotenv

load_dotenv()

from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, BaseMessage, ToolMessage
from langchain_core.tools import BaseTool, tool

class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    current_task: str
    context: Dict[str, Any]
    skills_used: List[str]

class NodeFactory:
    @staticmethod
    def create_model_node(llm: ChatOpenAI, get_relevant_skills_fn: Callable, load_prompt_fn: Callable) -> Callable:
        def model_node(state: AgentState) -> AgentState:
            relevant_skills = get_relevant_skills_fn(state["current_task"])

            messages = []
            system_prompt = load_prompt_fn("system_prompt")

            if system_prompt:
                if relevant_skills:
                    skill_context = "\n\n".join([f"## {name}\n{content}" for name, content in relevant_skills.items()])
                    system_content = system_prompt + "\n\n可用技能:\n" + skill_context
                else:
                    system_content = system_prompt
                messages.append(SystemMessage(content=system_content))

            messages.extend(state["messages"])
            response = llm.invoke(messages)

            return {
                "messages": [response],
                "current_task": state["current_task"],
                "context": state.get("context", {}),
                "skills_used": list(relevant_skills.keys())
            }

        return model_node

    @staticmethod
    def create_tool_node(tools: List[BaseTool]) -> Callable:
        def tool_node(state: AgentState) -> AgentState:
            last_message = state["messages"][-1]
            
            if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
                return state

            tool_messages = []
            for tool_call in last_message.tool_calls:
                # 处理 dict 或对象两种情况
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
                "skills_used": state.get("skills_used", [])
            }

        return tool_node

    @staticmethod
    def create_tools_condition(tools: List[BaseTool]) -> Callable:
        def tools_condition(state: AgentState) -> str:
            if not tools:
                return "end"

            last_message = state["messages"][-1] if state["messages"] else None
            if last_message and hasattr(last_message, "tool_calls") and last_message.tool_calls:
                return "tool_node"
            return "end"

        return tools_condition

class BaseAgent(ABC):
    """所有Agent的基类 - 基于 LangGraph 架构，支持自定义节点网络"""

    def __init__(self, agent_dir: str):
        self.agent_dir = Path(agent_dir)
        self.config = self._load_config()
        self.agent_type = self.config["agent_type"]
        self.agent_name = self.config["agent_name"]
        self.capabilities = self.config.get("capabilities", [])
        self.tools = self._load_tools()
        self.skills = self._load_skills()

        self.llm = self._init_llm()
        self.graph = self._build_graph()

    def _load_config(self) -> Dict[str, Any]:
        config_file = self.agent_dir / "agent_config.json"
        if not config_file.exists():
            raise FileNotFoundError(f"配置文件不存在: {config_file}")

        with open(config_file, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _load_tools(self) -> List[BaseTool]:
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
        return tools

    def _load_skills(self) -> Dict[str, str]:
        skills = {}
        skills_dir = self.agent_dir / "skills"
        if skills_dir.exists():
            for skill_dir in skills_dir.iterdir():
                if skill_dir.is_dir():
                    skill_file = skill_dir / "skill.md"
                    if skill_file.exists():
                        with open(skill_file, 'r', encoding='utf-8') as f:
                            skills[skill_dir.name] = f.read()
        return skills

    def _init_llm(self) -> ChatOpenAI:
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

        if self.tools:
            llm = llm.bind_tools(self.tools)

        return llm

    def _build_graph(self) -> StateGraph:
        """构建默认的标准图结构，子类可重写此方法定制自己的节点网络"""
        return self._build_standard_graph()

    def _build_standard_graph(self) -> StateGraph:
        """构建标准的 Agent 图结构（Tool-Use Loop 模式）"""
        workflow = StateGraph(AgentState)

        # 使用 NodeFactory 创建节点函数
        model_node = NodeFactory.create_model_node(
            self.llm,
            self.get_relevant_skills,
            self.load_prompt
        )

        tool_node = NodeFactory.create_tool_node(self.tools)
        tools_condition = NodeFactory.create_tools_condition(self.tools)

        # 添加节点
        workflow.add_node("model", model_node)
        workflow.add_node("tool_node", tool_node)

        # 设置入口点
        workflow.set_entry_point("model")

        # 添加条件边
        workflow.add_conditional_edges(
            "model",
            tools_condition,
            {
                "tool_node": "tool_node",  # tool_use → 执行工具
                "end": END                # end_turn → 任务完成
            }
        )

        # 执行工具后回到 model 节点（循环）
        workflow.add_edge("tool_node", "model")

        return workflow.compile()

    @abstractmethod
    def is_skill_relevant(self, skill_name: str, task: str) -> bool:
        """判断技能是否相关（子类必须实现）"""
        pass

    def get_relevant_skills(self, task: str) -> Dict[str, str]:
        relevant_skills = {}
        for skill_name, skill_content in self.skills.items():
            if self.is_skill_relevant(skill_name, task):
                relevant_skills[skill_name] = skill_content
        return relevant_skills

    def load_prompt(self, prompt_name: str) -> str:
        prompt_file = self.agent_dir / "prompts" / f"{prompt_name}.txt"
        if prompt_file.exists():
            with open(prompt_file, 'r', encoding='utf-8') as f:
                return f.read()
        return ""

    async def process_task(self, task: str, context: Optional[Dict] = None) -> Dict[str, Any]:
        """同步处理任务，返回最终结果"""
        history = context if isinstance(context, list) else []

        initial_state: AgentState = {
            "messages": [HumanMessage(content=task)],
            "current_task": task,
            "context": context or {},
            "skills_used": []
        }

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
        """流式处理任务，通过生成器返回中间状态（用于 SSE）"""
        try:
            from langgraph.types import StreamMode
            stream_mode = StreamMode.VALUES
        except (ImportError, AttributeError):
            # 兼容旧版本或不同导入方式
            stream_mode = "values"
        print(context)
        # 构建初始消息列表，包含历史消息
        messages = []

        # 处理历史消息 - 按顺序处理
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
                    print(f"tool_call_id: {tool_call_id}")
                    if tool_call_id:
                        messages.append(ToolMessage(
                            content=msg.get("content", ""),
                            tool_call_id=tool_call_id
                        ))
        
        # 添加当前任务
        messages.append(HumanMessage(content=task))
        initial_state: AgentState = {
            "messages": messages,
            "current_task": task,
            "context": context or {},
            "skills_used": []
        }

        # 流式执行图，获取每个节点的更新
        last_event = None
        async for event in self.graph.astream(initial_state, stream_mode=stream_mode):
            last_event = event
            messages = event.get("messages", [])
            if not messages:
                continue

            last_message = messages[-1]

            # 根据消息类型生成不同的事件
            if isinstance(last_message, AIMessage):
                if hasattr(last_message, "tool_calls") and last_message.tool_calls:
                    # AI 请求调用工具
                    tool_calls_list = []
                    for tc in last_message.tool_calls:
                        # 处理 dict 或对象两种情况
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
                    # AI 普通回复
                    yield {
                        "type": "assistant",
                        "content": last_message.content or ""
                    }

            elif isinstance(last_message, ToolMessage):
                # 工具执行结果
                yield {
                    "type": "tool_result",
                    "tool_call_id": last_message.tool_call_id,
                    "content": last_message.content
                }
            elif isinstance(last_message, HumanMessage):
                # 用户消息，跳过
                pass

        # 最终完成事件
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
        """将消息对象转换为字典格式，用于存储"""
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
                        # 处理 dict 或对象两种情况
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
