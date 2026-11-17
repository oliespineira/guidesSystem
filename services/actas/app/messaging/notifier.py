from abc import ABC, abstractmethod

from app.db import Connection
from app.messaging.topics import matches
from app.validation import require_text


class Notifier(ABC):
    @abstractmethod
    def notify(self, conn: Connection, topic: str, title: str, body: str | None = None) -> int:
        """Save a notice and deliver it. Returns the notice id."""


def save_notice(conn: Connection, topic: str, title: str, body: str | None = None) -> dict:
    topic = require_text(topic, "Notice topic")
    title = require_text(title, "Notice title")
    cur = conn.execute(
        "INSERT INTO notices (topic, title, body) VALUES (?, ?, ?)",
        (topic, title, body),
    )
    conn.commit()
    return dict(conn.execute("SELECT * FROM notices WHERE id = ?", (cur.lastrowid,)).fetchone())


class BrokerNotifier(Notifier):
    def __init__(self, broker):
        self._broker = broker

    def notify(self, conn, topic, title, body=None):
        notice = save_notice(conn, topic, title, body)
        self._broker.publish(notice)  # only after commit: never announce something that isn't saved
        return notice["id"]


def notices_since(conn: Connection, patterns, after_id: int = 0) -> list[dict]:
    """Every saved notice newer than after_id that matches any of the patterns, oldest first."""
    rows = conn.execute("SELECT * FROM notices WHERE id > ? ORDER BY id", (after_id,)).fetchall()
    return [dict(r) for r in rows if any(matches(p, r["topic"]) for p in patterns)]
