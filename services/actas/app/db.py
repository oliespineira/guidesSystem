import os
import time
from urllib.parse import unquote, urlparse

import pymssql
IntegrityError = pymssql.IntegrityError   # re-exported, so the services never import the driver themselves

from app.errors import NotFoundError


class Row(dict):
    """One result row. Read by column name (row["name"]) or by position (row[0]), like sqlite3.Row."""

    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


class Cursor:
    """Wraps a pymssql cursor so it returns Row objects."""

    def __init__(self, cursor):
        self._cursor = cursor

    def _row(self, values):
        names = [column[0] for column in self._cursor.description]
        return Row(zip(names, values))

    def fetchone(self):
        values = self._cursor.fetchone()
        return None if values is None else self._row(values)

    def fetchall(self):
        return [self._row(values) for values in self._cursor.fetchall()]

    def __iter__(self):
        return iter(self.fetchall())

    @property
    def rowcount(self):
        return self._cursor.rowcount

    @property
    def lastrowid(self):
        return self._cursor.lastrowid


class Connection:
    """Wraps a pymssql connection so the services keep sqlite3's conn.execute(sql, params) style."""

    def __init__(self, raw):
        self._raw = raw

    def execute(self, sql: str, params=()) -> Cursor:
        cursor = self._raw.cursor()
        cursor.execute(sql.replace("?", "%s"), tuple(params) or None)
        return Cursor(cursor)

    def commit(self):
        self._raw.commit()

    def rollback(self):
        self._raw.rollback()

    def close(self):
        self._raw.close()


def _connect_args() -> dict:
    url = urlparse(os.environ["DATABASE_URL"])   # mssql://user:password@host:port/database
    return {
        "server": url.hostname,
        "port": url.port or 1433,
        "user": unquote(url.username or ""),
        "password": unquote(url.password or ""),
        "database": url.path.lstrip("/"),
        "login_timeout": 10,
    }


def get_connection(attempts: int = 3) -> Connection:
    """Connect, retrying with backoff: on Azure the database may be resuming from pause (error 40613)."""
    delay = 1
    for attempt in range(1, attempts + 1):
        try:
            return Connection(pymssql.connect(**_connect_args()))
        except pymssql.OperationalError:
            if attempt == attempts:
                raise
            time.sleep(delay)
            delay = min(delay * 2, 10)


def wait_for_db(max_wait_s: int = 90) -> Connection:
    """At startup: keep trying for up to max_wait_s, so a paused or still-starting database doesn't crash the service."""
    deadline = time.monotonic() + max_wait_s
    delay = 1
    while True:
        try:
            return get_connection(attempts=1)
        except pymssql.OperationalError:
            if time.monotonic() + delay > deadline:
                raise
            print(f"Database not ready, retrying in {delay}s", flush=True)
            time.sleep(delay)
            delay = min(delay * 2, 10)


def get_db():
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


def require_row(conn: Connection, table: str, row_id: int) -> Row:
    """Return the row or raise NotFoundError. `table` must be a hard-coded literal,
    never user input: SQL placeholders cannot be used for table names."""
    row = conn.execute(f"SELECT * FROM {table} WHERE id = ?", (row_id,)).fetchone()
    if row is None:
        raise NotFoundError(f"{table} id {row_id} not found")
    return row