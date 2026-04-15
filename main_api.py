from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from contextlib import asynccontextmanager
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import json
import asyncio
import os
import sys
import subprocess
from pathlib import Path
from dotenv import load_dotenv  # load .env文件
import aiohttp
import psutil
import signal
from agent_commons.sessions.manager import SessionManager

BASE_DIR = Path(__file__).resolve().parent

async def check_agent_status_periodically():
    """定期检查所有Agent进程状态"""
    while True:
        try:
            index_data = session_manager._load_index()
            for session in index_data.get("sessions", []):
                pid = session.get("pid")
                if pid:
                    try:
                        proc = psutil.Process(pid)
                        if not proc.is_running() and session.get("status") == "active":
                            session["status"] = "suspended"
                            session["updated_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                    except psutil.NoSuchProcess:
                        if session.get("status") == "active":
                            session["status"] = "suspended"
                            session["updated_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            session_manager._save_index(index_data)
        except Exception as e:
            print(f"Error checking agent status: {e}")
        await asyncio.sleep(10)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    task = asyncio.create_task(check_agent_status_periodically())
    yield
    task.cancel()

app = FastAPI(title="Novel Agent API", lifespan=lifespan)

load_dotenv()

# 初始化SessionManager
session_manager = SessionManager(base_dir=str(BASE_DIR / "sessions"))
session_manager.migrate_sessions()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "frontend")), name="static")

AGENT_MAIN_FILES = {
    "supervisor": "agents/supervisor_agent/main.py",
    "character": "agents/character_agent/main.py",
    "outline": "agents/outline_agent/main.py",
    "content": "agents/content_agent/main.py",
    "theme": "agents/theme_agent/main.py"
}

PORT_BASE = 8001
MAX_PORT = 9000
USED_PORTS = set()

def get_next_available_port() -> int:
    """获取下一个可用端口"""
    port = PORT_BASE
    while port in USED_PORTS or is_port_in_use(port):
        port += 1
        if port > MAX_PORT:
            raise Exception("No available ports")
    USED_PORTS.add(port)
    return port

def release_port(port: int):
    """释放端口"""
    USED_PORTS.discard(port)

def is_port_in_use(port: int) -> bool:
    """检查端口是否被占用"""
    try:
        result = subprocess.run(
            ["lsof", "-i", f":{port}"],
            capture_output=True,
            text=True
        )
        return len(result.stdout.strip()) > 0
    except:
        return False

