import os
import sqlite3
from pathlib import Path

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def get_db_path() -> str:
    data_dir = os.environ.get("DATA_DIR", "./data")
    Path(data_dir).mkdir(parents=True, exist_ok=True)
    return str(Path(data_dir) / "app.db")


def get_connection(db_path: str | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path or get_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()


def get_db():
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()