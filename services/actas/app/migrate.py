from pathlib import Path

from app.db import Connection

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


def _batches(sql: str) -> list[str]:
    """Split a migration file on lines that say GO, like sqlcmd does."""
    batches, current = [], []
    for line in sql.splitlines():
        if line.strip().upper() == "GO":
            batches.append("\n".join(current))
            current = []
        else:
            current.append(line)
    batches.append("\n".join(current))
    return [b for b in batches if b.strip()]


def run_migrations(conn: Connection) -> None:
    conn.execute(
        "IF OBJECT_ID('dbo.schema_migrations') IS NULL "
        "CREATE TABLE schema_migrations ("
        "version NVARCHAR(100) PRIMARY KEY, "
        "applied_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME())"
    )
    conn.commit()
    applied = {row["version"] for row in conn.execute("SELECT version FROM schema_migrations")}
    pending = [path for path in sorted(MIGRATIONS_DIR.glob("*.sql")) if path.stem not in applied]
    if not pending:
        print("No pending migrations", flush=True)
        return
    for path in pending:
        try:
            for batch in _batches(path.read_text(encoding="utf-8")):
                conn.execute(batch)
            conn.execute("INSERT INTO schema_migrations (version) VALUES (?)", (path.stem,))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        print(f"Applied migration {path.stem}", flush=True)