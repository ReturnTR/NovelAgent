#!/usr/bin/env python3
import mysql.connector
from mysql.connector import Error
from typing import Dict, Any, List
from langchain_core.tools import tool

ALLOWED_SQL_PREFIXES = [
    "select",
    "show",
    "describe",
    "desc",
    "explain",
    "insert",
    "update",
    "delete"
]
DEFAULT_MYSQL_PASSWORD = "caonima990316"

@tool("execute_remote_mysql_command")
def execute_remote_mysql_command(
    sql_command: str,
    host: str = "127.0.0.1",
    user: str = "root",
    database: str = "NovelWorld",
    port: int = 3306
) -> Dict[str, Any]:
    """
    Execute a SQL command on a remote MySQL server.

    Use this tool when querying or updating MySQL data is needed for task completion.
    Args:
        sql_command: SQL statement to execute.
        host: MySQL host or IP. Default is 127.0.0.1.
        user: MySQL username. Default is root.
        database: Target database name. Default is NovelWorld.
        port: MySQL port. Default is 3306.

    Returns:
        Dict with stable fields:
        - success (bool): Whether execution succeeded.
        - rows (list): Query rows for read SQL.
        - rowcount (int): Affected rows for write SQL.
        - columns (list[str], optional): Column names for read SQL.
        - error (str, optional): Error details when failed.
        - host/database/sql_command (str): Execution context.
    """
    if not _is_sql_safe(sql_command):
        return {
            "success": False,
            "error": "SQL contains disallowed or potentially dangerous statements",
            "rows": [],
            "rowcount": 0,
            "sql_command": sql_command,
            "host": host,
            "database": database
        }

    connection = None
    cursor = None
    rows: List[Any] = []

    try:
        connection = mysql.connector.connect(
            host=host,
            user=user,
            password=DEFAULT_MYSQL_PASSWORD,
            database=database,
            port=port
        )

        if connection.is_connected():
            cursor = connection.cursor(buffered=True)
            cursor.execute(sql_command)

            if cursor.with_rows:
                rows = cursor.fetchall()
                columns = list(cursor.column_names) if cursor.column_names else []
                return {
                    "success": True,
                    "rows": rows,
                    "rowcount": len(rows),
                    "columns": columns,
                    "sql_command": sql_command,
                    "host": host,
                    "database": database
                }
            else:
                connection.commit()
                return {
                    "success": True,
                    "rows": [],
                    "rowcount": cursor.rowcount,
                    "sql_command": sql_command,
                    "host": host,
                    "database": database
                }

        return {
            "success": False,
            "error": "Failed to connect to MySQL server",
            "rows": [],
            "rowcount": 0,
            "sql_command": sql_command,
            "host": host,
            "database": database
        }
    except Error as e:
        return {
            "success": False,
            "error": str(e),
            "rows": [],
            "rowcount": 0,
            "sql_command": sql_command,
            "host": host,
            "database": database
        }
    finally:
        if cursor:
            try:
                cursor.close()
            except Error:
                pass
        if connection and connection.is_connected():
            connection.close()

def _is_sql_safe(sql_command: str) -> bool:
    sql = (sql_command or "").strip().lower()
    if not sql:
        return False
    if ";" in sql[:-1]:
        return False
    if any(token in sql for token in ["drop ", "truncate ", "alter ", "grant ", "revoke "]):
        return False
    return any(sql.startswith(prefix) for prefix in ALLOWED_SQL_PREFIXES)

tools = [
    execute_remote_mysql_command,
]
