"""
OpenAI 系 LLM Provider

支持 reasoning_content 的 ChatOpenAI 包装类，用于 Kimi k2.5 等支持思考模式的模型。
"""

import os
import logging
from typing import List, Dict, Any, Optional, TYPE_CHECKING, Callable
import json

from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, AIMessage, ToolMessage
from langchain_core.outputs import ChatResult, ChatGeneration, ChatGenerationChunk
from langchain_core.callbacks import CallbackManagerForLLMRun
import openai

from .base import LLMProvider
from .registry import register_provider

if TYPE_CHECKING:
    pass

# 日志配置
DEBUG_MODE = os.getenv("AGENT_DEBUG", "false").lower() == "true"
DEBUG_LLM = os.getenv("AGENT_DEBUG_LLM", "false").lower() == "true" or DEBUG_MODE
DEBUG_REASONING = os.getenv("AGENT_DEBUG_REASONING", "false").lower() == "true" or DEBUG_MODE

if DEBUG_LLM or DEBUG_REASONING:
    logging.basicConfig(level=logging.DEBUG, format='[%(asctime)s] %(name)s - %(levelname)s - %(message)s', datefmt='%H:%M:%S')

logger = logging.getLogger(__name__)


class OpenAIReasoningProvider(LLMProvider):
    """
    OpenAI 系 Provider，支持 reasoning_content

    用于 Kimi、DeepSeek 等支持 thinking_content 的模型。
    """

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 4000,
        tools: Optional[List] = None,
    ):
        """
        初始化 OpenAI Provider

        Args:
            api_key: API key
            base_url: API base URL
            model: 模型名称
            temperature: 温度
            max_tokens: 最大 token 数
            tools: 可用工具列表
        """
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.tools = tools  # 保存工具列表

        self._llm = ChatOpenAI(
            api_key=api_key,
            base_url=base_url,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens
        )

        if tools:
            self._llm = self._llm.bind_tools(tools)

    def format_messages(self, messages: List[BaseMessage]) -> List[Dict[str, Any]]:
        """
        将 LangChain 消息转换为 OpenAI 格式

        重写了 _get_request_payload 来注入 reasoning_content

        Returns:
            消息列表
        """
        return self._llm._get_request_payload(messages)["messages"]

    def extract_reasoning(self, response: Any) -> Optional[str]:
        """
        从响应中提取 reasoning_content

        Args:
            response: OpenAI 响应对象

        Returns:
            reasoning_content 字符串
        """
        if hasattr(response, "choices") and response.choices:
            return getattr(response.choices[0].message, "reasoning_content", None)
        return None

    def invoke(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        **kwargs
    ) -> ChatResult:
        """
        同步调用 LLM

        关键：注入 reasoning_content 到请求，提取响应中的 reasoning_content
        """
        self._ensure_sync_client_available()
        payload = self._get_request_payload(messages, stop=stop, **kwargs)

        # 日志：LLM 请求
        if DEBUG_LLM:
            msg_count = len(payload.get("messages", []))
            logger.debug(f"[LLM_REQUEST] messages={msg_count}")

        # 注入 reasoning_content
        self._inject_reasoning_content(payload, messages)

        # 日志：reasoning_content 注入
        if DEBUG_REASONING:
            for i, msg_dict in enumerate(payload.get("messages", [])):
                if msg_dict.get("role") == "assistant" and msg_dict.get("tool_calls"):
                    rc = msg_dict.get("reasoning_content", "")
                    logger.debug(f"[REASONING_INJECT] msg[{i}] has_reasoning={bool(rc)}, len={len(rc)}")
                    if not rc:
                        logger.warning(f"[REASONING_MISSING] msg[{i}] role=assistant, has_tool_calls=True")

        # 添加 tools 到 payload（bind_tools 绑定后需要手动添加）
        if self.tools:
            tools_list = []
            for tool in self.tools:
                # 获取参数 schema
                args_schema = getattr(tool, 'args_schema', None)
                if args_schema:
                    if hasattr(args_schema, 'schema'):
                        params = args_schema.schema()
                    elif hasattr(args_schema, 'model_json_schema'):
                        params = args_schema.model_json_schema()
                    else:
                        params = {"type": "object", "properties": {}}
                else:
                    params = {"type": "object", "properties": {}}

                tools_list.append({
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": getattr(tool, 'description', '') or '',
                        "parameters": params
                    }
                })
            payload["tools"] = tools_list

        # 启用 Kimi k2.5 思考模式 (通过 extra_body)
        payload["extra_body"] = {
            "thinking": {
                "type": "enabled",
                "max_tokens": self.max_tokens
            }
        }

        # 清理空消息 - 不要清空 tool_calls
        for i, msg_dict in enumerate(payload.get("messages", [])):
            if i < len(messages):
                msg = messages[i]
                if isinstance(msg, AIMessage) and msg_dict.get("role") == "assistant":
                    if not msg_dict.get("content") and msg_dict.get("tool_calls"):
                        pass  # 不要清空 tool_calls，保留以进行工具调用

        generation_info = None
        raw_response = None

        try:
            raw_response = self._llm.client.with_raw_response.create(**payload)
            response = raw_response.parse()
        except openai.BadRequestError as e:
            raise ValueError(f"OpenAI BadRequestError: {e}") from e
        except openai.APIError as e:
            raise ValueError(f"OpenAI APIError: {e}") from e
        except Exception as e:
            if raw_response is not None and hasattr(raw_response, "http_response"):
                e.response = raw_response.http_response
            raise e

        if self._llm.include_response_headers and raw_response is not None:
            if hasattr(raw_response, "headers"):
                generation_info = {"headers": dict(raw_response.headers)}

        result = self._llm._create_chat_result(response, generation_info)

        # 提取 reasoning_content 到 generation
        for i, generation in enumerate(result.generations):
            if isinstance(generation, ChatGeneration):
                if i < len(response.choices):
                    reasoning_content = getattr(response.choices[i].message, "reasoning_content", None)
                    if reasoning_content:
                        generation.message.additional_kwargs["reasoning_content"] = reasoning_content

        # 日志：LLM 响应
        if DEBUG_LLM:
            generation = result.generations[0] if result.generations else None
            message = generation.message if generation else None
            content = message.content if message else ""
            tc = message.tool_calls if message else None
            rc = message.additional_kwargs.get("reasoning_content") if message else None

            logger.debug(f"[LLM_RESPONSE] content_len={len(content)}, tool_calls={bool(tc)}, reasoning={bool(rc)}")
            if tc:
                for t in (tc if isinstance(tc, list) else []):
                    tc_id = t.get("id") if isinstance(t, dict) else getattr(t, "id", "N/A")
                    tc_name = t.get("name") if isinstance(t, dict) else getattr(t, "name", "N/A")
                    logger.debug(f"  tool_call: id={tc_id}, name={tc_name}")

        return result

    async def ainvoke(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        **kwargs
    ) -> ChatResult:
        """异步调用 LLM"""
        await self._ensure_async_client_available()
        payload = self._get_request_payload(messages, stop=stop, **kwargs)

        # 注入 reasoning_content
        self._inject_reasoning_content(payload, messages)

        # 添加 tools 到 payload
        if self.tools:
            tools_list = []
            for tool in self.tools:
                args_schema = getattr(tool, 'args_schema', None)
                if args_schema:
                    if hasattr(args_schema, 'schema'):
                        params = args_schema.schema()
                    elif hasattr(args_schema, 'model_json_schema'):
                        params = args_schema.model_json_schema()
                    else:
                        params = {"type": "object", "properties": {}}
                else:
                    params = {"type": "object", "properties": {}}

                tools_list.append({
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": getattr(tool, 'description', '') or '',
                        "parameters": params
                    }
                })
            payload["tools"] = tools_list

        # 启用 Kimi k2.5 思考模式 (通过 extra_body)
        payload["extra_body"] = {
            "thinking": {
                "type": "enabled",
                "max_tokens": self.max_tokens
            }
        }

        # 清理空消息 - 不要清空 tool_calls
        for i, msg_dict in enumerate(payload.get("messages", [])):
            if i < len(messages):
                msg = messages[i]
                if isinstance(msg, AIMessage) and msg_dict.get("role") == "assistant":
                    if not msg_dict.get("content") and msg_dict.get("tool_calls"):
                        pass  # 不要清空 tool_calls，保留以进行工具调用

        generation_info = None
        raw_response = None

        try:
            raw_response = await self._llm.async_client.with_raw_response.create(**payload)
            response = raw_response.parse()
        except openai.BadRequestError as e:
            raise ValueError(f"OpenAI BadRequestError: {e}") from e
        except openai.APIError as e:
            raise ValueError(f"OpenAI APIError: {e}") from e
        except Exception as e:
            if raw_response is not None and hasattr(raw_response, "http_response"):
                e.response = raw_response.http_response
            raise e

        if self._llm.include_response_headers and raw_response is not None:
            if hasattr(raw_response, "headers"):
                generation_info = {"headers": dict(raw_response.headers)}

        result = self._llm._create_chat_result(response, generation_info)

        # 提取 reasoning_content
        for i, generation in enumerate(result.generations):
            if isinstance(generation, ChatGeneration):
                if i < len(response.choices):
                    reasoning_content = getattr(response.choices[i].message, "reasoning_content", None)
                    if reasoning_content:
                        generation.message.additional_kwargs["reasoning_content"] = reasoning_content

        return result

    def bind_tools(self, tools: List[Any]) -> "OpenAIReasoningProvider":
        """绑定工具"""
        self._llm = self._llm.bind_tools(tools)
        return self

    @property
    def llm(self):
        """获取底层 LLM 实例"""
        return self._llm

    # ========== 内部辅助方法 ==========

    def _ensure_sync_client_available(self):
        """确保同步客户端可用"""
        if not hasattr(self._llm, "client") or self._llm.client is None:
            self._llm.client = self._llm._get_sync_client()

    async def _ensure_async_client_available(self):
        """确保异步客户端可用"""
        await self._llm._ensure_async_client_available()

    def _get_request_payload(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        **kwargs
    ) -> dict:
        """获取请求 payload"""
        return self._llm._get_request_payload(messages, stop=stop, **kwargs)

    def _inject_reasoning_content(self, payload: dict, messages: List[BaseMessage]) -> None:
        """将 reasoning_content 注入到 payload"""
        for i, msg_dict in enumerate(payload.get("messages", [])):
            if i < len(messages):
                msg = messages[i]
                rc = getattr(msg, "reasoning_content", None) or msg.additional_kwargs.get("reasoning_content", None)
                if rc:
                    msg_dict["reasoning_content"] = rc
                elif msg_dict.get("role") == "assistant" and msg_dict.get("tool_calls"):
                    # When thinking mode is enabled, assistant messages with tool_calls
                    # must include reasoning_content field (even if empty)
                    if "reasoning_content" not in msg_dict:
                        msg_dict["reasoning_content"] = ""


# 便捷函数
def create_openai_provider(
    api_key: str,
    base_url: str,
    model: str,
    temperature: float = 0.7,
    max_tokens: int = 4000,
    tools: Optional[List] = None,
) -> OpenAIReasoningProvider:
    """创建并注册 OpenAI Provider"""
    provider = OpenAIReasoningProvider(
        api_key=api_key,
        base_url=base_url,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        tools=tools,
    )
    register_provider("openai", provider)
    return provider
