import pytest

from src.actas import policies, tesoreria
from src.kraal import service as kraal


@pytest.fixture
def budget(conn):
    ronda = kraal.create_ronda(conn, "2026", "2026-09-01")
    return ronda, tesoreria.create_budget(conn, ronda, "Material", 10000)


@pytest.fixture
def treasurer(conn, budget):
    """A volunteer who holds the treasurer role in the budget's ronda."""
    t = kraal.add_volunteer(conn, "Tesorera")
    kraal.assign_role(conn, budget[0], t, "Tesorera")
    return t


def test_pending_request_notifies_the_treasurer(conn, budget, notifier, monkeypatch):
    monkeypatch.delenv("TREASURER_ROLE", raising=False)
    ronda, bid = budget
    tesoreria.submit_request(conn, bid, "Guías", "Tiendas", 3000, policies.RejectOverBudget(), notifier)
    assert [n["topic"] for n in notifier.sent] == [f"ronda.{ronda}.role.tesorera"]
    assert "Guías" in notifier.sent[0]["title"] and "30.00 EUR" in notifier.sent[0]["title"]


def test_treasurer_role_name_comes_from_the_environment(conn, budget, notifier, monkeypatch):
    monkeypatch.setenv("TREASURER_ROLE", "Tesorero")
    ronda, bid = budget
    tesoreria.submit_request(conn, bid, "Guías", "Tiendas", 3000, policies.RejectOverBudget(), notifier)
    assert notifier.sent[0]["topic"] == f"ronda.{ronda}.role.tesorero"


def test_treasurer_is_told_when_another_rama_asked_for_the_same(conn, budget, notifier):
    ronda, bid = budget
    tesoreria.submit_request(conn, bid, "Alitas", "Tiendas", 3000, policies.AlwaysToMeeting())
    tesoreria.submit_request(conn, bid, "Guías", "tiendas", 3000, policies.AlwaysToMeeting(), notifier)
    assert "Already requested by: Alitas" in notifier.sent[0]["body"]


def test_decision_by_policy_goes_straight_to_the_rama(conn, budget, notifier):
    ronda, bid = budget
    tesoreria.submit_request(conn, bid, "Guías", "Pilas", 1000, policies.AutoApproveUnder(5000), notifier)
    assert notifier.sent[0]["topic"] == f"ronda.{ronda}.rama.guias"
    assert notifier.sent[0]["title"] == "Your request for Pilas was approved"


def test_commands_notify_the_requesting_rama(conn, budget, notifier, treasurer):
    ronda, bid = budget
    r = tesoreria.submit_request(conn, bid, "Guías", "Albergue", 3000, policies.RejectOverBudget())
    tesoreria.Approve(r.request_id, treasurer).execute(conn, notifier)
    tesoreria.MarkPaid(r.request_id, payment_ref="TRF-42", by=treasurer).execute(conn, notifier)
    assert [n["topic"] for n in notifier.sent] == [f"ronda.{ronda}.rama.guias"] * 2
    assert notifier.sent[1]["body"] == "Payment reference: TRF-42"


def test_failed_command_sends_nothing(conn, budget, notifier, treasurer):
    _, bid = budget
    r = tesoreria.submit_request(conn, bid, "Guías", "Albergue", 3000, policies.RejectOverBudget())
    with pytest.raises(Exception):
        tesoreria.MarkPaid(r.request_id, payment_ref="TRF-1", by=treasurer).execute(conn, notifier)
    assert notifier.sent == []