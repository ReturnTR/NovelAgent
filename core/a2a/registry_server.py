"""
集中式 Agent 注册中心

提供 Agent 的注册、发现和管理功能：
- register_agent: 注册新的 Agent
- unregister_agent: 注销 Agent
- update_heartbeat: 更新 Agent 心跳
- get_agent: 获取特定 Agent 信息
- list_agents: 列出所有 Agent
- search_agents: 搜索 Agent（支持关键词和类型筛选）
- cleanup_stale_agents: 清理超时未响应的 Agent

设计思路：
- 使用单例模式，全局共享一个注册中心实例
- 使用 asyncio.Lock 保证线程安全
- 支持心跳检测，自动清理离线 Agent
"""

import asyncio
import uuid
from typing import Dict, List, Optional
from datetime import datetime, timezone
from .types import AgentCard, AgentCapability, A2AEvent, EventType


class AgentRegistryServer:
    """
    集中式 Agent 注册中心

    管理所有活跃 Agent 的 AgentCard 信息，提供：
    - 注册/注销
    - 心跳维护
    - 搜索发现
    """

    def __init__(self):
        self.agents: Dict[str, AgentCard] = {}  # 存储所有注册的 Agent
        self.lock = asyncio.Lock()  # 异步锁，保证线程安全
        self.heartbeat_timeout = 60  # 心跳超时时间（秒），超过则认为 Agent 离线

    async def register_agent(self, agent_card: AgentCard) -> bool:
        """
        注册一个新的 Agent

        Args:
            agent_card: Agent 的数字名片（包含 ID、名称、类型、地址、能力等）

        Returns:
            bool: 注册是否成功
        """
        async with self.lock:
            # 更新心跳时间
            agent_card.last_heartbeat = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            # 存入注册表
            self.agents[agent_card.agent_id] = agent_card
            print(f"[Registry] Agent registered: {agent_card.agent_id} ({agent_card.agent_name})")
            return True

    async def unregister_agent(self, agent_id: str) -> bool:
        """
        注销一个 Agent

        Args:
            agent_id: 要注销的 Agent ID

        Returns:
            bool: 注销是否成功
        """
        async with self.lock:
            if agent_id in self.agents:
                del self.agents[agent_id]
                print(f"[Registry] Agent unregistered: {agent_id}")
                return True
            return False

    async def update_heartbeat(self, agent_id: str) -> bool:
        """
        更新 Agent 心跳

        用于定期检测 Agent 是否仍然活跃：
        1. Agent 定期调用此方法更新心跳时间
        2. 如果超过 heartbeat_timeout 时间未更新，则认为 Agent 已离线

        Args:
            agent_id: Agent ID

        Returns:
            bool: 更新是否成功
        """
        async with self.lock:
            if agent_id in self.agents:
                # 更新心跳时间戳
                self.agents[agent_id].last_heartbeat = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                # 确保状态为 active
                self.agents[agent_id].status = "active"
                return True
            return False

    async def get_agent(self, agent_id: str) -> Optional[AgentCard]:
        """
        获取特定 Agent 的信息

        Args:
            agent_id: Agent ID

        Returns:
            AgentCard 或 None（如果不存在）
        """
        async with self.lock:
            return self.agents.get(agent_id)

    async def list_agents(self) -> List[AgentCard]:
        """
        列出所有已注册的 Agent

        Returns:
            AgentCard 列表
        """
        async with self.lock:
            return list(self.agents.values())

    async def list_agents_by_type(self, agent_type: str) -> List[AgentCard]:
        """
        按类型列出 Agent

        Args:
            agent_type: Agent 类型，如 "supervisor", "character"

        Returns:
            符合条件的 AgentCard 列表
        """
        async with self.lock:
            return [agent for agent in self.agents.values() if agent.agent_type == agent_type]

    async def search_agents(
        self,
        keywords: Optional[str] = None,
        agent_type: Optional[str] = None
    ) -> List[AgentCard]:
        """
        搜索 Agent

        支持两种筛选方式：
        1. keywords: 关键词搜索，匹配 Agent 名称、描述或能力
        2. agent_type: 按类型筛选

        Args:
            keywords: 搜索关键词
            agent_type: Agent 类型

        Returns:
            符合条件的 AgentCard 列表
        """
        async with self.lock:
            results = list(self.agents.values())

            # 按类型筛选
            if agent_type:
                results = [agent for agent in results if agent.agent_type == agent_type]

            # 按关键词筛选（匹配名称、描述、能力名称、能力描述）
            if keywords:
                keywords_lower = keywords.lower()
                results = [
                    agent for agent in results
                    if keywords_lower in agent.agent_name.lower()  # 匹配名称
                    or keywords_lower in agent.description.lower()  # 匹配描述
                    or any(
                        keywords_lower in cap.name.lower()  # 匹配能力名称
                        or keywords_lower in cap.description.lower()  # 匹配能力描述
                        for cap in agent.capabilities
                    )
                ]

            return results

    async def cleanup_stale_agents(self):
        """
        清理超时的 Agent

        定期检查所有 Agent 的心跳时间：
        - 如果超过 heartbeat_timeout 秒未更新心跳
        - 则认为该 Agent 已离线，从注册表中移除

        通常由后台任务定期调用
        """
        async with self.lock:
            now = datetime.now(timezone.utc)
            stale_agents = []

            # 遍历所有 Agent，检查心跳超时
            for agent_id, agent in list(self.agents.items()):
                if agent.last_heartbeat:
                    try:
                        # 解析心跳时间
                        last_hb = datetime.fromisoformat(agent.last_heartbeat.replace("Z", "+00:00"))
                        # 检查是否超时
                        if (now - last_hb).total_seconds() > self.heartbeat_timeout:
                            stale_agents.append(agent_id)
                    except:
                        # 解析失败也视为超时
                        stale_agents.append(agent_id)

            # 移除超时的 Agent
            for agent_id in stale_agents:
                del self.agents[agent_id]
                print(f"[Registry] Stale agent removed: {agent_id}")


# 全局单例注册中心实例
# 所有 Agent 和服务共享同一个注册中心
_registry_instance: Optional[AgentRegistryServer] = None


def get_registry() -> AgentRegistryServer:
    """
    获取全局注册中心单例实例

    Returns:
        AgentRegistryServer 实例

    Note:
        如果实例不存在，会创建一个新的
    """
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = AgentRegistryServer()
    return _registry_instance
