import pytest

from src.actas import policies, tesoreria
from src.errors import ConflictError, InvalidInputError, NotFoundError
from src.kraal import service as kraal


@pytest.fixture
def ronda(conn):
    return kraal.create_ronda(conn, "2026", "2026-09-01")


@pytest.fixture
def budget(conn, ronda):
    return tesoreria.create_budget(conn, ronda, "Material", 10000)   # 100.00 EUR


def test_new_budget_has_everything_remaining(conn, budget):
    assert tesoreria.remaining_cents(conn, budget) == 10000


def test_duplicate_category_in_same_ronda_is_a_conflict(conn, ronda, budget):
    with pytest.raises(ConflictError):
        tesoreria.create_budget(conn, ronda, "Material", 500)


def test_negative_budget_is_rejected(conn, ronda):
    with pytest.raises(InvalidInputError):
        tesoreria.create_budget(conn, ronda, "Salidas", -1)


def test_budget_for_unknown_ronda_is_not_found(conn):
    with pytest.raises(NotFoundError):
        tesoreria.create_budget(conn, 999, "Material", 100)


@pytest.mark.parametrize("amount", [0, -500])
def test_non_positive_amount_is_rejected(conn, budget, amount):
    with pytest.raises(InvalidInputError):
        tesoreria.submit_request(conn, budget, "Guias", "Cuerdas", amount, policies.RejectOverBudget())


def test_blank_item_is_rejected(conn, budget):
    with pytest.raises(InvalidInputError):
        tesoreria.submit_request(conn, budget, "Guias", "   ", 100, policies.RejectOverBudget())


def test_over_budget_request_is_rejected_and_not_counted_as_spent(conn, budget):
    r = tesoreria.submit_request(conn, budget, "Guias", "Tiendas", 20000, policies.RejectOverBudget())
    assert r.verdict.status == "rejected"
    assert tesoreria.remaining_cents(conn, budget) == 10000


def test_auto_approved_request_is_spent_and_logged_as_decided_by_policy(conn, budget):
    r = tesoreria.submit_request(conn, budget, "Guias", "Pilas", 1000, policies.AutoApproveUnder(5000))
    assert tesoreria.remaining_cents(conn, budget) == 9000
    history = tesoreria.request_history(conn, r.request_id)
    assert [(h["action"], h["actor"]) for h in history] == [("submitted", "Guias"), ("approved", "policy")]


def test_same_item_from_another_rama_is_flagged(conn, budget):
    tesoreria.submit_request(conn, budget, "Guias", "Tiendas de campaña", 3000, policies.AlwaysToMeeting())
    r = tesoreria.submit_request(conn, budget, "Alitas", "  tiendas DE campaña ", 3000, policies.AlwaysToMeeting())
    assert [s["rama"] for s in r.similar] == ["Guias"]


def test_same_item_from_the_same_rama_is_not_flagged(conn, budget):
    tesoreria.submit_request(conn, budget, "Guias", "Tiendas", 3000, policies.AlwaysToMeeting())
    r = tesoreria.submit_request(conn, budget, "Guias", "Tiendas", 3000, policies.AlwaysToMeeting())
    assert r.similar == []


def test_rejected_requests_are_not_flagged_as_duplicates(conn, budget):
    tesoreria.submit_request(conn, budget, "Guias", "Tiendas", 50000, policies.RejectOverBudget())
    r = tesoreria.submit_request(conn, budget, "Alitas", "Tiendas", 3000, policies.RejectOverBudget())
    assert r.similar == []


def test_list_budgets_shows_remaining_per_category(conn, ronda, budget):
    tesoreria.create_budget(conn, ronda, "Albergues", 50000)
    tesoreria.submit_request(conn, budget, "Guias", "Pilas", 1000, policies.AutoApproveUnder(5000))
    rows = {b["category"]: b["remaining_cents"] for b in tesoreria.list_budgets(conn, ronda)}
    assert rows == {"Albergues": 50000, "Material": 9000}