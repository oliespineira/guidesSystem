import os
import re

import pytest
from app.actas import seam
from app.db import get_connection
from app.errors import NotFoundError, ServiceUnavailableError
from app.migrate import run_migrations
from fastapi.testclient import TestClient

# Children before parents, so no foreign key blocks a DELETE.
TABLES = [
    "votes",
    "votings",
    "bookings",
    "request_events",
    "budget_requests",
    "budgets",
    "decisions",
    "agenda_items",
    "meetings",
    "calendar_events",
    "notices",
]


class FakeKraal:
    """Stands in for the kraal service in actas tests.

    The setup methods have the same names as kraal's service, so tests build their
    data the same way as before; get() answers the seam's HTTP questions from memory.
    """

    def __init__(self):
        self.down = False  # set to True to simulate kraal being unavailable
        self.rondas = {}  # ronda_id -> ronda as kraal returns it
        self.volunteers = {}  # volunteer_id -> name
        self.ramas = {}  # rama_id -> (ronda_id, rama name)
        self.rama_of = {}  # (ronda_id, volunteer_id) -> rama name
        self.roles = []  # (ronda_id, volunteer_id, role_name)

    def create_ronda(self, conn, year_label, start_date):
        ronda_id = len(self.rondas) + 1
        self.rondas[ronda_id] = {"id": ronda_id, "year_label": year_label, "start_date": start_date, "status": "active"}
        return ronda_id

    def add_volunteer(self, conn, name, joined_date=None):
        volunteer_id = len(self.volunteers) + 1
        self.volunteers[volunteer_id] = name
        return volunteer_id

    def create_rama(self, conn, ronda_id, name):
        rama_id = len(self.ramas) + 1
        self.ramas[rama_id] = (ronda_id, name)
        return rama_id

    def assign_to_rama(self, conn, rama_id, volunteer_id, availability_pct=100, notes=None):
        ronda_id, name = self.ramas[rama_id]
        self.rama_of[(ronda_id, volunteer_id)] = name
        return len(self.rama_of)

    def assign_role(self, conn, ronda_id, volunteer_id, role_name):
        self.roles.append((ronda_id, volunteer_id, role_name))
        return len(self.roles)

    def get(self, path):
        if self.down:
            raise ServiceUnavailableError(seam.KRAAL_DOWN)
        match = re.fullmatch(r"/api/kraal/rondas/(\d+)(/members|/roles|/volunteers/(\d+)/membership)?", path)
        ronda_id, tail = int(match.group(1)), match.group(2)
        if tail is None:
            if ronda_id not in self.rondas:
                raise NotFoundError(f"rondas id {ronda_id} not found")
            return self.rondas[ronda_id]
        if tail == "/members":
            in_rama = {v for (r, v) in self.rama_of if r == ronda_id}
            with_role = {v for (r, v, _) in self.roles if r == ronda_id}
            return sorted(in_rama | with_role)
        if tail == "/roles":
            return [
                {"role_name": name, "volunteer_id": v, "volunteer_name": self.volunteers[v]}
                for (r, v, name) in self.roles
                if r == ronda_id
            ]
        volunteer_id = int(match.group(3))
        if ronda_id not in self.rondas:
            raise NotFoundError(f"rondas id {ronda_id} not found")
        if volunteer_id not in self.volunteers:
            raise NotFoundError(f"volunteers id {volunteer_id} not found")
        return {
            "volunteer_id": volunteer_id,
            "name": self.volunteers[volunteer_id],
            "rama": self.rama_of.get((ronda_id, volunteer_id)),
            "roles": sorted(name for (r, v, name) in self.roles if r == ronda_id and v == volunteer_id),
        }


@pytest.fixture(autouse=True)
def kraal(monkeypatch):
    fake = FakeKraal()
    monkeypatch.setattr(seam, "_kraal_get", fake.get)
    return fake


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
def client(conn, kraal):
    from app.main import app

    with TestClient(app) as c:
        yield c


class RecordingNotifier:
    """Fake Notifier for tests: remembers what would have been sent, saves and delivers nothing."""

    def __init__(self):
        self.sent = []

    def notify(self, conn, topic, title, body=None):
        self.sent.append({"topic": topic, "title": title, "body": body})
        return len(self.sent)


@pytest.fixture
def notifier():
    return RecordingNotifier()
