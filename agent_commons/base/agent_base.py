from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, TypedDict
from pathlib import Path
import json
from ..a2a.protocol import A2AProtocol
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
import os
from dotenv import load_dotenv

load_dotenv()

class AgentState(TypedDict):
    messages: List[Dict[str, Any]]
    current_task: str
    context: Dict[str, Any]

class BaseAgent(ABC):
    """所有Agent的基类"""
    
    def __init__(self, agent_dir: str):
        self.agent_dir = Path(agent_dir)
        self.config = self._load_config()
        self.a2a = A2AProtocol()
        
        self.agent_type = self.config["agent_type"]
        self.agent_name = self.config["agent_name"]
        self.capabilities = self.config.get("capabilities", [])
        self.tools = self._load_tools()
        self.skills = self._load_skills()
        
        # 初始化LLM
        self.llm = self._init_llm()
    
    def _load_config(self) -> Dict[str, Any]:
        """加载Agent配置文件"""
        config_file = self.agent_dir / "agent_config.json"
        if not config_file.exists():
            raise FileNotFoundError(f"配置文件不存在: {config_file}")
        
        with open(config_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _load_tools(self) -> List[Any]:
        """加载工具函数"""
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
                            tools.extend(module.tools)
                    except Exception as e:
                        print(f"加载工具失败 {tool_file}: {e}")
        return tools
    
    def _load_skills(self) -> Dict[str, str]:
        """加载技能（渐进式披露的MD文件）"""
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
    
    @abstractmethod
    async def process_task(self, task: str, context: Optional[Dict] = None) -> Dict[str, Any]:
        """处理任务（子类实现）"""
        pass
    
    @abstractmethod
    def is_skill_relevant(self, skill_name: str, task: str) -> bool:
        """判断技能是否相关（子类实现）"""
        pass
    
    def get_relevant_skills(self, task: str) -> Dict[str, str]:
        """获取相关技能"""
        relevant_skills = {}
        for skill_name, skill_content in self.skills.items():
            if self.is_skill_relevant(skill_name, task):
                relevant_skills[skill_name] = skill_content
        return relevant_skills
    
    def load_prompt(self, prompt_name: str) -> str:
        """加载提示文件"""
        prompt_file = self.agent_dir / "prompts" / f"{prompt_name}.txt"
        if prompt_file.exists():
            with open(prompt_file, 'r', encoding='utf-8') as f:
                return f.read()
        return ""
    
    def _init_llm(self) -> ChatOpenAI:
        """初始化LLM"""
        model_config = self.config.get("model", {})
        
        # 从环境变量或配置中获取API信息
        api_key = os.getenv("OPENAI_API_KEY")
        api_base = os.getenv("OPENAI_API_BASE")
        model_id = model_config.get("model_id", "gpt-4")
        temperature = model_config.get("temperature", 0.7)
        max_tokens = model_config.get("max_tokens", 4000)
        
        # 初始化ChatOpenAI
        return ChatOpenAI(
            api_key=api_key,
            base_url=api_base,
            model=model_id,
            temperature=temperature,
            max_tokens=max_tokens
        )
    
    async def generate_response(self, task: str, context: Optional[Any] = None) -> str:
        """生成LLM响应"""
        # 加载系统提示
        system_prompt = self.load_prompt("system_prompt")
        
        # 构建消息
        messages = []
        
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
        
        # 添加历史消息
        if context and isinstance(context, list):
            for msg in context:
                if msg.get("role") == "user":
                    messages.append(HumanMessage(content=msg.get("content", "")))
                elif msg.get("role") == "assistant":
                    messages.append(AIMessage(content=msg.get("content", "")))
        
        # 添加当前任务
        messages.append(HumanMessage(content=task))
        
        # 调用LLM
        response = await self.llm.ainvoke(messages)
        return response.content
