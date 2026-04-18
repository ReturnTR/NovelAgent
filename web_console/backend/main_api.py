import os
import sys
import json
import asyncio
import subprocess
import signal
import argparse
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

import psutil
import aiohttp
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent.parent.parent
PROJECT_ROOT = BASE_DIR
# 确保 agent 模块能被找到
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / 'agent'))

from agent.core.session.manager import SessionManager
from agent.core.a2a import get_registry


def setup_logging(debug: bool = False):
    """配置日志"""
    level = logging.DEBUG if debug else logging.INFO
    format_str = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    handlers = [logging.StreamHandler()]
    if debug:
        handlers.append(logging.FileHandler('api_debug.log'))
    logging.basicConfig(level=level, format=format_str, handlers=handlers)
    return logging.getLogger(__name__)


class AgentProcessManager:
    """Agent进程管理器"""

    PORT_BASE = 8001
    MAX_PORT = 9000

    def __init__(self, base_dir: Path, logger: logging.Logger):
        self.base_dir = base_dir
        self.logger = logger
        self.used_ports: set[int] = set()
        self.session_manager = SessionManager(
            base_dir=str(base_dir / "web_console" / "backend" / "sessions")
        )
        self.session_manager.migrate_sessions()
        self._sync_ports()

    def _sync_ports(self):
        """同步已使用的端口"""
        for session in self.session_manager.list_sessions():
            port = session.get("port")
            if port:
                self.used_ports.add(port)

    def _is_port_in_use(self, port: int) -> bool:
        """检查端口是否被占用"""
        try:
            result = subprocess.run(
                ["lsof", "-i", f":{port}"],
                capture_output=True,
                text=True
            )
            return len(result.stdout.strip()) > 0
        except Exception:
            return False

    def get_next_available_port(self) -> int:
        """获取下一个可用端口"""
        port = self.PORT_BASE
        while port in self.used_ports or self._is_port_in_use(port):
            port += 1
            if port > self.MAX_PORT:
                raise Exception("No available ports")
        self.used_ports.add(port)
        self.logger.debug(f"Port {port} allocated, used_ports: {self.used_ports}")
        return port

    def release_port(self, port: int):
        """释放端口"""
        self.used_ports.discard(port)
        self.logger.debug(f"Port {port} released, used_ports: {self.used_ports}")

    def is_process_running(self, pid: int) -> bool:
        """检查进程是否在运行（不包括僵尸进程）"""
        try:
            proc = psutil.Process(pid)
            return proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE
        except psutil.NoSuchProcess:
            return False

    def _find_process_by_port(self, port: int) -> Optional[psutil.Process]:
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

    def _get_all_running_pids(self) -> List[int]:
        """获取所有运行的Agent进程PID"""
        pids = []
        for session in self.session_manager.list_sessions():
            pid = session.get("pid")
            if pid and self.is_process_running(pid):
                pids.append(pid)
        return pids

    def _get_venv_python(self) -> str:
        """获取虚拟环境python路径"""
        venv_python = self.base_dir / "venv" / "bin" / "python"
        if venv_python.exists():
            return str(venv_python)
        return sys.executable

    def start_agent_process(self, session_id: str, agent_type: str, agent_name: str, main_file: str) -> tuple:
        """启动Agent进程，返回 (port, pid)"""
        self.logger.info(f"Starting agent: type={agent_type}, name={agent_name}, session={session_id}")
        main_path = self.base_dir / main_file
        if not main_path.exists():
            raise FileNotFoundError(f"Agent main file not found: {main_path}")

        port = self.get_next_available_port()

        try:
            env = os.environ.copy()
            env["AGENT_PORT"] = str(port)
            env["AGENT_TYPE"] = agent_type
            env["AGENT_SESSION_ID"] = session_id
            env["AGENT_NAME"] = agent_name

            # 使用conda的agent环境启动Agent
            conda_activate = "source ~/miniconda3/bin/activate agent && "
            proc = subprocess.Popen(
                ["bash", "-c", conda_activate + f"cd {str(self.base_dir)} && python {str(main_path)}"],
                env=env,
                cwd=str(self.base_dir),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            self.logger.info(f"Agent started: pid={proc.pid}, port={port}")
            return port, proc.pid
        except Exception as e:
            self.release_port(port)
            self.logger.error(f"Failed to start agent: {e}")
            raise e

    def stop_agent_process(self, pid: int):
        """停止Agent进程"""
        self.logger.info(f"Stopping agent process: pid={pid}")
        try:
            proc = psutil.Process(pid)
            proc.terminate()
            proc.wait(timeout=5)
            self.logger.info(f"Agent process {pid} terminated gracefully")
        except psutil.NoSuchProcess:
            self.logger.warning(f"Process {pid} not found")
            pass
        except Exception:
            try:
                proc.kill()
                self.logger.warning(f"Agent process {pid} killed forcefully")
            except:
                pass

    async def check_agent_status(self):
        """定期检查所有Agent进程状态"""
        self.logger.info("Agent status checker started")
        while True:
            try:
                index_data = self.session_manager._load_index()
                for session in index_data.get("sessions", []):
                    pid = session.get("pid")
                    if pid:
                        try:
                            proc = psutil.Process(pid)
                            if not proc.is_running() and session.get("status") == "active":
                                session["status"] = "suspended"
                                session["updated_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                                self.logger.info(f"Session {session.get('id')} marked as suspended (process not running)")
                        except psutil.NoSuchProcess:
                            if session.get("status") == "active":
                                session["status"] = "suspended"
                                session["updated_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                                self.logger.info(f"Session {session.get('id')} marked as suspended (NoSuchProcess)")
                self.session_manager._save_index(index_data)
            except Exception as e:
                self.logger.error(f"Error checking agent status: {e}")
            await asyncio.sleep(10)


class AgentService:
    """Agent服务类"""

    AGENT_MAIN_FILES = {
        "supervisor": "agent/agent_instances/supervisor_agent/main.py",
        "character": "agent/agent_instances/character_agent/main.py",
    }

    def __init__(self, process_manager: AgentProcessManager, logger: logging.Logger):
        self.process_manager = process_manager
        self.session_manager = process_manager.session_manager
        self.logger = logger

    async def list_agents(self) -> List[Dict[str, Any]]:
        """列出所有Agent"""
        self.logger.debug("Listing all agents")
        self.session_manager.sync_sessions_status(self.process_manager._get_all_running_pids())
        sessions = self.session_manager.list_sessions()

        agents = []
        for session in sessions:
            port = session.get("port")
            status = "inactive"

            if port:
                try:
                    async with aiohttp.ClientSession() as http_session:
                        async with http_session.get(
                            f"http://localhost:{port}/a2a/health",
                            timeout=aiohttp.ClientTimeout(total=2)
                        ) as response:
                            if response.status == 200:
                                status = "active"
                except Exception:
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

        self.logger.debug(f"Found {len(agents)} agents")
        return agents

    def create_agent(self, agent_type: str, agent_name: str) -> Dict[str, Any]:
        """创建新Agent实例"""
        self.logger.info(f"Creating agent: type={agent_type}, name={agent_name}")
        if agent_type not in self.AGENT_MAIN_FILES:
            raise ValueError(f"Unknown agent type: {agent_type}")

        session_id = self.session_manager.create_session(agent_type, agent_name)
        port, pid = self.process_manager.start_agent_process(
            session_id, agent_type, agent_name, self.AGENT_MAIN_FILES[agent_type]
        )
        self.session_manager.update_session_port_pid(session_id, port, pid)

        result = {
            "status": "ok",
            "message": f"Agent {agent_name} created",
            "session_id": session_id,
            "agent_type": agent_type,
            "agent_name": agent_name,
            "port": port,
            "pid": pid
        }
        self.logger.info(f"Agent created successfully: {result}")
        return result

    def suspend_agent(self, session_id: str) -> Dict[str, Any]:
        """挂起Agent"""
        self.logger.info(f"Suspending agent: session_id={session_id}")
        session = self.session_manager.get_session_by_id(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        pid = session.get("pid")
        if pid:
            self.process_manager.stop_agent_process(pid)

        port = session.get("port")
        if port:
            self.process_manager.release_port(port)

        self.session_manager.update_session_port_pid(session_id, None, None)
        self.session_manager.update_session_status(session_id, "suspended")

        self.logger.info(f"Agent {session_id} suspended")
        return {"status": "ok", "message": f"Agent {session_id} suspended"}

    def resume_agent(self, session_id: str) -> Dict[str, Any]:
        """恢复Agent"""
        self.logger.info(f"Resuming agent: session_id={session_id}")
        session = self.session_manager.get_session_by_id(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        if session.get("status") != "suspended":
            return {"status": "ok", "message": f"Agent {session_id} is not suspended"}

        pid = session.get("pid")
        if pid and self.process_manager.is_process_running(pid):
            return {"status": "ok", "message": f"Agent {session_id} is already running"}

        agent_type = session.get("agent_type")
        port, new_pid = self.process_manager.start_agent_process(
            session_id,
            agent_type,
            session.get("agent_name"),
            self.AGENT_MAIN_FILES.get(agent_type, "")
        )
        self.session_manager.update_session_port_pid(session_id, port, new_pid)
        self.session_manager.update_session_status(session_id, "active")

        result = {
            "status": "ok",
            "message": f"Agent {session_id} resumed",
            "port": port,
            "pid": new_pid
        }
        self.logger.info(f"Agent {session_id} resumed: {result}")
        return result

    def delete_agent(self, session_id: str) -> Dict[str, Any]:
        """删除Agent"""
        self.logger.info(f"Deleting agent: session_id={session_id}")
        session = self.session_manager.get_session_by_id(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        pid = session.get("pid")
        if pid:
            self.process_manager.stop_agent_process(pid)

        port = session.get("port")
        if port:
            self.process_manager.release_port(port)

        self.session_manager.delete_session(session_id)

        self.logger.info(f"Agent {session_id} deleted")
        return {"status": "ok", "message": f"Agent {session_id} deleted"}

    async def chat_stream(self, session_id: str, message: str):
        """流式聊天"""
        self.logger.info(f"Chat stream: session_id={session_id}, message={message[:50]}...")
        session = self.session_manager.get_session_by_id(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        port = session.get("port")
        if not port:
            raise ValueError("Agent is not running, please resume it first")

        self.session_manager.append_message(session_id, "user", message)

        session_messages = self.session_manager.get_session_messages(session_id)
        self.logger.debug(f"Session messages count: {len(session_messages)}")

        async def generate():
            try:
                self.logger.debug(f"Sending request to agent at port {port}")
                async with aiohttp.ClientSession() as http_session:
                    async with http_session.post(
                        f"http://localhost:{port}/chat/stream",
                        json={
                            "task": message,
                            "context": session_messages
                        },
                        timeout=aiohttp.ClientTimeout(total=120)
                    ) as response:
                        self.logger.debug(f"Agent response status: {response.status}")
                        if response.status == 200:
                            async for line in response.content:
                                line = line.decode('utf-8').strip()
                                if not line.startswith('data:'):
                                    continue

                                try:
                                    data = json.loads(line[5:].strip())
                                    event_type = data.get('type')
                                    self.logger.debug(f"Event type: {event_type}")

                                    if event_type in ('assistant', 'content'):
                                        content = data.get('content', '')
                                        self.session_manager.append_message(session_id, "assistant", content)
                                        yield f"data: {json.dumps({'type': 'content', 'content': content}, ensure_ascii=False)}\n\n"

                                    elif event_type == 'tool_call':
                                        tool_calls = data.get('tool_calls', [])
                                        content = data.get('content', '')
                                        self.session_manager.append_message(session_id, "assistant", content, tool_calls=tool_calls)
                                        self.logger.debug(f"Tool call: {tool_calls}")
                                        yield f"data: {json.dumps({'type': 'tool_call', 'tool_calls': tool_calls}, ensure_ascii=False)}\n\n"

                                    elif event_type == 'tool_result':
                                        tool_call_id = data.get('tool_call_id')
                                        content = data.get('content', '')
                                        self.session_manager.append_message(session_id, "tool", content, tool_call_id=tool_call_id)
                                        self.logger.debug(f"Tool result: tool_call_id={tool_call_id}")
                                        yield f"data: {json.dumps({'type': 'tool_result', 'tool_call_id': tool_call_id, 'content': content}, ensure_ascii=False)}\n\n"

                                    elif event_type == 'done':
                                        yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"

                                    elif event_type == 'error':
                                        error = data.get('error')
                                        self.logger.error(f"Agent error: {error}")
                                        yield f"data: {json.dumps({'type': 'error', 'error': error}, ensure_ascii=False)}\n\n"

                                    else:
                                        self.logger.warning(f'Unknown event type: {event_type}, data: {data}')

                                    self.logger.debug(f"Agent response session content: {content}")
                                except json.JSONDecodeError:
                                    continue
                        else:
                            error_msg = f"Agent 响应错误: {response.status}"
                            self.logger.error(error_msg)
                            yield f"data: {json.dumps({'type': 'error', 'error': error_msg}, ensure_ascii=False)}\n\n"

            except aiohttp.ClientError as e:
                import traceback
                tb = traceback.format_exc()
                error_msg = f'连接Agent失败: {str(e)}'
                self.logger.error(f"{error_msg}\n{tb}")
                yield f"data: {json.dumps({'type': 'error', 'error': error_msg}, ensure_ascii=False)}\n\n"
            except Exception as e:
                import traceback
                tb = traceback.format_exc()
                error_msg = f'处理失败: {str(e)}'
                self.logger.error(f"{error_msg}\n{tb}")
                yield f"data: {json.dumps({'type': 'error', 'error': error_msg}, ensure_ascii=False)}\n\n"

        return StreamingResponse(generate(), media_type="text/event-stream")


class ChatMessage(BaseModel):
    message: str
    history: List[Dict[str, Any]] = []
    session_id: Optional[str] = None


class CreateAgentRequest(BaseModel):
    agent_type: str
    agent_name: str


class MessageModel(BaseModel):
    role: str
    content: Optional[str] = ""
    tool_calls: Optional[List[Dict]] = None
    tool_results: Optional[List[Dict]] = None


def create_app(debug: bool = False) -> tuple[FastAPI, AgentService, logging.Logger]:
    """创建FastAPI应用和Agent服务"""
    logger = setup_logging(debug)
    logger.info(f"Creating app with debug={debug}")

    app = FastAPI(title="Novel Agent API")
    process_manager = AgentProcessManager(BASE_DIR, logger)
    agent_service = AgentService(process_manager, logger)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.mount("/static", StaticFiles(directory=str(BASE_DIR / "web_console" / "frontend")), name="static")

    @app.on_event("startup")
    async def startup():
        logger.info("Application startup")
        asyncio.create_task(process_manager.check_agent_status())

    # ========================================================================
    # 注册中心接口
    # 提供 Agent 注册、发现、搜索等功能
    # ========================================================================

    @app.get("/api/registry/agents")
    async def registry_list_agents():
        """
        列出所有已注册的 Agent

        返回注册中心中所有活跃的 Agent 列表
        """
        registry = get_registry()
        agents = await registry.list_agents()
        return {"count": len(agents), "agents": [agent.model_dump() for agent in agents]}

    @app.get("/api/registry/agents/{agent_id}")
    async def registry_get_agent(agent_id: str):
        """
        获取特定 Agent 的信息

        Args:
            agent_id: Agent ID

        Returns:
            AgentCard 信息
        """
        registry = get_registry()
        agent = await registry.get_agent(agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        return agent.model_dump()

    @app.get("/api/registry/search")
    async def registry_search_agents(keywords: Optional[str] = None, agent_type: Optional[str] = None):
        """
        搜索 Agent

        支持关键词搜索和类型筛选：
        - keywords: 匹配 Agent 名称、描述、能力
        - agent_type: 按类型筛选

        Args:
            keywords: 搜索关键词
            agent_type: Agent 类型
        """
        from agent.core.a2a import AgentCard
        
        # 第一步：从 SessionManager 获取所有活跃的 Agent
        active_sessions = []
        for session in agent_service.session_manager.list_sessions():
            if session.get("status") == "active" and session.get("port"):
                active_sessions.append(session)
        
        # 第二步：对每个活跃 Agent，请求它的 /a2a/.well-known/agent-card.json 获取 AgentCard
        agents = []
        for session in active_sessions:
            port = session.get("port")
            try:
                async with aiohttp.ClientSession() as http_session:
                    async with http_session.get(
                        f"http://localhost:{port}/a2a/.well-known/agent-card.json",
                        timeout=aiohttp.ClientTimeout(total=2)
                    ) as response:
                        if response.status == 200:
                            agent_card_data = await response.json()
                            agent_card = AgentCard(**agent_card_data)
                            agents.append(agent_card)
            except Exception as e:
                logger.debug(f"Failed to get agent card from port {port}: {e}")
        
        # 第三步：应用筛选
        filtered_agents = []
        for agent in agents:
            # 按类型筛选
            if agent_type and agent.agent_type != agent_type:
                continue
            # 按关键词筛选
            if keywords:
                keywords_lower = keywords.lower()
                match = False
                if keywords_lower in agent.agent_name.lower():
                    match = True
                elif keywords_lower in agent.description.lower():
                    match = True
                else:
                    for cap in agent.capabilities:
                        if keywords_lower in cap.name.lower() or keywords_lower in cap.description.lower():
                            match = True
                            break
                if not match:
                    continue
            filtered_agents.append(agent)
        
        return {"count": len(filtered_agents), "agents": [agent.model_dump() for agent in filtered_agents]}

    @app.post("/api/registry/register")
    async def registry_register_agent(request: Request):
        """
        注册一个新的 Agent

        手动注册接口，通常 Agent 启动时自动注册

        请求体：
        {
            "agent_id": "agent-001",
            "agent_name": "Agent Name",
            "agent_type": "character",
            "endpoint": "http://localhost:8001",
            "capabilities": [...]
        }
        """
        registry = get_registry()
        data = await request.json()
        from agent.core.a2a import AgentCard
        agent_card = AgentCard(**data)
        await registry.register_agent(agent_card)
        return {"status": "ok", "agent_id": agent_card.agent_id}

    @app.get("/")
    async def root():
        return FileResponse(str(BASE_DIR / "web_console" / "frontend" / "index.html"))

    @app.get("/api/agents")
    async def list_agents():
        agents = await agent_service.list_agents()
        return {"agents": agents}

    @app.post("/api/agents")
    async def create_agent(request: CreateAgentRequest):
        try:
            result = agent_service.create_agent(request.agent_type, request.agent_name)
            return result
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))

    @app.post("/api/agents/{session_id}/suspend")
    async def suspend_agent(session_id: str):
        try:
            result = agent_service.suspend_agent(session_id)
            return result
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))

    @app.post("/api/agents/{session_id}/resume")
    async def resume_agent(session_id: str):
        try:
            result = agent_service.resume_agent(session_id)
            return result
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))

    @app.delete("/api/agents/{session_id}")
    async def delete_agent(session_id: str):
        try:
            result = agent_service.delete_agent(session_id)
            return result
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))

    @app.post("/chat/stream")
    async def chat_stream(chat_message: ChatMessage):
        if not chat_message.session_id:
            return StreamingResponse(
                iter([f"data: {json.dumps({'error': 'session_id is required'}, ensure_ascii=False)}\n\n"]),
                media_type="text/event-stream"
            )
        try:
            return await agent_service.chat_stream(chat_message.session_id, chat_message.message)
        except ValueError as e:
            return StreamingResponse(
                iter([f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"]),
                media_type="text/event-stream"
            )

    @app.get("/health")
    async def health():
        return {"status": "healthy"}

    @app.get("/api/sessions")
    async def list_sessions(agent_type: str = None, status: str = None):
        sessions = agent_service.session_manager.list_sessions(agent_type=agent_type, status=status)
        return {"sessions": sessions}

    @app.post("/api/sessions")
    async def create_session(request: CreateAgentRequest):
        try:
            result = agent_service.create_agent(request.agent_type, request.agent_name)
            return result
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))

    @app.get("/api/sessions/{session_id}")
    async def get_session(session_id: str):
        session = agent_service.session_manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
        return session

    @app.post("/api/sessions/{session_id}/agent-message")
    async def append_agent_message(session_id: str, request: Request):
        """
        Agent间通信消息记录接口

        让Agent可以通过HTTP调用将接收到的Agent间通信消息记录到Session中

        请求体：
        {
            "role": "user" or "assistant",
            "content": "消息内容",
            "source_agent_id": "发送者Agent ID",
            "target_agent_id": "接收者Agent ID",
            "event_id": "事件ID（可选）",
            "task_id": "任务ID（可选）"
        }
        """
        try:
            data = await request.json()
            role = data.get("role", "user")
            content = data.get("content", "")
            source_agent_id = data.get("source_agent_id", "")
            target_agent_id = data.get("target_agent_id", "")
            event_id = data.get("event_id")
            task_id = data.get("task_id")

            agent_service.session_manager.append_agent_message(
                session_id,
                role,
                content,
                source_agent_id,
                target_agent_id,
                event_id,
                task_id
            )

            return {"status": "ok", "message": "Agent message appended"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/sessions/{session_id}/messages")
    async def get_session_messages(session_id: str):
        messages = agent_service.session_manager.get_session_messages(session_id)
        return {"messages": messages}

    @app.post("/api/sessions/{session_id}/messages")
    async def append_message(session_id: str, message: MessageModel):
        role = message.role
        content = message.content or ""
        tool_calls = message.tool_calls
        tool_results = message.tool_results

        if not role:
            raise HTTPException(status_code=400, detail="Missing role")

        if not content and not tool_calls and not tool_results:
            raise HTTPException(status_code=400, detail="Missing content, tool_calls, or tool_results")

        agent_service.session_manager.append_message(session_id, role, content, tool_calls, tool_results)
        return {"status": "ok", "received": {"tool_calls": tool_calls, "tool_results": tool_results}}

    @app.delete("/api/sessions/{session_id}")
    async def delete_session(session_id: str):
        try:
            result = agent_service.delete_agent(session_id)
            return result
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))

    return app, agent_service, logger


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Novel Agent API Server")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    args = parser.parse_args()

    import uvicorn
    app, _, logger = create_app(debug=args.debug)
    logger.info(f"Starting server on port 8000, debug={args.debug}")
    uvicorn.run(app, host="0.0.0.0", port=8000)
