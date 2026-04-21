"""
A2A 事件处理器

职责：
1. 接收 A2AEvent（来自 A2A 网络）和用户消息（来自 Web Console）
2. 调用 BaseAgent.process_task_stream() 处理
3. 维护 Session 历史（读写 Agent 本地 JSONL 文件）
4. yield 结构化事件给 FastAPI 端点

设计原则：
- BaseAgent 只做任务处理，不知道谁在调用
- Session 历史完全由 Handler 维护
"""

import json
import uuid
import asyncio
from pathlib import Path
from typing import Dict, List, Any, Optional, AsyncIterator
from datetime import datetime, timezone

from .types import A2AEvent, EventType


class A2AEventHandler:
    """
    A2A 事件处理器

    持有 BaseAgent 引用，负责：
    - 事件路由分发
    - Session 维护
    - 调用 Agent 处理并 yield 结构化事件
    """

    def __init__(self, agent, session_dir: str):
        """
        Args:
            agent: BaseAgent 实例
            session_dir: Session 文件存储目录
        """
        self.agent = agent
        self.session_dir = Path(session_dir)
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.session_index_file = self.session_dir / "sessions_index.json"

        self._ensure_session_index()

    def _ensure_session_index(self):
        """确保 Session 索引文件存在"""
        if not self.session_index_file.exists():
            self._save_index({"sessions": []})

    def _load_index(self) -> Dict:
        """加载 Session 索引"""
        try:
            with open(self.session_index_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {"sessions": []}

    def _save_index(self, index_data: Dict):
        """保存 Session 索引"""
        with open(self.session_index_file, 'w', encoding='utf-8') as f:
            json.dump(index_data, f, ensure_ascii=False, indent=2)

    def _get_or_create_session(self, session_id: str):
        """获取或创建 Session 元数据"""
        index_data = self._load_index()
        for session in index_data["sessions"]:
            if session.get("session_id") == session_id:
                return session

        # 创建新 Session
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        new_session = {
            "session_id": session_id,
            "agent_id": self.agent.agent_id,
            "created_at": now,
            "updated_at": now,
            "status": "active"
        }
        index_data["sessions"].append(new_session)
        self._save_index(index_data)
        return new_session

    def _append_message_to_session_file(self, session_id: str, message: Dict):
        """追加消息到 Session 文件（JSONL 格式）"""
        session_file = self.session_dir / f"{session_id}.jsonl"
        with open(session_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(message, ensure_ascii=False) + '\n')

        # 更新索引的 updated_at
        index_data = self._load_index()
        for session in index_data["sessions"]:
            if session.get("session_id") == session_id:
                session["updated_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                self._save_index(index_data)
                break

    def get_session_history(self, session_id: str) -> List[Dict]:
        """获取指定 Session 的历史消息"""
        session_file = self.session_dir / f"{session_id}.jsonl"
        if not session_file.exists():
            return []

        messages = []
        with open(session_file, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    try:
                        msg = json.loads(line)
                        # 过滤掉 metadata 行
                        if msg.get("type") not in ("message", "agent"):
                            continue
                        messages.append(msg)
                    except json.JSONDecodeError:
                        continue
        return messages

    async def handle_user_message(self, task: str, session_id: str) -> AsyncIterator[Dict]:
        """
        处理用户消息（来自 Web Console）

        流程：
        1. 确保 Session 存在
        2. 保存用户消息到 Session
        3. 获取 Session 历史作为 context
        4. 调用 agent.process_task_stream()
        5. 保存 Agent 响应到 Session
        6. yield 结构化事件

        Args:
            task: 用户任务描述
            session_id: Session ID

        Yields:
            {"type": "reasoning", "content": "..."}
            {"type": "tool_call", "tool_calls": [...]}
            {"type": "content", "content": "..."}
            {"type": "tool_result", "tool_call_id": "...", "content": "..."}
            {"type": "done", "skills_used": [...]}
        """
        # 确保 Session 存在
        self._get_or_create_session(session_id)

        # 保存用户消息
        user_msg = {
            "type": "message",
            "role": "user",
            "content": task,
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        }
        self._append_message_to_session_file(session_id, user_msg)

        # 获取 Session 历史作为 context
        history = self.get_session_history(session_id)

        # 调用 Agent 处理
        assistant_content = ""
        reasoning_content = ""
        tool_calls_result = []
        tool_results = []
        skills_used = []

        async for event in self.agent.process_task_stream(task, history):
            evt_type = event.get("type")

            if evt_type == "reasoning":
                reasoning_content = event.get("content", "")
                yield event

            elif evt_type == "assistant":
                assistant_content = event.get("content", "")
                yield event

            elif evt_type == "tool_call":
                tool_calls_result = event.get("tool_calls", [])
                yield event

            elif evt_type == "tool_result":
                tool_results.append(event)
                yield event

            elif evt_type == "done":
                skills_used = event.get("skills_used", [])
                yield event

        # 保存 Assistant 响应消息
        if assistant_content or tool_calls_result:
            assistant_msg = {
                "type": "message",
                "role": "assistant",
                "content": assistant_content,
                "tool_calls": tool_calls_result if tool_calls_result else None,
                "reasoning_content": reasoning_content if reasoning_content else None,
                "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            }
            # 移除 None 值
            assistant_msg = {k: v for k, v in assistant_msg.items() if v}
            self._append_message_to_session_file(session_id, assistant_msg)

        # 保存 Tool 结果消息
        for tr in tool_results:
            tool_msg = {
                "type": "message",
                "role": "tool",
                "tool_call_id": tr.get("tool_call_id"),
                "content": tr.get("content", ""),
                "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            }
            self._append_message_to_session_file(session_id, tool_msg)

    async def handle_event(self, event: A2AEvent) -> AsyncIterator[Dict]:
        """
        处理 A2A 事件（Agent 间通信）

        流程：
        1. 如果是 TASK_REQUEST，提取 task 和 context
        2. 调用 agent.process_task_stream()
        3. yield 结构化事件

        Args:
            event: A2AEvent 事件对象

        Yields:
            结构化事件（同 handle_user_message）
        """
        task = event.content.get("task", "")
        context = event.content.get("context", [])

        async for evt in self.agent.process_task_stream(task, context):
            yield evt

    def get_a2a_app(self):
        """
        获取 FastAPI 应用（代理到 agent.get_a2a_app）

        保留此方法是为了兼容原有调用方式
        """
        return self.agent.get_a2a_app()