"""Agent process management - handles Agent lifecycle (start/stop/status)"""
import os
import sys
import subprocess
import signal
import logging
import socket
from pathlib import Path
from datetime import datetime
from typing import Set

import psutil
from web_console.backend.config import PROJECT_ROOT, PORT_BASE, MAX_PORT

logger = logging.getLogger(__name__)


class AgentProcessManager:
    """Manages Agent processes - start, stop, port allocation"""

    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self.used_ports: Set[int] = set()

    def _is_port_in_use(self, port: int) -> bool:
        """Check if port is in use"""
        try:
            with socket.create_connection(("localhost", port), timeout=1):
                return True
        except (socket.timeout, ConnectionRefusedError, OSError):
            return False

    def get_next_available_port(self, preferred_port: int = None) -> int:
        """Get next available port, starting from preferred_port if specified"""
        if preferred_port and preferred_port not in self.used_ports and not self._is_port_in_use(preferred_port):
            self.used_ports.add(preferred_port)
            return preferred_port

        port = PORT_BASE
        while port in self.used_ports or self._is_port_in_use(port):
            port += 1
            if port > MAX_PORT:
                raise Exception("No available ports")
        self.used_ports.add(port)
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

    def _get_venv_python(self) -> str:
        """Get virtual environment python path"""
        venv_python = PROJECT_ROOT / "venv" / "bin" / "python"
        if venv_python.exists():
            return str(venv_python)
        return sys.executable

    def start_agent_process(self, agent_id: str, agent_type: str, agent_name: str,
                           main_file: str, port: int) -> int:
        """Start Agent process, returns pid"""
        self.logger.info(f"Starting agent: id={agent_id}, type={agent_type}, port={port}")

        main_path = PROJECT_ROOT / main_file
        if not main_path.exists():
            raise FileNotFoundError(f"Agent main file not found: {main_path}")

        try:
            agent_dir = Path(main_path).parent
            log_dir = agent_dir / "logs"
            log_dir.mkdir(exist_ok=True)
            log_file = log_dir / f"{datetime.now().strftime('%Y%m%d')}.log"
            log_fd = open(log_file, "a", encoding="utf-8")

            env = os.environ.copy()
            env["AGENT_ID"] = agent_id
            env["AGENT_TYPE"] = agent_type
            env["AGENT_NAME"] = agent_name
            env["AGENT_PORT"] = str(port)
            env["AGENT_DIR"] = str(agent_dir)
            env["PROJECT_ROOT"] = str(PROJECT_ROOT)

            # Use conda agent environment
            conda_activate = "source /opt/anaconda3/bin/activate agent && "
            proc = subprocess.Popen(
                ["bash", "-c", conda_activate + f"cd {str(PROJECT_ROOT)} && python {str(main_path)}"],
                env=env,
                cwd=str(PROJECT_ROOT),
                stdout=log_fd,
                stderr=subprocess.STDOUT,
                start_new_session=True
            )

            # Get actual python process PID reliably using pgrep
            import time
            import subprocess as subproc
            actual_pid = None
            for _ in range(10):  # Retry 10 times within 1 second
                try:
                    result = subproc.run(
                        ["pgrep", "-P", str(proc.pid)],
                        capture_output=True, text=True, timeout=1
                    )
                    if result.stdout.strip():
                        actual_pid = int(result.stdout.strip().split()[0])
                        break
                except Exception:
                    pass
                time.sleep(0.1)

            if not actual_pid:
                # Fallback: find python process by command line
                try:
                    result = subproc.run(
                        ["pgrep", "-f", f"python.*{main_path.name}"],
                        capture_output=True, text=True, timeout=1
                    )
                    if result.stdout.strip():
                        actual_pid = int(result.stdout.strip().split()[0])
                except Exception:
                    pass

            if not actual_pid:
                actual_pid = proc.pid  # Last resort fallback

            self.logger.info(f"Agent started: python_pid={actual_pid}, port={port}, log={log_file}")
            return actual_pid
        except Exception as e:
            self.release_port(port)
            self.logger.error(f"Failed to start agent: {e}")
            raise e

    def stop_agent_process(self, pid: int):
        """Stop Agent process - kill the entire process group"""
        self.logger.info(f"Stopping agent process group: pid={pid}")
        try:
            import signal
            # Kill entire process group (since we use start_new_session=True)
            os.killpg(pid, signal.SIGTERM)
            self.logger.info(f"Agent process group {pid} terminated")
        except ProcessLookupError:
            self.logger.warning(f"Process group {pid} not found - may have already exited")
        except PermissionError:
            # Fallback to psutil kill
            try:
                proc = psutil.Process(pid)
                proc.kill()
                self.logger.info(f"Agent process {pid} killed via psutil")
            except psutil.NoSuchProcess:
                self.logger.warning(f"Process {pid} not found")
        except Exception as e:
            self.logger.error(f"Error stopping process {pid}: {e}")