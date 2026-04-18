import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import uuid

class SessionManager:
    def __init__(self, base_dir: str = "sessions"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(exist_ok=True)
        self.index_file = self.base_dir / "sessions_index.json"
        self._ensure_index_file()
    
    def _ensure_index_file(self):
        """确保索引文件存在"""
        if not self.index_file.exists():
            self._save_index({"sessions": []})
    
    def _load_index(self) -> Dict:
        """加载索引文件"""
        try:
            with open(self.index_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for session in data.get("sessions", []):
                    if "port" not in session:
                        session["port"] = None
                    if "pid" not in session:
                        session["pid"] = None
                return data
        except (FileNotFoundError, json.JSONDecodeError):
            return {"sessions": []}

    def migrate_sessions(self):
        """迁移旧session，确保字段一致性"""
        index_data = self._load_index()
        changed = False
        
        # 迁移到新的字段格式（id -> session_id, 新增 agent_id）
        for session in index_data.get("sessions", []):
            # 1. 迁移字段名 id -> session_id
            if "id" in session and "session_id" not in session:
                session["session_id"] = session["id"]
                del session["id"]
                changed = True
            
            # 2. 确保 agent_id 字段存在
            if "agent_id" not in session:
                # 如果没有 agent_id，生成一个基于类型和随机数的
                agent_type = session.get("agent_type", "unknown")
                # 如果没有 agent_id，我们可以根据 session_id 或者生成新的
                # 这里我们采用类型 + 时间戳（从created_at中取，或者现在的时间）
                created_at = session.get("created_at", datetime.utcnow().isoformat() + "Z")
                # 从创建时间中提取并简化，或者用随机数
                import time
                timestamp = int(time.time() * 1000)
                session["agent_id"] = f"{agent_type}-{timestamp}"
                changed = True
            
            # 3. 确保 port 和 pid 存在
            if "port" not in session:
                session["port"] = None
                changed = True
            if "pid" not in session:
                session["pid"] = None
                changed = True
        
        if changed:
            self._save_index(index_data)
    
    def _save_index(self, index_data: Dict):
        """保存索引文件"""
        with open(self.index_file, 'w', encoding='utf-8') as f:
            json.dump(index_data, f, ensure_ascii=False, indent=2)
    
    def create_session(self, agent_type: str, agent_name: str = None, port: int = None, pid: int = None) -> str:
        """创建新会话"""
        session_id = str(uuid.uuid4())
        # 生成唯一的 agent_id：类型 + 时间戳（毫秒级）
        import time
        timestamp = int(time.time() * 1000)
        agent_id = f"{agent_type}-{timestamp}"
        
        session_file = self.base_dir / f"{session_id}.jsonl"

        now = datetime.utcnow().isoformat() + "Z"

        if agent_name is None:
            agent_name = agent_type.capitalize() + " Agent"

        session_metadata = {
            "type": "session_metadata",
            "version": 4,
            "id": session_id,
            "agent_id": agent_id,
            "created_at": now
        }

        with open(session_file, 'w', encoding='utf-8') as f:
            f.write(json.dumps(session_metadata, ensure_ascii=False) + '\n')

        self._add_to_index(session_id, agent_type, agent_name, agent_id, port=port, pid=pid)

        return session_id

    def create_session_with_info(self, agent_type: str, agent_name: str, port: int, pid: int) -> str:
        """创建带完整信息的会话"""
        return self.create_session(agent_type, agent_name, port=port, pid=pid)
    
    def append_message(self, session_id: str, role: str, content: str, tool_calls: Optional[List[Dict]] = None, tool_results: Optional[List[Dict]] = None, tool_call_id: Optional[str] = None):
        """追加消息到会话文件"""
        session_file = self.base_dir / f"{session_id}.jsonl"

        if not session_file.exists():
            raise FileNotFoundError(f"Session file not found: {session_file}")

        message_event = {
            "type": "message",
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

        if tool_calls:
            message_event["tool_calls"] = tool_calls

        # if tool_results:
        #     message_event["tool_results"] = tool_results

        if tool_call_id:
            message_event["tool_call_id"] = tool_call_id

        with open(session_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(message_event, ensure_ascii=False) + '\n')

        self._update_message_count(session_id)
    
    def append_agent_message(self, session_id: str, role: str, content: str, source_agent_id: str, target_agent_id: str, event_id: Optional[str] = None, task_id: Optional[str] = None):
        """追加Agent间通信消息到会话文件"""
        session_file = self.base_dir / f"{session_id}.jsonl"

        if not session_file.exists():
            raise FileNotFoundError(f"Session file not found: {session_file}")

        message_event = {
            "type": "agent",
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "source_agent_id": source_agent_id,
            "target_agent_id": target_agent_id
        }

        if event_id:
            message_event["event_id"] = event_id
        if task_id:
            message_event["task_id"] = task_id

        with open(session_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(message_event, ensure_ascii=False) + '\n')

        self._update_message_count(session_id)
    
    def get_session(self, session_id: str) -> Optional[Dict]:
        """获取会话详情"""
        session_file = self.base_dir / f"{session_id}.jsonl"
        
        if not session_file.exists():
            return None
        
        events = []
        with open(session_file, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    events.append(json.loads(line))
        
        if not events:
            return None
        
        session_metadata = events[0]
        messages = [e for e in events[1:] if e.get('type') in ['message', 'agent']]
        
        index_data = self._load_index()
        index_entry = next(
            (s for s in index_data.get("sessions", []) 
             if (s.get("session_id") or s.get("id")) == session_id),
            None
        )
        
        if index_entry:
            session_metadata.update({
                "agent_type": index_entry.get("agent_type"),
                "agent_name": index_entry.get("agent_name"),
                "agent_id": index_entry.get("agent_id"),
                "status": index_entry.get("status"),
                "message_count": index_entry.get("message_count"),
                "updated_at": index_entry.get("updated_at")
            })
        
        return {
            "metadata": session_metadata,
            "messages": messages
        }
    
    def get_session_by_id(self, session_id: str) -> Optional[Dict]:
        """通过 session_id 获取会话索引信息"""
        index_data = self._load_index()
        return next(
            (s for s in index_data.get("sessions", []) 
             if (s.get("session_id") or s.get("id")) == session_id),
            None
        )
    
    def get_agent_id(self, session_id: str) -> Optional[str]:
        """通过 session_id 获取对应的 agent_id"""
        session_info = self.get_session_by_id(session_id)
        return session_info.get("agent_id") if session_info else None
    
    def get_session_messages(self, session_id: str) -> List[Dict]:
        """获取会话的所有消息（包括用户消息和Agent间消息）"""
        session = self.get_session(session_id)
        if not session:
            return []
        return session["messages"]
    
    def list_sessions(self, agent_type: str = None, status: str = None) -> List[Dict]:
        """列出会话，可按agent_type和status过滤"""
        index_data = self._load_index()
        sessions = index_data.get("sessions", [])
        
        if agent_type:
            sessions = [s for s in sessions if s.get("agent_type") == agent_type]
        
        if status:
            sessions = [s for s in sessions if s.get("status") == status]
        
        return sorted(sessions, key=lambda x: x.get("updated_at", ""), reverse=True)
    
    def update_session_status(self, session_id: str, status: str):
        """更新会话状态 - 只更新索引文件"""
        self._update_session_in_index(session_id, {"status": status})
    
    def delete_session(self, session_id: str):
        """删除会话"""
        session_file = self.base_dir / f"{session_id}.jsonl"
        
        if session_file.exists():
            session_file.unlink()
        
        self._remove_from_index(session_id)
    
    def _add_to_index(self, session_id: str, agent_type: str, agent_name: str, agent_id: str, port: int = None, pid: int = None):
        """添加会话到索引"""
        index_data = self._load_index()

        now = datetime.utcnow().isoformat() + "Z"

        index_entry = {
            "session_id": session_id,
            "agent_id": agent_id,
            "agent_type": agent_type,
            "agent_name": agent_name,
            "created_at": now,
            "updated_at": now,
            "status": "active",
            "message_count": 0,
            "port": port,
            "pid": pid
        }
        
        index_data["sessions"].append(index_entry)
        self._save_index(index_data)
    
    def _update_session_in_index(self, session_id: str, updates: Dict):
        """更新索引中的会话信息"""
        index_data = self._load_index()
        
        for session in index_data["sessions"]:
            # 兼容新旧两种格式
            session_key = session.get("session_id") or session.get("id")
            if session_key == session_id:
                session.update(updates)
                session["updated_at"] = datetime.utcnow().isoformat() + "Z"
                break
        
        self._save_index(index_data)
    
    def _update_message_count(self, session_id: str):
        """更新会话消息数量（统计所有类型的消息）"""
        session_file = self.base_dir / f"{session_id}.jsonl"
        
        if not session_file.exists():
            return
        
        message_count = 0
        with open(session_file, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    event = json.loads(line)
                    if event.get('type') in ['message', 'agent']:
                        message_count += 1
        
        self._update_session_in_index(session_id, {
            "message_count": message_count,
            "updated_at": datetime.utcnow().isoformat() + "Z"
        })
    
    def _remove_from_index(self, session_id: str):
        """从索引中移除会话"""
        index_data = self._load_index()
        index_data["sessions"] = [
            s for s in index_data["sessions"] 
            if (s.get("session_id") or s.get("id")) != session_id
        ]
        self._save_index(index_data)
    
    def get_or_create_session(self, agent_type: str, agent_name: str = None) -> str:
        """获取或创建会话 - 返回该Agent最新的活跃会话，如果没有则创建新会话"""
        active_sessions = self.list_sessions(agent_type=agent_type, status="active")
        
        if active_sessions:
            return active_sessions[0]["session_id"] or active_sessions[0]["id"]
        
        return self.create_session(agent_type, agent_name)
    
    def update_agent_name(self, agent_type: str, new_name: str):
        """更新某个Agent类型的所有会话中的agent_name"""
        index_data = self._load_index()

        for session in index_data["sessions"]:
            if session.get("agent_type") == agent_type:
                session["agent_name"] = new_name
                session["updated_at"] = datetime.utcnow().isoformat() + "Z"

        self._save_index(index_data)

    def update_session_port_pid(self, session_id: str, port: int, pid: int):
        """更新session的端口和进程ID"""
        self._update_session_in_index(session_id, {"port": port, "pid": pid})

    def update_session_status_by_pid(self, pid: int, status: str):
        """通过PID更新会话状态"""
        index_data = self._load_index()
        for session in index_data["sessions"]:
            if session.get("pid") == pid:
                session["status"] = status
                session["updated_at"] = datetime.utcnow().isoformat() + "Z"
        self._save_index(index_data)

    def get_session_by_pid(self, pid: int) -> Optional[Dict]:
        """通过PID查找会话"""
        index_data = self._load_index()
        for session in index_data["sessions"]:
            if session.get("pid") == pid:
                return session
        return None

    def delete_message_by_index(self, session_id: str, message_index: int):
        """根据消息索引删除会话中的特定消息
        message_index 是 messages 列表中的索引（从 0 开始，排除 session_metadata）
        """
        session_file = self.base_dir / f"{session_id}.jsonl"
        
        if not session_file.exists():
            raise FileNotFoundError(f"Session file not found: {session_file}")
        
        all_lines = []
        with open(session_file, 'r', encoding='utf-8') as f:
            all_lines = [line.rstrip('\n') for line in f]
        
        if not all_lines:
            return
        
        # 找到要删除的行
        # 第一行是 metadata，从第二行开始是 events
        # 我们要找的是第 message_index + 1 行（如果是 message 或 agent 类型）
        events_line_numbers = []
        for i, line in enumerate(all_lines[1:], 1):  # 从索引 1 开始
            if line.strip():
                try:
                    event = json.loads(line)
                    if event.get('type') in ['message', 'agent']:
                        events_line_numbers.append(i)
                except json.JSONDecodeError:
                    continue
        
        if message_index < 0 or message_index >= len(events_line_numbers):
            raise IndexError(f"Message index {message_index} out of range")
        
        # 删除找到的行
        line_to_remove = events_line_numbers[message_index]
        new_lines = [line for i, line in enumerate(all_lines) if i != line_to_remove]
        
        # 写回文件
        with open(session_file, 'w', encoding='utf-8') as f:
            for line in new_lines:
                f.write(line + '\n')
        
        self._update_message_count(session_id)
    
    def sync_sessions_status(self, running_pids: List[int]):
        """同步会话状态：根据实际运行的PID更新状态"""
        index_data = self._load_index()
        for session in index_data["sessions"]:
            if session.get("pid") in running_pids:
                session["status"] = "active"
            else:
                if session.get("status") == "active":
                    session["status"] = "suspended"
            session["updated_at"] = datetime.utcnow().isoformat() + "Z"
        self._save_index(index_data)
