"""
A2A 客户端模块

负责：
- 发现可用 Agent
- 向其他 Agent 发送消息
- 提供 A2A Tools（供 LLM 调用）
"""

import json
import uuid
from typing import Dict, List, Any, Optional

import requests
from langchain_core.tools import tool

from .types import A2AEvent, EventType, SendMessageMode


class A2AClient:
    """A2A 客户端"""

    def __init__(self, agent_id: str, registry_endpoint: str):
        """
        初始化 A2AClient

        Args:
            agent_id: 当前 Agent ID
            registry_endpoint: 注册中心地址
        """
        self.agent_id = agent_id
        self.registry_endpoint = registry_endpoint

    def discover_agents(
        self,
        keywords: Optional[str] = None,
        agent_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """发现可用 Agent"""
        try:
            params = {}
            if keywords:
                params["keywords"] = keywords
            if agent_type:
                params["agent_type"] = agent_type

            response = requests.get(
                f"{self.registry_endpoint}/api/registry/search",
                params=params,
                timeout=30
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("agents", [])
            return []
        except Exception:
            return []

    def _send_event(
        self,
        target_endpoint: str,
        event: A2AEvent,
        timeout: int = 30
    ) -> Optional[A2AEvent]:
        """向目标 Agent 发送 A2A 事件"""
        try:
            response = requests.post(
                f"{target_endpoint}/a2a/event",
                json=event.model_dump(),
                timeout=timeout,
                stream=True
            )
            if response.status_code == 200:
                content_type = response.headers.get("content-type", "")
                if "text/event-stream" in content_type:
                    events_data = []
                    for line in response.iter_lines():
                        if line:
                            line_str = line.decode("utf-8") if isinstance(line, bytes) else line
                            if line_str.startswith("data: "):
                                try:
                                    events_data.append(json.loads(line_str[6:]))
                                except json.JSONDecodeError:
                                    pass

                    final_content = ""
                    for evt in events_data:
                        if evt.get("type") == "assistant":
                            final_content = evt.get("content", "")
                        elif evt.get("type") == "done":
                            break

                    return A2AEvent(
                        event_id=event.event_id,
                        event_type=EventType.TASK_RESPONSE,
                        source=event.target or "",
                        target=event.source,
                        task_id=event.task_id,
                        content={
                            "result": final_content,
                            "events_count": len(events_data)
                        }
                    )
                else:
                    data = response.json()
                    return A2AEvent(**data)
            return None
        except Exception:
            return None

    def send_agent_message(
        self,
        target_agent_id: str,
        task: str,
        context: Optional[Dict[str, Any]] = None,
        mode: SendMessageMode = SendMessageMode.SYNC,
        timeout: int = 30
    ) -> Dict[str, Any]:
        """
        向指定 Agent 发送消息

        Args:
            target_agent_id: 目标 Agent ID
            task: 任务描述
            context: 任务上下文
            mode: 发送模式（同步/异步）
            timeout: 超时时间

        Returns:
            执行结果字典
        """
        # 查找目标 Agent
        target_agents = self.discover_agents()
        target_agent = next(
            (a for a in target_agents if a.get("agent_id") == target_agent_id),
            None
        )

        if not target_agent:
            return {"success": False, "error": f"Agent {target_agent_id} not found"}

        # 构造事件
        event = A2AEvent(
            event_id=f"evt-{str(uuid.uuid4())[:8]}",
            event_type=EventType.TASK_REQUEST,
            source=self.agent_id,
            target=target_agent_id,
            task_id=f"task-{str(uuid.uuid4())[:8]}",
            content={
                "task": task,
                "context": context or {},
                "mode": mode.value,
                "timeout": timeout
            }
        )

        target_endpoint = target_agent.get("endpoint")

        if mode == SendMessageMode.SYNC:
            response_event = self._send_event(target_endpoint, event, timeout=timeout)
            if response_event:
                return {
                    "success": True,
                    "event": response_event.model_dump(),
                    "result": response_event.content.get("result")
                }
            return {"success": False, "error": "No response received"}
        else:
            self._send_event(target_endpoint, event, timeout=5)
            return {
                "success": True,
                "message": "Message sent asynchronously",
                "event_id": event.event_id,
                "task_id": event.task_id
            }

    # =========================================================================
    # A2A Tools（供 LLM 调用）
    # =========================================================================

    def get_tools(self) -> List:
        """获取 A2A Tools（供 LLM 调用）"""
        client = self

        @tool("discover_agents")
        def discover_agents(
            keywords: Optional[str] = None,
            agent_type: Optional[str] = None
        ) -> Dict[str, Any]:
            """
            搜索和发现可用的 Agent

            Args:
                keywords: 搜索关键词，匹配 Agent 名称、描述或能力
                agent_type: 按 Agent 类型筛选，如 "character", "supervisor"

            Returns:
                找到的 Agent 列表
            """
            try:
                agents = client.discover_agents(keywords, agent_type)
                return {"success": True, "count": len(agents), "agents": agents}
            except Exception as e:
                return {"success": False, "error": str(e)}

        @tool("send_agent_message")
        def send_agent_message(
            target_agent_id: str,
            task: str,
            context: Optional[Dict[str, Any]] = None,
            timeout: int = 30
        ) -> Dict[str, Any]:
            """
            向指定的 Agent 发送消息（同步模式，等待返回结果）

            使用场景：
            - 需要等待目标 Agent 处理完成后才能继续
            - 需要获取目标 Agent 的执行结果

            Args:
                target_agent_id: 目标 Agent 的 ID
                task: 任务描述
                context: 任务上下文数据
                timeout: 超时时间（秒），默认 30 秒

            Returns:
                同步响应结果
            """
            try:
                result = client.send_agent_message(
                    target_agent_id=target_agent_id,
                    task=task,
                    context=context,
                    mode=SendMessageMode.SYNC,
                    timeout=timeout
                )
                return result
            except Exception as e:
                return {"success": False, "error": str(e)}

        @tool("send_agent_message_async")
        def send_agent_message_async(
            content: str,
            target_agent_id: str,
            event_id: Optional[str] = None
        ) -> Dict[str, Any]:
            """
            异步发送消息给指定 Agent（发送后立即返回，不等待结果）

            使用场景：
            - 不需要立即获取结果
            - 目标 Agent 可以慢慢处理
            - 目标 Agent 会自主判断是否回复

            消息格式：
            "这是一条来自\"{source_agent_id}\"的消息，消息id为{event_id}，消息内容如下：\n{content}"

            Args:
                content: 消息内容
                target_agent_id: 目标 Agent 的 ID
                event_id: 消息ID（可选，不填则自动生成）

            Returns:
                发送成功或失败信息
            """
            try:
                # 自动生成 event_id
                if not event_id:
                    event_id = f"evt-{str(uuid.uuid4())[:8]}"

                # 格式化内容
                formatted_content = f"这是一条来自\"{client.agent_id}\"的消息，消息id为{event_id}，消息内容如下：\n{content}"

                # 查找目标 Agent
                target_agents = client.discover_agents()
                target_agent = next(
                    (a for a in target_agents if a.get("agent_id") == target_agent_id),
                    None
                )

                if not target_agent:
                    return {"success": False, "message": f"发送失败: 未找到 Agent {target_agent_id}"}

                target_endpoint = target_agent.get("endpoint")

                # 构造事件
                from .types import A2AEvent, EventType
                event = A2AEvent(
                    event_id=event_id,
                    event_type=EventType.TASK_REQUEST,
                    source=client.agent_id,
                    target=target_agent_id,
                    task_id=f"task-{str(uuid.uuid4())[:8]}",
                    content={
                        "task": formatted_content,
                        "context": {},
                        "mode": "async"
                    }
                )

                # 发送（不等待响应）
                import requests
                response = requests.post(
                    f"{target_endpoint}/a2a/async_event",
                    json=event.model_dump(),
                    timeout=10
                )

                if response.status_code == 200:
                    return {"success": True, "message": "发送成功", "event_id": event_id}
                else:
                    return {"success": False, "message": f"发送失败: {response.text}"}

            except Exception as e:
                return {"success": False, "message": f"发送失败: {str(e)}"}

        return [discover_agents, send_agent_message_async]