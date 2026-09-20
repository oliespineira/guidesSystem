import pytest
from fastapi.testclient import TestClient

from src.db import get_connection, init_db


@pytest.fixture
def conn():
    c = get_connection(":memory:")
    init_db(c)
    yield c
    c.close()


@pytest.fixture
def client(tmp_path, monkeypatch):
    # A real temp file, not :memory:, because every request opens its own connection.
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    from app import app
    with TestClient(app) as c:   # the `with` runs the lifespan (creates the schema)
        yield c