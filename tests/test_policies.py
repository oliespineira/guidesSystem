import pytest

from src.actas import policies
from src.errors import InvalidInputError


@pytest.mark.parametrize("amount, expected", [(9999, "pending"), (10000, "pending"), (10001, "rejected")])
def test_reject_over_budget_boundaries(amount, expected):
    assert policies.RejectOverBudget().evaluate(amount, 10000).status == expected


@pytest.mark.parametrize("amount, expected", [(5000, "approved"), (5001, "pending"), (10001, "rejected")])
def test_auto_approve_under_limit_boundaries(amount, expected):
    assert policies.AutoApproveUnder(5000).evaluate(amount, 10000).status == expected


def test_always_to_meeting_never_decides_on_its_own():
    assert policies.AlwaysToMeeting().evaluate(999_999, 0).status == "pending"


def test_policy_from_name_builds_the_right_class():
    assert isinstance(policies.policy_from_name("always_to_meeting"), policies.AlwaysToMeeting)


def test_unknown_policy_name_is_rejected():
    with pytest.raises(InvalidInputError):
        policies.policy_from_name("approve_everything")


def test_get_policy_defaults_to_reject_over_budget(monkeypatch):
    monkeypatch.delenv("APPROVAL_POLICY", raising=False)
    assert isinstance(policies.get_policy(), policies.RejectOverBudget)


def test_get_policy_reads_the_environment(monkeypatch):
    monkeypatch.setenv("APPROVAL_POLICY", "auto_approve_small")
    monkeypatch.setenv("AUTO_APPROVE_LIMIT_CENTS", "2000")
    policy = policies.get_policy()
    assert isinstance(policy, policies.AutoApproveUnder) and policy.limit_cents == 2000