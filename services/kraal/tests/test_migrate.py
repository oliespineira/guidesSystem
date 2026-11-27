import pytest
from app import migrate


def test_an_empty_migration_file_is_refused_and_not_recorded(conn, tmp_path, monkeypatch):
    (tmp_path / "999_empty.sql").write_text("", encoding="utf-8")
    monkeypatch.setattr(migrate, "MIGRATIONS_DIR", tmp_path)
    with pytest.raises(RuntimeError, match="999_empty.sql is empty"):
        migrate.run_migrations(conn)
    recorded = conn.execute("SELECT version FROM schema_migrations WHERE version = '999_empty'").fetchone()
    assert recorded is None
