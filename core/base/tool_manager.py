"""
工具管理器

负责从多种来源加载工具：
1. 配置文件中集中管理的工具
2. agent_dir/tools/ 目录下的额外工具
3. A2A 工具
"""

import importlib
from pathlib import Path
from typing import List, Dict, Any

from langchain_core.tools import BaseTool


class ToolManager:
    """
    工具管理器
    """

    @staticmethod
    def load_tools_from_config(config: Dict[str, Any]) -> List[BaseTool]:
        """
        从配置文件的 tools 列表加载集中管理的工具

        Args:
            config: Agent 配置字典

        Returns:
            工具列表
        """
        tools = []
        tools_config = config.get("tools", [])

        for tool_config in tools_config:
            module_name = tool_config.get("module")
            if not module_name:
                continue
            try:
                module = importlib.import_module(module_name)
                if hasattr(module, "tools"):
                    for func in module.tools:
                        tools.append(func)
                print(f"[ToolManager] Loaded tool from {module_name}")
            except Exception as e:
                print(f"[ToolManager] Failed to load tool from {module_name}: {e}")

        return tools

    @staticmethod
    def load_tools_from_directory(tools_dir: Path) -> List[BaseTool]:
        """
        从 agent_dir/tools/ 目录加载额外工具

        Args:
            tools_dir: tools 目录路径

        Returns:
            工具列表
        """
        tools = []
        if not tools_dir.exists():
            return tools

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
                    print(f"[ToolManager] Failed to load local tool {tool_file}: {e}")

        return tools

    @staticmethod
    def load_a2a_tools() -> List[BaseTool]:
        """
        加载 A2A 工具

        Returns:
            A2A 工具列表
        """
        tools = []
        try:
            from core.a2a import create_a2a_tools
            a2a_tools = create_a2a_tools()
            tools.extend(a2a_tools)
            print(f"[ToolManager] Added {len(a2a_tools)} A2A tools")
        except Exception as e:
            print(f"[ToolManager] Failed to load A2A tools: {e}")
        return tools

    @classmethod
    def load_all_tools(cls, config: Dict[str, Any], agent_dir: Path) -> List[BaseTool]:
        """
        加载所有来源的工具

        Args:
            config: Agent 配置字典
            agent_dir: Agent 目录路径

        Returns:
            合并后的工具列表
        """
        tools = []

        # 1. 从配置文件加载
        tools.extend(cls.load_tools_from_config(config))

        # 2. 从 agent_dir/tools/ 目录加载
        tools_dir = agent_dir / "tools"
        tools.extend(cls.load_tools_from_directory(tools_dir))

        # 3. A2A 工具
        tools.extend(cls.load_a2a_tools())

        return tools
