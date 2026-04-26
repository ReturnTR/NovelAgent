"""
集中管理的工具

包含：
- bash_executor: Bash 命令执行
- mysql_executor: MySQL 命令执行
- skill_content_reader: 技能内容读取
"""

from .bash_executor import execute_bash, tools as bash_tools
from .skill_content_reader import read_skill_content, tools as skill_tools
from .mysql_executor import execute_remote_mysql_command, tools as mysql_tools

__all__ = [
    "execute_bash",
    "read_skill_content",
    "execute_remote_mysql_command",
    "bash_tools",
    "skill_tools",
    "mysql_tools",
]


def get_all_tools():
    """获取所有集中管理的工具"""
    return bash_tools + skill_tools + mysql_tools
