"""
LLM Provider 基类

定义统一接口，各 Provider 实现：
- 消息格式转换
- reasoning_content 提取
- LLM 调用
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, TYPE_CHECKING

from langchain_core.messages import BaseMessage
from langchain_core.outputs import ChatResult

if TYPE_CHECKING:
    from langchain_core.callbacks import CallbackManagerForLLMRun


class LLMProvider(ABC):
    """
    LLM Provider 抽象接口

    各厂商实现需提供：
    1. 消息格式转换 (format_messages)
    2. reasoning_content 提取 (extract_reasoning)
    3. LLM 调用 (invoke, ainvoke)
    """

    @abstractmethod
    def format_messages(self, messages: List[BaseMessage]) -> List[Dict[str, Any]]:
        """
        将 LangChain 消息转换为 provider 格式

        Args:
            messages: LangChain 消息列表

        Returns:
            转换后的消息列表
        """
        pass

    @abstractmethod
    def extract_reasoning(self, response: Any) -> Optional[str]:
        """
        从响应中提取 reasoning_content

        Args:
            response: LLM 响应对象

        Returns:
            reasoning_content 字符串，无则返回 None
        """
        pass

    @abstractmethod
    def invoke(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        **kwargs
    ) -> ChatResult:
        """
        同步调用 LLM

        Args:
            messages: 消息列表
            stop: 停止词
            **kwargs: 其他参数

        Returns:
            ChatResult
        """
        pass

    async def ainvoke(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        **kwargs
    ) -> ChatResult:
        """
        异步调用 LLM

        默认实现调用同步版本，可被子类重写以支持真正的异步

        Args:
            messages: 消息列表
            stop: 停止词
            **kwargs: 其他参数

        Returns:
            ChatResult
        """
        import asyncio
        return await asyncio.get_event_loop().run_in_executor(
            None, self.invoke, messages, stop
        )

    def bind_tools(self, tools: List[Any]) -> "LLMProvider":
        """
        绑定工具到 LLM

        默认实现返回 self，子类可重写

        Args:
            tools: 工具列表

        Returns:
            绑定工具后的 LLMProvider
        """
        return self
