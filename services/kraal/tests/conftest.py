import os

import pytest
from app.db import get_connection
from app.migrate import run_migrations
from fastapi.testclient import TestClient

# Children before parents, so no foreign key blocks a DELETE.
TABLES = ["rama_assignments", "roles", "ramas", "volunteers", "rondas"]


@pytest.fixture(scope="session", autouse=True)
def test_database():
    """Once per test run: point the app at the test database and apply the migrations."""
    url = os.environ.get("TEST_DATABASE_URL", "")
    if not url.rstrip("/").endswith("_test"):
        pytest.exit("Set TEST_DATABASE_URL to a SQL Server database whose name ends in _test", returncode=2)
    os.environ["DATABASE_URL"] = url
    conn = get_connection()
    run_migrations(conn)
    conn.close()


@pytest.fixture
def conn():
    """Before every test: empty every table, so each test starts from a clean database."""
    c = get_connection()
    for table in TABLES:
        c.execute(f"DELETE FROM {table}")
    c.commit()
    yield c
    c.close()


@pytest.fixture
def client(conn):
    from app.main import app

    with TestClient(app) as c:  # the `with` runs the lifespan: connect and migrations
        yield c
