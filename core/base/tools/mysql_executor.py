#!/usr/bin/env python3
import os
from typing import Dict, Any
from langchain_core.tools import tool

import requests

ALLOWED_SQL_PREFIXES = [
    "select",
    "show",
    "pragma",
    "insert",
    "update",
    "delete"
]


@tool("execute_remote_mysql_command")
def execute_remote_mysql_command(
    sql_command: str,
    host: str = "127.0.0.1",
    port: int = 3307
) -> Dict[str, Any]:
    """
    Execute a SQL command on the SQLite database server.

    Use this tool when querying or updating database is needed for task completion.

    Args:
        sql_command: SQL statement to execute.
        host: Database server host. Default is 127.0.0.1.
        port: Database server port. Default is 3307.

    Returns:
        Dict with stable fields:
        - success (bool): Whether execution succeeded.
        - rows (list): Query rows for read SQL.
        - columns (list[str], optional): Column names for read SQL.
        - affected (int): Affected rows for write SQL.
        - error (str, optional): Error details when failed.
    """
    if not _is_sql_safe(sql_command):
        return {
            "success": False,
            "error": "SQL contains disallowed or potentially dangerous statements",
            "rows": [],
        }

    db_endpoint = f"http://{host}:{port}"
    try:
        response = requests.post(
            f"{db_endpoint}/sql",
            json={"sql": sql_command, "params": None},
            timeout=30
        )

        if response.status_code == 200:
            return response.json()
        else:
            return {
                "success": False,
                "error": f"HTTP {response.status_code}: {response.text}",
                "rows": [],
            }

    except requests.exceptions.ConnectionError:
        return {
            "success": False,
            "error": f"Cannot connect to DB server at {db_endpoint}. Make sure the DB server is running.",
            "rows": [],
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "rows": [],
        }


def _is_sql_safe(sql_command: str) -> bool:
    sql = (sql_command or "").strip().lower()
    if not sql:
        return False
    if ";" in sql[:-1]:
        return False
    if any(token in sql for token in ["drop ", "truncate ", "alter ", "grant ", "revoke ", "create "]):
        return False
    return any(sql.startswith(prefix) for prefix in ALLOWED_SQL_PREFIXES)


tools = [
    execute_remote_mysql_command,
]
