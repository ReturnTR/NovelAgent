"""
SQLite HTTP 服务

提供 HTTP 接口执行 SQL 语句，供 Agent 通过 A2A 工具调用

启动方式：
    python -m business.db.server
"""

import sqlite3
from pathlib import Path
from typing import Dict, Any, Optional, List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# 添加项目根路径
import sys
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from business.db.config import DB_PATH

app = FastAPI(title="SQLite DB Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SqlRequest(BaseModel):
    sql: str
    params: Optional[List] = None


ALLOWED_SQL_PREFIXES = [
    "select",
    "show",
    "pragma",
    "insert",
    "update",
    "delete",
]


def _is_sql_safe(sql: str) -> bool:
    """SQL 安全检查"""
    sql = (sql or "").strip().lower()
    if not sql:
        return False
    if ";" in sql[:-1]:
        return False
    if any(token in sql for token in ["drop ", "truncate ", "alter ", "grant ", "revoke ", "create "]):
        return False
    return any(sql.startswith(prefix) for prefix in ALLOWED_SQL_PREFIXES)


def _get_connection():
    """获取数据库连接"""
    return sqlite3.connect(DB_PATH)


@app.post("/sql")
def execute_sql(req: SqlRequest) -> Dict[str, Any]:
    """执行 SQL 语句"""
    if not _is_sql_safe(req.sql):
        return {
            "success": False,
            "error": "SQL contains disallowed or potentially dangerous statements",
            "rows": [],
        }

    conn = None
    try:
        conn = _get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        if req.params:
            cursor.execute(req.sql, req.params)
        else:
            cursor.execute(req.sql)

        if cursor.description:
            rows = [dict(row) for row in cursor.fetchall()]
            return {
                "success": True,
                "rows": rows,
                "columns": [desc[0] for desc in cursor.description],
            }
        else:
            conn.commit()
            return {
                "success": True,
                "rows": [],
                "affected": cursor.rowcount,
            }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "rows": [],
        }
    finally:
        if conn:
            conn.close()


@app.get("/health")
def health_check() -> Dict[str, str]:
    """健康检查"""
    try:
        conn = _get_connection()
        conn.execute("SELECT 1")
        conn.close()
        return {"status": "healthy", "database": str(DB_PATH)}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


@app.get("/init")
def init_database() -> Dict[str, Any]:
    """初始化数据库，执行 init.sql"""
    init_sql_path = Path(__file__).parent / "init.sql"
    if not init_sql_path.exists():
        return {"success": False, "error": "init.sql not found"}

    conn = None
    try:
        conn = _get_connection()
        with open(init_sql_path, 'r', encoding='utf-8') as f:
            sql_script = f.read()

        # 使用 executescript 执行完整 SQL 脚本
        conn.executescript(sql_script)
        conn.commit()

        # 验证
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM person")
        count = cursor.fetchone()[0]

        return {
            "success": True,
            "message": f"Database initialized, {count} persons inserted"
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    import uvicorn
    from business.db.config import DB_PORT
    uvicorn.run(app, host="0.0.0.0", port=DB_PORT)
