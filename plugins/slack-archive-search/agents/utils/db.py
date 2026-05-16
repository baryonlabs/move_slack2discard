"""
agents/utils/db.py
Shared database utilities
"""
import sqlite3
from pathlib import Path

def get_db_connection(db_path: str = "./data/archive.db") -> sqlite3.Connection:
    """Create SQLite connection with WAL mode and row factory"""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn
