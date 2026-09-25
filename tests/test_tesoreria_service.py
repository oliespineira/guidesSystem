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

def test_approving_consumes_budget(conn, budget):
    r = tesoreria.submit_request(conn, budget, "Guias", "Tiendas", 6000, policies.RejectOverBudget())
    tesoreria.Approve(r.request_id, actor="Tesorera").execute(conn)
    assert tesoreria.remaining_cents(conn, budget) == 4000


def test_cannot_pay_before_approval(conn, budget):
    r = tesoreria.submit_request(conn, budget, "Guias", "Albergue", 3000, policies.RejectOverBudget())
    with pytest.raises(ConflictError):
        tesoreria.MarkPaid(r.request_id, payment_ref="TRF-1").execute(conn)


def test_cannot_approve_twice(conn, budget):
    r = tesoreria.submit_request(conn, budget, "Guias", "Albergue", 3000, policies.RejectOverBudget())
    tesoreria.Approve(r.request_id).execute(conn)
    with pytest.raises(ConflictError):
        tesoreria.Approve(r.request_id).execute(conn)


def test_rejected_request_cannot_be_approved_later(conn, budget):
    r = tesoreria.submit_request(conn, budget, "Guias", "Albergue", 3000, policies.RejectOverBudget())
    tesoreria.Reject(r.request_id, note="Not this year").execute(conn)
    with pytest.raises(ConflictError):
        tesoreria.Approve(r.request_id).execute(conn)


def test_approve_fails_if_money_was_spent_in_the_meantime(conn, budget):
    first = tesoreria.submit_request(conn, budget, "Guias", "Tiendas", 6000, policies.RejectOverBudget())
    second = tesoreria.submit_request(conn, budget, "Alitas", "Albergue", 6000, policies.RejectOverBudget())
    tesoreria.Approve(first.request_id).execute(conn)
    with pytest.raises(ConflictError):
        tesoreria.Approve(second.request_id).execute(conn)


def test_payment_needs_a_reference(conn, budget):
    r = tesoreria.submit_request(conn, budget, "Guias", "Albergue", 3000, policies.RejectOverBudget())
    tesoreria.Approve(r.request_id).execute(conn)
    with pytest.raises(InvalidInputError):
        tesoreria.MarkPaid(r.request_id, payment_ref="  ")


def test_unknown_request_is_not_found(conn):
    with pytest.raises(NotFoundError):
        tesoreria.Approve(999).execute(conn)


def test_history_is_the_payment_record(conn, budget):
    r = tesoreria.submit_request(conn, budget, "Guias", "Albergue", 3000, policies.RejectOverBudget())
    tesoreria.Approve(r.request_id, actor="Tesorera").execute(conn)
    tesoreria.MarkPaid(r.request_id, payment_ref="TRF-42", actor="Tesorera").execute(conn)
    history = tesoreria.request_history(conn, r.request_id)
    assert [h["action"] for h in history] == ["submitted", "approved", "paid"]
    assert history[-1]["payment_ref"] == "TRF-42"