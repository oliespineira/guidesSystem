import os
from abc import ABC, abstractmethod
from dataclasses import dataclass

from src.errors import InvalidInputError

@dataclass(frozen = True)
class Verdict:
    status:str #"approved" | "rejected"| "pending"
    reason:str

class ApprovalPolicy(ABC):
    @abstractmethod
    def evaluate(self, amount_cents:int, remaining_cents:int)->Verdict: ...

class RejectOverBudget(ApprovalPolicy):
    def evaluate(self, amount_cents, remaining_cents):
        if amount_cents>remaining_cents:
            return Verdict("rejected", f"Exceeds remaining budget ({remaining_cents / 100:.2f} EUR)")
        return Verdict("pendind", "Within budget; waiting for the treasurer")

class AutoApproveUnder(ApprovalPolicy):
    def __init__(self, limit_cents: int):
        self.limit_cents = limit_cents

    def evaluate(self, amount_cents, remaining_cents):
        if amount_cents > remaining_cents:
            return Verdict("rejected", f"Exceeds remaining budget ({remaining_cents / 100:.2f} EUR)")
        if amount_cents <= self.limit_cents:
            return Verdict("approved", f"Auto-approved: under {self.limit_cents / 100:.2f} EUR")
        return Verdict("pending", "Within budget; waiting for the treasurer")


class AlwaysToMeeting(ApprovalPolicy):
    def evaluate(self, amount_cents, remaining_cents):
        return Verdict("pending", "To be decided at the next meeting")



_POLICIES = {
    "reject_over_budget": lambda: RejectOverBudget(),
    "auto_approve_small": lambda: AutoApproveUnder(int(os.environ.get("AUTO_APPROVE_LIMIT_CENTS", "5000"))),
    "always_to_meeting": lambda: AlwaysToMeeting(),
}


def policy_from_name(name: str) -> ApprovalPolicy:
    try:
        return _POLICIES[name]()
    except KeyError:
        raise InvalidInputError(f"Unknown approval policy '{name}'") from None


def get_policy() -> ApprovalPolicy:
    """FastAPI dependency: the active policy comes from the environment (§7.9)."""
    return policy_from_name(os.environ.get("APPROVAL_POLICY", "reject_over_budget"))