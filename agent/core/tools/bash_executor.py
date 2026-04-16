import subprocess
import json
from typing import Dict, Any, List, Optional, Callable
from pathlib import Path

ALLOWED_DIRECTORIES = [
    "./"
]

MAX_TIMEOUT = 30

def execute_bash(command: str, cwd: Optional[str] = None, timeout: int = MAX_TIMEOUT) -> Dict[str, Any]:
    """
    执行bash命令并返回结果

    参数:
        command: 要执行的bash命令
        cwd: 工作目录，默认为项目根目录
        timeout: 超时时间（秒），默认30秒

    返回:
        包含执行结果的字典
    """
    if not cwd:
        cwd = "./"

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

def list_directory(path: str = ".") -> Dict[str, Any]:
    """
    列出目录内容

    参数:
        path: 目录路径，相对于项目根目录

    返回:
        目录内容列表
    """
    base_dir = Path("./")
    target_dir = (base_dir / path).resolve()

    if not str(target_dir).startswith(str(base_dir)):
        return {
            "success": False,
            "error": "路径不在允许范围内"
        }

    try:
        items = []
        for item in target_dir.iterdir():
            items.append({
                "name": item.name,
                "type": "directory" if item.is_dir() else "file",
                "size": item.stat().st_size if item.is_file() else 0
            })

        return {
            "success": True,
            "path": str(target_dir),
            "items": sorted(items, key=lambda x: (x["type"] != "directory", x["name"]))
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

tools = [
    execute_bash,
    list_directory
]
