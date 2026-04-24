"""Agent process management - handles Agent lifecycle (start/stop/status)"""
import os
import sys
import subprocess
import signal
import asyncio
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Optional, Set

import psutil
from config import PROJECT_ROOT, SESSION_DIR, PORT_BASE, MAX_PORT

logger = logging.getLogger(__name__)


class AgentProcessManager:
    """Manages Agent processes - start, stop, port allocation"""

    def __init__(self, base_dir: Path, logger: logging.Logger):
        self.base_dir = base_dir
        self.logger = logger
        self.used_ports: Set[int] = set()
        self.session_manager = None  # injected later
        self._sync_ports()

    def _sync_ports(self):
        """Sync already used ports from session manager"""
        if self.session_manager:
            for session in self.session_manager.list_sessions():
                port = session.get("port")
                if port:
                    self.used_ports.add(port)

    def _is_port_in_use(self, port: int) -> bool:
        """Check if port is in use"""
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
        """Get next available port"""
        port = PORT_BASE
        while port in self.used_ports or self._is_port_in_use(port):
            port += 1
            if port > MAX_PORT:
                raise Exception("No available ports")
        self.used_ports.add(port)
        self.logger.debug(f"Port {port} allocated")
        return port

    def release_port(self, port: int):
        """Release port"""
        self.used_ports.discard(port)

    def is_process_running(self, pid: int) -> bool:
        """Check if process is running (not zombie)"""
        try:
            proc = psutil.Process(pid)
            return proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE
        except psutil.NoSuchProcess:
            return False

    def _find_process_by_port(self, port: int) -> Optional[psutil.Process]:
        """Find process by port"""
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
        """Get all running Agent process PIDs"""
        pids = []
        if self.session_manager:
            for session in self.session_manager.list_sessions():
                pid = session.get("pid")
                if pid and self.is_process_running(pid):
                    pids.append(pid)
        return pids

    def _get_venv_python(self) -> str:
        """Get virtual environment python path"""
        venv_python = self.base_dir / "venv" / "bin" / "python"
        if venv_python.exists():
            return str(venv_python)
        return sys.executable

    def start_agent_process(self, session_id: str, agent_type: str, agent_name: str, main_file: str) -> tuple:
        """Start Agent process, returns (port, pid)"""
        self.logger.info(f"Starting agent: type={agent_type}, name={agent_name}")
        main_path = self.base_dir / main_file
        if not main_path.exists():
            raise FileNotFoundError(f"Agent main file not found: {main_path}")

        port = self.get_next_available_port()

        # Get or generate agent_id
        agent_id = None
        if self.session_manager:
            agent_id = self.session_manager.get_agent_id(session_id)
        if not agent_id:
            import time
            agent_id = f"{agent_type}-{int(time.time() * 1000)}"

        try:
            agent_dir = str(main_path.parent)
            env = os.environ.copy()
            env["AGENT_PORT"] = str(port)
            env["AGENT_TYPE"] = agent_type
            env["AGENT_SESSION_ID"] = session_id
            env["AGENT_NAME"] = agent_name
            env["AGENT_ID"] = agent_id
            env["AGENT_DIR"] = agent_dir
            env["PROJECT_ROOT"] = str(self.base_dir)

            # Use conda agent environment
            conda_activate = "source /opt/anaconda3/bin/activate agent && "
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
        """Stop Agent process gracefully"""
        self.logger.info(f"Stopping agent process: pid={pid}")
        try:
            proc = psutil.Process(pid)
            proc.terminate()
            proc.wait(timeout=5)
            self.logger.info(f"Agent process {pid} terminated gracefully")
        except psutil.NoSuchProcess:
            self.logger.warning(f"Process {pid} not found")
        except Exception:
            try:
                proc.kill()
                self.logger.warning(f"Agent process {pid} killed forcefully")
            except:
                pass

    async def check_agent_status(self):
        """Periodically check all Agent processes"""
        self.logger.info("Agent status checker started")
        while True:
            try:
                if self.session_manager:
                    index_data = self.session_manager._load_index()
                    for session in index_data.get("sessions", []):
                        pid = session.get("pid")
                        session_id = session.get("session_id") or session.get("id")
                        if pid:
                            is_running = False
                            try:
                                proc = psutil.Process(pid)
                                is_running = proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE
                            except psutil.NoSuchProcess:
                                is_running = False

                            if not is_running and session.get("status") == "active":
                                port = session.get("port")
                                session["status"] = "suspended"
                                session["pid"] = None
                                session["port"] = None
                                session["updated_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                                if port:
                                    self.release_port(port)
                                self.logger.info(f"Session {session_id} marked as suspended")
                    self.session_manager._save_index(index_data)
            except Exception as e:
                self.logger.error(f"Error checking agent status: {e}")
            await asyncio.sleep(10)