def start_agent_process(session_id: str, agent_type: str, agent_name: str) -> tuple:
    """启动Agent进程，返回 (port, pid)"""
    if agent_type not in AGENT_MAIN_FILES:
        raise ValueError(f"Unknown agent type: {agent_type}")

    main_file = AGENT_MAIN_FILES.get(agent_type)
    main_path = BASE_DIR / main_file

    if not main_path.exists():
        raise FileNotFoundError(f"Agent main file not found: {main_path}")

    venv_python = BASE_DIR / "venv" / "bin" / "python"
    if not venv_python.exists():
        venv_python = sys.executable

    port = get_next_available_port()

    try:
        env = os.environ.copy()
        env["AGENT_PORT"] = str(port)
        env["AGENT_TYPE"] = agent_type
        env["AGENT_SESSION_ID"] = session_id
        env["AGENT_NAME"] = agent_name

        proc = subprocess.Popen(
            [str(venv_python), str(main_path)],
            env=env,
            cwd=str(BASE_DIR),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        return port, proc.pid
    except Exception as e:
        release_port(port)
        raise e

def stop_agent_process(pid: int):
    """停止Agent进程"""
    try:
        proc = psutil.Process(pid)
        proc.terminate()
        proc.wait(timeout=5)
    except psutil.NoSuchProcess:
        pass
    except Exception:
        try:
            proc.kill()
        except:
            pass

def find_agent_process_by_port(port: int) -> Optional[psutil.Process]:
    """通过端口查找Agent进程"""
    try:
        result = subprocess.run(
            ["lsof", "-ti", f":{port}"],
            capture_output=True,
            text=True
        )
        if result.stdout.strip():
            pid = int(result.stdout.strip().split('\n')[0])
            return psutil.Process(pid)
    except Exception:
        pass
    return None

def get_all_running_agent_pids() -> List[int]:
    """获取所有运行的Agent进程PID"""
    pids = []
    for session in session_manager.list_sessions():
        pid = session.get("pid")
        if pid and is_process_running(pid):
            pids.append(pid)
    return pids

def is_process_running(pid: int) -> bool:
    """检查进程是否在运行（不包括僵尸进程）"""
    try:
        proc = psutil.Process(pid)
        return proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE
    except psutil.NoSuchProcess:
        return False

# ==================== API Models ====================

class ChatMessage(BaseModel):
    message: str
    history: List[Dict[str, Any]] = []
    session_id: Optional[str] = None

class CreateAgentRequest(BaseModel):
    agent_type: str
    agent_name: str

class AgentInfo(BaseModel):
    agent_type: str
    agent_name: str
    port: int
    status: str
    capabilities: List[Dict[str, Any]]

# ==================== API Endpoints ====================

@app.get("/")
async def root():
    return FileResponse(str(BASE_DIR / "frontend" / "index.html"))

@app.get("/api/agents")
async def list_agents():
    """列出所有Agent - 直接从sessions_index.json读取"""
    session_manager.sync_sessions_status(get_all_running_agent_pids())
    sessions = session_manager.list_sessions()

    agents = []
    for session in sessions:
        port = session.get("port")
        status = "inactive"

        if port:
            try:
                async with aiohttp.ClientSession() as http_session:
                    async with http_session.get(f"http://localhost:{port}/health", timeout=aiohttp.ClientTimeout(total=2)) as response:
                        if response.status == 200:
                            status = "active"
            except:
                pass

        agents.append({
            "agent_type": session.get("agent_type"),
            "agent_name": session.get("agent_name"),
            "port": port,
            "pid": session.get("pid"),
            "status": status,
            "session_id": session.get("id"),
            "updated_at": session.get("updated_at"),
            "message_count": session.get("message_count", 0),
            "capabilities": []
        })

    return {"agents": agents}

@app.post("/api/agents")
async def create_agent(request: CreateAgentRequest):
    """创建新Agent实例"""
    agent_type = request.agent_type
    agent_name = request.agent_name

    if agent_type not in AGENT_MAIN_FILES:
        raise HTTPException(status_code=404, detail=f"Agent type {agent_type} not found")

    session_id = session_manager.create_session(agent_type, agent_name)
    port, pid = start_agent_process(session_id, agent_type, agent_name)
    session_manager.update_session_port_pid(session_id, port, pid)

    return {
        "status": "ok",
        "message": f"Agent {agent_name} created",
        "session_id": session_id,
        "agent_type": agent_type,
        "agent_name": agent_name,
        "port": port,
        "pid": pid
    }

@app.post("/api/agents/{session_id}/suspend")
async def suspend_agent(session_id: str):
    """挂起Agent - 关闭进程并更新状态"""
    session = session_manager.get_session_by_id(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    pid = session.get("pid")
    if pid:
        stop_agent_process(pid)

    port = session.get("port")
    if port:
        release_port(port)

    session_manager.update_session_port_pid(session_id, None, None)
    session_manager.update_session_status(session_id, "suspended")

    return {"status": "ok", "message": f"Agent {session_id} suspended"}

@app.post("/api/agents/{session_id}/resume")
async def resume_agent(session_id: str):
    """恢复Agent - 重新启动进程"""
    session = session_manager.get_session_by_id(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    if session.get("status") != "suspended":
        return {"status": "ok", "message": f"Agent {session_id} is not suspended"}

    pid = session.get("pid")
    if pid and is_process_running(pid):
        return {"status": "ok", "message": f"Agent {session_id} is already running"}

    port, new_pid = start_agent_process(
        session_id,
        session.get("agent_type"),
        session.get("agent_name")
    )
    session_manager.update_session_port_pid(session_id, port, new_pid)
    session_manager.update_session_status(session_id, "active")

    return {
        "status": "ok",
        "message": f"Agent {session_id} resumed",
        "port": port,
        "pid": new_pid
    }

@app.delete("/api/agents/{session_id}")
async def delete_agent(session_id: str):
    """删除Agent - 关闭进程并删除session"""
    session = session_manager.get_session_by_id(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    pid = session.get("pid")
    if pid:
        stop_agent_process(pid)

    port = session.get("port")
    if port:
        release_port(port)

    session_manager.delete_session(session_id)

    return {"status": "ok", "message": f"Agent {session_id} deleted"}

@app.post("/chat/stream")
async def chat_stream(chat_message: ChatMessage):
    """流式聊天接口 - 支持工具调用展示"""
    session_id = chat_message.session_id
    if not session_id:
        return StreamingResponse(
            iter([f"data: {json.dumps({'error': 'session_id is required'}, ensure_ascii=False)}\n\n"]),
            media_type="text/event-stream"
        )

    session = session_manager.get_session_by_id(session_id)
    if not session:
        return StreamingResponse(
            iter([f"data: {json.dumps({'error': f'Session {session_id} not found'}, ensure_ascii=False)}\n\n"]),
            media_type="text/event-stream"
        )

    port = session.get("port")
    if not port:
        return StreamingResponse(
            iter([f"data: {json.dumps({'error': 'Agent is not running, please resume it first'}, ensure_ascii=False)}\n\n"]),
            media_type="text/event-stream"
        )

    async def generate():
        messages_to_save = []  # 收集所有消息用于保存
        
        try:
            # 1. 先保存用户消息
            session_manager.append_message(session_id, "user", chat_message.message)
            messages_to_save.append({"role": "user", "content": chat_message.message})
            
            async with aiohttp.ClientSession() as http_session:
                # 2. 从 session 文件读取完整的 context（而不是使用前端发送的不完整 history）
                session_messages = session_manager.get_session_messages(session_id)
                full_context = []
                for msg in session_messages:
                    item = {"role": msg.get("role")}
                    if msg.get("role") == "user":
                        item["content"] = msg.get("content", "")
                    elif msg.get("role") == "assistant":
                        item["content"] = msg.get("content", "")
                        if msg.get("tool_calls"):
                            item["tool_calls"] = msg["tool_calls"]
                    elif msg.get("role") == "tool":
                        item["content"] = msg.get("content", "")
                        item["tool_call_id"] = msg.get("tool_call_id")
                    full_context.append(item)

                async with http_session.post(
                    f"http://localhost:{port}/a2a/message/stream",
                    json={
                        "message_id": "msg-001",
                        "message_type": "task_request",
                        "sender": "user",
                        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                        "content": {
                            "task": chat_message.message,
                            "context": full_context
                        }
                    },
                    timeout=aiohttp.ClientTimeout(total=120)
                ) as response:
                    if response.status == 200:
                        # 3. 处理 SSE 流
                        async for line in response.content:
                            line = line.decode('utf-8').strip()
                            if not line.startswith('data:'):
                                continue
                            
                            try:
                                data = json.loads(line[5:].strip())
                                event_type = data.get('type')

                                if event_type == 'assistant' or event_type == 'content':
                                    content = data.get('content', '')
                                    session_manager.append_message(session_id, "assistant", content)
                                    yield f"data: {json.dumps({'type': 'content', 'content': content}, ensure_ascii=False)}\n\n"

                                elif event_type == 'tool_call':
                                    tool_calls = data.get('tool_calls', [])
                                    content = data.get('content', '')
                                    session_manager.append_message(session_id, "assistant", content, tool_calls=tool_calls)
                                    yield f"data: {json.dumps({'type': 'tool_call', 'tool_calls': tool_calls}, ensure_ascii=False)}\n\n"

                                elif event_type == 'tool_result':
                                    tool_call_id = data.get('tool_call_id')
                                    content = data.get('content', '')
                                    session_manager.append_message(session_id, "tool", content, tool_call_id=tool_call_id)
                                    yield f"data: {json.dumps({'type': 'tool_result', 'tool_call_id': tool_call_id, 'content': content}, ensure_ascii=False)}\n\n"

                                elif event_type == 'done':
                                    skills_used = data.get('skills_used', [])
                                    yield f"data: {json.dumps({'type': 'done', 'skills_used': skills_used}, ensure_ascii=False)}\n\n"

                                elif event_type == 'error':
                                    yield f"data: {json.dumps({'type': 'error', 'error': data.get('error')}, ensure_ascii=False)}\n\n"

                                else:
                                    print(f'Unknown event type: {event_type}, data: {data}')
                                    
                            except json.JSONDecodeError:
                                continue
                    else:
                        error_msg = f"Agent 响应错误: {response.status}"
                        yield f"data: {json.dumps({'type': 'error', 'error': error_msg}, ensure_ascii=False)}\n\n"

        except aiohttp.ClientError as e:
            import traceback
            tb = traceback.format_exc()
            error_msg = f'连接Agent失败: {str(e)}\n\nTraceback:\n{tb}'
            yield f"data: {json.dumps({'type': 'error', 'error': error_msg}, ensure_ascii=False)}\n\n"
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            error_msg = f'处理失败: {str(e)}\n\nTraceback:\n{tb}'
            yield f"data: {json.dumps({'type': 'error', 'error': error_msg}, ensure_ascii=False)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")

@app.get("/health")
async def health():
    return {"status": "healthy"}

# ==================== 会话管理API ====================

@app.get("/api/sessions")
async def list_sessions(agent_type: str = None, status: str = None):
    """列出所有会话"""
    sessions = session_manager.list_sessions(agent_type=agent_type, status=status)
    return {"sessions": sessions}

@app.post("/api/sessions")
async def create_session(request: CreateAgentRequest):
    """创建新会话并启动Agent进程"""
    agent_type = request.agent_type
    agent_name = request.agent_name

    if agent_type not in AGENT_MAIN_FILES:
        raise HTTPException(status_code=404, detail=f"Agent type {agent_type} not found")

    session_id = session_manager.create_session(agent_type, agent_name)
    port, pid = start_agent_process(session_id, agent_type, agent_name)
    session_manager.update_session_port_pid(session_id, port, pid)

    return {
        "status": "ok",
        "session_id": session_id,
        "agent_type": agent_type,
        "agent_name": agent_name,
        "port": port,
        "pid": pid
    }

@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str):
    """获取会话详情"""
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    return session

@app.get("/api/sessions/{session_id}/messages")
async def get_session_messages(session_id: str):
    """获取会话消息"""
    messages = session_manager.get_session_messages(session_id)
    return {"messages": messages}

@app.post("/api/sessions/{session_id}/messages")
async def append_message(session_id: str, message: Dict[str, Any]):
    """追加消息到会话"""
    role = message.get("role")
    content = message.get("content", "")
    tool_calls = message.get("tool_calls")
    tool_results = message.get("tool_results")

    if not role:
        raise HTTPException(status_code=400, detail="Missing role")

    if not content and not tool_calls and not tool_results:
        raise HTTPException(status_code=400, detail="Missing content, tool_calls, or tool_results")

    session_manager.append_message(session_id, role, content, tool_calls, tool_results)
    return {"status": "ok", "received": {"tool_calls": tool_calls, "tool_results": tool_results}}

@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    """删除会话"""
    session = session_manager.get_session_by_id(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    pid = session.get("pid")
    if pid:
        stop_agent_process(pid)

    port = session.get("port")
    if port:
        release_port(port)

    session_manager.delete_session(session_id)
    return {"status": "ok", "message": f"Session {session_id} deleted"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
