import os
import sqlite3
from pathlib import Path

from src.errors import NotFoundError

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def get_db_path() -> str:
    data_dir = os.environ.get("DATA_DIR", "./data") #configured in the environment and not hard coded.
    Path(data_dir).mkdir(parents=True, exist_ok=True)
    return str(Path(data_dir) / "app.db")


def get_connection(db_path: str | None = None) -> sqlite3.Connection:
    # check_same_thread=False: FastAPI runs sync routes in a thread pool, so the
    # connection may be created in one thread and used in another. That is safe
    # here because every request gets its own private connection.
    conn = sqlite3.connect(db_path or get_db_path(), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.commit()


def get_db():
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


def require_row(conn: sqlite3.Connection, table: str, row_id: int) -> sqlite3.Row:
    """Return the row or raise NotFoundError. `table` must be a hard-coded literal,
    never user input: SQL placeholders cannot be used for table names."""
    row = conn.execute(f"SELECT * FROM {table} WHERE id = ?", (row_id,)).fetchone()
    if row is None:
        raise NotFoundError(f"{table} id {row_id} not found")
    return row