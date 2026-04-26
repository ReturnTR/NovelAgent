import subprocess
import os
from typing import Dict, Any, List, Optional
from pathlib import Path
from langchain_core.tools import tool

MAX_TIMEOUT = 30

def _get_allowed_directories() -> List[str]:
    """获取允许的目录列表"""
    allowed = []
    agent_dir = os.getenv("AGENT_DIR")
    if agent_dir:
        allowed.append(agent_dir)
    skills_dir = os.getenv("AGENT_SKILLS_DIR")
    if skills_dir:
        allowed.append(skills_dir)
    project_root = os.getenv("PROJECT_ROOT")
    if project_root:
        allowed.append(project_root)
    if not allowed:
        allowed = [str(Path(__file__).parent.parent.parent.parent)]
    return allowed

ALLOWED_DIRECTORIES = _get_allowed_directories()

@tool("execute_bash")
def execute_bash(command: str, cwd: Optional[str] = None, timeout: int = MAX_TIMEOUT) -> Dict[str, Any]:
    """
    Execute a bash command in a safe sandboxed directory.

    Use this tool when shell execution is required (e.g., run scripts, inspect files, or check command output).
    The command is blocked if it contains dangerous patterns or if the working directory is outside allowed paths.

    Args:
        command: Full bash command to execute.
        cwd: Working directory. Defaults to AGENT_DIR when omitted.
        timeout: Max execution time in seconds. Default is 30.

    Returns:
        Dict with stable fields:
        - success (bool): Whether command completed with exit code 0.
        - stdout (str): Standard output text.
        - stderr (str): Standard error text.
        - returncode (int): Process exit code, -1 when blocked/failed/timeout.
        - command (str): Original input command.
        - cwd (str, optional): Effective working directory when execution started.
        - error (str, optional): Human-readable error when execution is rejected or fails.
    """
    if not cwd:
        cwd = os.getenv("AGENT_DIR", "./")

    if not _is_path_safe(cwd, ALLOWED_DIRECTORIES):
        return {
            "success": False,
            "error": f"路径不在允许范围内: {cwd}",
            "stdout": "",
            "stderr": "",
            "returncode": -1
        }

    if not _is_command_safe(command):
        return {
            "success": False,
            "error": "命令包含不安全的内容",
            "stdout": "",
            "stderr": "",
            "returncode": -1
        }

    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout
        )

        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
            "command": command,
            "cwd": cwd
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": f"命令执行超时（{timeout}秒）",
            "stdout": "",
            "stderr": "",
            "returncode": -1,
            "command": command
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"执行错误: {str(e)}",
            "stdout": "",
            "stderr": "",
            "returncode": -1,
            "command": command
        }

def _is_path_safe(path: str, allowed_dirs: List[str]) -> bool:
    """检查路径是否在允许的目录列表中"""
    try:
        resolved_path = Path(path).resolve()
        for allowed_dir in allowed_dirs:
            allowed_resolved = Path(allowed_dir).resolve()
            if str(resolved_path).startswith(str(allowed_resolved)):
                return True
        return False
    except:
        return False

def _is_command_safe(command: str) -> bool:
    """简单的命令安全检查"""
    dangerous_patterns = [
        "rm -rf /",
        "rm -rf /*",
        "> /dev/sda",
        "mkfs",
        ":(){ :|:& };:",
        "forkbomb"
    ]

    command_lower = command.lower()
    for pattern in dangerous_patterns:
        if pattern.lower() in command_lower:
            return False

    return True

tools = [
    execute_bash,
]
