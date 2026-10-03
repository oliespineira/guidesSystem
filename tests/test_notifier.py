import pytest

from src.errors import InvalidInputError
from src.messaging.notifier import BrokerNotifier, notices_since, save_notice


class FakeBroker:
    """Records publish calls instead of delivering them: no event loop needed."""
    def __init__(self):
        self.published = []

    def publish(self, message):
        self.published.append(message)


def test_broker_notifier_saves_then_publishes_the_same_notice(conn):
    broker = FakeBroker()
    notice_id = BrokerNotifier(broker).notify(conn, "ronda.1.all", "Reunión el lunes", "A las 19h")
    saved = notices_since(conn, ["ronda.1.#"])
    assert [n["id"] for n in saved] == [notice_id]
    assert broker.published == saved            # exactly what was stored, created_at included


def test_blank_title_is_rejected_and_nothing_is_published(conn):
    broker = FakeBroker()
    with pytest.raises(InvalidInputError):
        BrokerNotifier(broker).notify(conn, "ronda.1.all", "   ")
    assert broker.published == [] and notices_since(conn, ["#"]) == []


def test_notices_since_filters_by_pattern_and_id(conn):
    first = save_notice(conn, "ronda.1.rama.guias", "Guías 1")["id"]
    save_notice(conn, "ronda.1.rama.alitas", "Alitas 1")
    save_notice(conn, "ronda.1.rama.guias", "Guías 2")
    save_notice(conn, "ronda.2.all", "Otra ronda")

    guias = notices_since(conn, ["ronda.1.rama.guias", "ronda.1.all"])
    assert [n["title"] for n in guias] == ["Guías 1", "Guías 2"]

    newer = notices_since(conn, ["ronda.1.rama.guias"], after_id=first)
    assert [n["title"] for n in newer] == ["Guías 2"]