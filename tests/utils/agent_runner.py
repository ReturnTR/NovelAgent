"""
Agent 测试运行器

管理测试 Agent 的生命周期：启动、停止、日志收集
"""

import os
import sys
import time
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

# 添加项目路径
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "agents" / "supervisor_agent"))
sys.path.insert(0, str(PROJECT_ROOT / "agents" / "test_agent"))


class AgentRunner:
    """
    管理测试 Agent 的生命周期
    """

    def __init__(
        self,
        agent_dir: str,
        port: int = 9999,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        log_file: Optional[str] = None
    ):
        self.agent_dir = Path(agent_dir)
        self.port = port
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.api_base = api_base or os.getenv("OPENAI_API_BASE")
        self.agent = None
        self.log_file = Path(log_file) if log_file else None
        self._setup_logging()

    def _setup_logging(self):
        """设置日志"""
        # 总是配置 logging（不管 DEBUG 模式）
        handlers = []
        if self.log_file:
            self.log_file.parent.mkdir(parents=True, exist_ok=True)
            handlers.append(logging.FileHandler(self.log_file, encoding='utf-8'))
        handlers.append(logging.StreamHandler())

        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S',
            handlers=handlers
        )
        self.logger = logging.getLogger("agent_runner")

    def start(self) -> 'AgentRunner':
        """启动 Agent"""
        self.logger.info(f"[AgentRunner] Starting agent from {self.agent_dir}")
        self.logger.info(f"[AgentRunner] API_KEY set: {bool(self.api_key)}, API_BASE: {self.api_base}")

        # 设置环境变量（在创建 Agent 之前）
        os.environ["OPENAI_API_KEY"] = self.api_key
        os.environ["OPENAI_API_BASE"] = self.api_base

        # 导入并创建 Agent via A2AEventServer
        from cores.supervisor_agent import SupervisorAgent
        from core.a2a.event_server import A2AEventServer

        self.logger.info(f"[AgentRunner] Creating SupervisorAgent with dir: {self.agent_dir}")
        self.logger.info(f"[AgentRunner] Env before Agent - OPENAI_API_BASE: {os.getenv('OPENAI_API_BASE')}")

        agent_id = f"test-agent-{int(time.time())}"

        # Load config
        config_path = Path(self.agent_dir) / "agent_config.json"
        import json
        config = json.loads(config_path.read_text())

        # Create A2AEventServer which creates the agent internally
        self.a2a_server = A2AEventServer(
            agent_id=agent_id,
            config=config,
            agent_dir=self.agent_dir,
            port=self.port,
            agent_class=SupervisorAgent
        )

        # Get agent reference
        self.agent = self.a2a_server.agent

        # 始终重建 LLM 以确保使用正确的 API 配置
        self.logger.info(f"[AgentRunner] Recreating LLM with correct API config...")
        self._recreate_llm()

        self.logger.info(f"[AgentRunner] Agent started: {agent_id}")
        self.logger.info(f"[AgentRunner] LLM base_url: {getattr(self.agent.llm, 'base_url', 'N/A')}")
        self.logger.info(f"[AgentRunner] tools: {[t.name for t in self.agent.tools]}")
        return self

    def _recreate_llm(self):
        """重新创建 LLM（当环境变量被污染时）"""
        print(f"[AgentRunner] _recreate_llm called, api_base={self.api_base}")
        from core.base.llm.openai_provider import OpenAIReasoningProvider

        model_config = self.agent.config.get("model", {})
        model_id = model_config.get("model_id", "kimi-k2.5")
        temperature = model_config.get("temperature", 1.0)
        max_tokens = model_config.get("max_tokens", 8192)

        self.agent.llm = OpenAIReasoningProvider(
            api_key=self.api_key,
            base_url=self.api_base,
            model=model_id,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=self.agent.tools if self.agent.tools else None,
        )
        print(f"[AgentRunner] LLM recreated, new base_url={getattr(self.agent.llm, 'base_url', 'N/A')}")

    def stop(self):
        """停止 Agent"""
        if self.agent:
            self.logger.info(f"[AgentRunner] Stopping agent")
            self.agent = None

    async def chat_async(self, task: str, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """异步发送聊天请求并返回事件列表"""
        if not self.agent:
            raise RuntimeError("Agent not started")

        session_id = session_id or f"test-session-{int(time.time())}"
        events = []

        async for event in self.a2a_server.handle_user_message(task, session_id):
            events.append(event)

        return events

    def chat(self, task: str, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        发送聊天请求并返回事件列表（同步版本）

        Args:
            task: 任务描述
            session_id: 会话 ID，默认自动生成

        Returns:
            事件列表
        """
        import asyncio

        if not self.agent:
            raise RuntimeError("Agent not started")

        return asyncio.run(self.chat_async(task, session_id))

    def get_session_history(self, session_id: str) -> List[Dict[str, Any]]:
        """获取会话历史"""
        if not self.agent:
            raise RuntimeError("Agent not started")
        return self.a2a_server.session_manager.get_session_history(session_id)

    def get_log_content(self) -> str:
        """读取日志文件内容"""
        if self.log_file and self.log_file.exists():
            with open(self.log_file, 'r', encoding='utf-8') as f:
                return f.read()
        return ""

    @classmethod
    def create_for_test(cls, test_name: str, agent_dir: str, port: int = 9999,
                        api_key: str = None, api_base: str = None) -> 'AgentRunner':
        """
        工厂方法：为测试创建 Runner

        Args:
            test_name: 测试名称，用于日志文件名
            agent_dir: Agent 目录路径
            port: 端口号
            api_key: API 密钥
            api_base: API 基础 URL
        """
        log_dir = Path(__file__).parent.parent / "logs"
        log_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f"{test_name}_{timestamp}.log"

        return cls(
            agent_dir=agent_dir,
            port=port,
            api_key=api_key,
            api_base=api_base,
            log_file=str(log_file)
        )


class ChatResult:
    """聊天结果封装"""

    def __init__(self, events: List[Dict[str, Any]]):
        self.events = events

        # 解析事件
        self.reasoning = [e for e in events if e.get("type") == "reasoning"]
        self.tool_calls = [e for e in events if e.get("type") == "tool_call"]
        self.tool_results = [e for e in events if e.get("type") == "tool_result"]
        self.assistant = [e for e in events if e.get("type") == "assistant"]
        self.final = events[-1] if events else {}

    @property
    def final_content(self) -> str:
        """最终回复内容"""
        return self.final.get("content", "")

    @property
    def has_tool_call(self) -> bool:
        """是否有工具调用"""
        return len(self.tool_calls) > 0

    @property
    def first_tool_name(self) -> Optional[str]:
        """第一个工具名称"""
        if self.tool_calls:
            tc = self.tool_calls[0].get("tool_calls", [{}])[0]
            return tc.get("name")
        return None

    @property
    def first_tool_args(self) -> Optional[Dict]:
        """第一个工具参数"""
        if self.tool_calls:
            tc = self.tool_calls[0].get("tool_calls", [{}])[0]
            return tc.get("arguments", {})
        return None
