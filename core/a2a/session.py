"""
Session 管理模块

负责单 agent 内部的会话管理：
- 索引文件管理 (sessions_index.json)
- 会话消息持久化 (JSONL 格式)
- 唯一 active session 机制
"""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional


def _now_iso() -> str:
    """返回当前 UTC 时间 ISO 格式"""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class SessionManager:
    """
    单 Agent Session 管理器

    负责：
    - 索引文件读写
    - 会话消息追加
    - 唯一 active session 机制
    """

    def __init__(self, session_dir: str, agent_id: str):
        """
        初始化 SessionManager

        Args:
            session_dir: Session 文件存储目录
            agent_id: Agent 唯一标识
        """
        self.session_dir = Path(session_dir)
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.session_index_file = self.session_dir / "sessions_index.json"
        self.agent_id = agent_id
        self._ensure_session_index()
        self.migrate_sessions()  # 确保所有旧session都有session_name

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

    def _get_or_create_session(self, session_id: str) -> Dict:
        """获取或创建 Session 元数据"""
        index_data = self._load_index()
        for session in index_data["sessions"]:
            if session.get("session_id") == session_id:
                return session

        now = _now_iso()
        new_session = {
            "session_id": session_id,
            "agent_id": self.agent_id,
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
                session["updated_at"] = _now_iso()
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
                        if msg.get("type") not in ("message", "agent_request", "agent_response"):
                            continue
                        messages.append(msg)
                    except json.JSONDecodeError:
                        continue
        return messages

    def list_sessions(self) -> List[Dict]:
        """列出所有 session"""
        index_data = self._load_index()
        return index_data.get("sessions", [])

    def ensure_active_session(self, session_id: str):
        """确保指定 session 是唯一的 active session"""
        index_data = self._load_index()
        has_change = False
        for session in index_data["sessions"]:
            if session["session_id"] == session_id:
                if session.get("status") != "active":
                    session["status"] = "active"
                    session["updated_at"] = _now_iso()
                    has_change = True
            else:
                if session.get("status") == "active":
                    session["status"] = "suspended"
                    has_change = True
        if has_change:
            self._save_index(index_data)

    def activate_session(self, session_id: str):
        """激活指定 session，暂停其他所有 session"""
        index_data = self._load_index()
        found = False
        for session in index_data["sessions"]:
            if session["session_id"] == session_id:
                session["status"] = "active"
                session["updated_at"] = _now_iso()
                found = True
            else:
                if session.get("status") == "active":
                    session["status"] = "suspended"
        if not found:
            raise ValueError(f"Session {session_id} not found")
        self._save_index(index_data)

    def get_session_status(self, session_id: str) -> str:
        """获取 session 状态"""
        index_data = self._load_index()
        for session in index_data["sessions"]:
            if session.get("session_id") == session_id:
                return session.get("status", "suspended")
        return "not_found"

    def create_session(self) -> str:
        """创建新 session，返回 session_id"""
        session_id = str(uuid.uuid4())
        session_name = session_id  # 初始化为 session_id
        now = _now_iso()

        # 创建 session 文件
        session_file = self.session_dir / f"{session_id}.jsonl"
        session_file.touch()

        # 添加到索引，并确保只有这一个 active session
        index_data = self._load_index()

        # 先暂停所有现有的 active session
        for session in index_data["sessions"]:
            if session.get("status") == "active":
                session["status"] = "suspended"

        # 添加新 session，设置为 active
        index_data["sessions"].append({
            "session_id": session_id,
            "session_name": session_name,
            "agent_id": self.agent_id,
            "created_at": now,
            "updated_at": now,
            "status": "active"
        })
        self._save_index(index_data)
        return session_id

    def delete_session(self, session_id: str):
        """删除指定 session"""
        # 删除 session 文件
        session_file = self.session_dir / f"{session_id}.jsonl"
        if session_file.exists():
            session_file.unlink()

        # 从索引中移除
        index_data = self._load_index()

        # 检查被删除的是否是 active session
        was_active = False
        for session in index_data["sessions"]:
            if session.get("session_id") == session_id and session.get("status") == "active":
                was_active = True
                break

        # 移除要删除的 session
        index_data["sessions"] = [
            s for s in index_data["sessions"]
            if s.get("session_id") != session_id
        ]

        # 如果删除的是 active session，激活 updated_at 最近的 session
        if was_active and index_data["sessions"]:
            # 按 updated_at 降序排序，取第一个
            sorted_sessions = sorted(
                index_data["sessions"],
                key=lambda x: x.get("updated_at", ""),
                reverse=True
            )
            for session in sorted_sessions:
                session["status"] = "active"
                break

        self._save_index(index_data)

    def rename_session(self, session_id: str, new_name: str):
        """重命名指定 session"""
        index_data = self._load_index()
        found = False
        for session in index_data["sessions"]:
            if session.get("session_id") == session_id:
                session["session_name"] = new_name
                session["updated_at"] = _now_iso()
                found = True
                break
        if not found:
            raise ValueError(f"Session {session_id} not found")
        self._save_index(index_data)

    def migrate_sessions(self):
        """迁移旧session，确保所有session都有session_name字段"""
        index_data = self._load_index()
        changed = False
        for session in index_data["sessions"]:
            if "session_name" not in session:
                session["session_name"] = session.get("session_id", "")
                changed = True
        if changed:
            self._save_index(index_data)