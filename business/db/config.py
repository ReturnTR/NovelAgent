"""数据库配置"""
from pathlib import Path

DB_DIR = Path(__file__).parent
DB_PATH = DB_DIR / "database.db"
DB_PORT = 3307
