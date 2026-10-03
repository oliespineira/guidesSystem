import sqlite3
import os
from dataclasses import dataclass

from src.actas.policies import ApprovalPolicy, Verdict
from src.actas.seam import require_ronda 
from src.db import require_row
from src.errors import ConflictError, InvalidInputError
from src.validation import require_text

from src.messaging.notifier import Notifier
from src.messaging.topics import rama_topic, role_topic


def _normalize(item: str) -> str:
    return " ".join(item.lower().split())


def _log_event(conn, request_id, action, actor=None, note=None, payment_ref=None) -> None:
    # No commit here: the event is saved in the same transaction as the change it records.
    conn.execute(
        "INSERT INTO request_events (request_id, action, actor, note, payment_ref) VALUES (?, ?, ?, ?, ?)",
        (request_id, action, actor, note, payment_ref),
    )

def _eur(cents: int) -> str:
    return f"{cents / 100:.2f} EUR"


def _treasurer_topic(ronda_id: int) -> str:
    # The role name is configuration, not code (§7.9): it can change from one ronda to the next.
    return role_topic(ronda_id, os.environ.get("TREASURER_ROLE", "Tesorera"))

def create_budget(conn: sqlite3.Connection, ronda_id: int, category: str, allocated_cents: int) -> int:
    require_ronda(conn, ronda_id)
    category = require_text(category, "Category")
    if allocated_cents < 0:
        raise InvalidInputError("allocated_cents cannot be negative")
    try:
        cur = conn.execute(
            "INSERT INTO budgets (ronda_id, category, allocated_cents) VALUES (?, ?, ?)",
            (ronda_id, category, allocated_cents),
        )
    except sqlite3.IntegrityError:
        raise ConflictError(f"Budget '{category}' already exists for this ronda") from None
    conn.commit()
    return cur.lastrowid

def remaining_cents(conn: sqlite3.Connection, budget_id: int) -> int:
    budget = require_row(conn, "budgets", budget_id)
    spent = conn.execute(
        """SELECT COALESCE(SUM(amount_cents), 0) AS spent FROM budget_requests
           WHERE budget_id = ? AND status IN ('approved', 'paid')""",
        (budget_id,),
    ).fetchone()["spent"]
    return budget["allocated_cents"] - spent


def list_budgets(conn: sqlite3.Connection, ronda_id: int) -> list[dict]:
    require_ronda(conn, ronda_id)
    rows = conn.execute(
        """SELECT b.id, b.category, b.allocated_cents,
                  b.allocated_cents - COALESCE(SUM(CASE WHEN r.status IN ('approved', 'paid')
                                                        THEN r.amount_cents END), 0) AS remaining_cents
           FROM budgets b LEFT JOIN budget_requests r ON r.budget_id = b.id
           WHERE b.ronda_id = ?
           GROUP BY b.id ORDER BY b.category""",
        (ronda_id,),
    ).fetchall()
    return [dict(r) for r in rows]

def similar_requests(conn, budget_id: int, item_key: str, rama: str) -> list[dict]:
    """Open requests for the same item from OTHER ramas in the same ronda."""
    rows = conn.execute(
        """SELECT br.id, br.rama, br.item, br.status
           FROM budget_requests br JOIN budgets b ON b.id = br.budget_id
           WHERE b.ronda_id = (SELECT ronda_id FROM budgets WHERE id = ?)
             AND br.item_key = ? AND br.rama <> ? AND br.status <> 'rejected'
           ORDER BY br.id""",
        (budget_id, item_key, rama),
    ).fetchall()
    return [dict(r) for r in rows]


@dataclass
class SubmitResult:
    request_id: int
    verdict: Verdict
    similar: list[dict]



def submit_request(conn, budget_id: int, rama: str, item: str, amount_cents: int,
                   policy: ApprovalPolicy, notifier: Notifier | None = None) -> SubmitResult:
    require_row(conn, "budgets", budget_id)
    rama = require_text(rama, "Rama")
    item = require_text(item, "Item")
    if amount_cents <= 0:
        raise InvalidInputError("amount_cents must be positive")

    key = _normalize(item)
    similar = similar_requests(conn, budget_id, key, rama)
    verdict = policy.evaluate(amount_cents, remaining_cents(conn, budget_id))

    cur = conn.execute(
        """INSERT INTO budget_requests (budget_id, rama, item, item_key, amount_cents, status)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (budget_id, rama, item, key, amount_cents, verdict.status),
    )
    _log_event(conn, cur.lastrowid, "submitted", actor=rama)
    if verdict.status != "pending":
        _log_event(conn, cur.lastrowid, verdict.status, actor="policy", note=verdict.reason)
    
    conn.commit()

    if notifier is not None:
        ronda_id = conn.execute("SELECT ronda_id FROM budgets WHERE id = ?", (budget_id,)).fetchone()["ronda_id"]
        if verdict.status == "pending":
            body = verdict.reason
            if similar:
                body += ". Already requested by: " + ", ".join(sorted({s["rama"] for s in similar}))
            notifier.notify(conn, _treasurer_topic(ronda_id),
                            f"New request from {rama}: {item} ({_eur(amount_cents)})", body)
        else:
            notifier.notify(conn, rama_topic(ronda_id, rama),
                            f"Your request for {item} was {verdict.status}", verdict.reason)
    return SubmitResult(cur.lastrowid, verdict, similar)


#Here we define the changes of state of the requests. every change od state is an object that records itself.

ALLOWED = {"pending": {"approved", "rejected"}, "approved": {"paid"}} #order

class RequestCommand:
    """Base class. Use a subclass: each one sets target_status."""
    target_status: str


    def __init__(self, request_id: int, actor: str | None = None, note: str | None = None):
        self.request_id = request_id
        self.actor = actor
        self.note = note

    def execute(self, conn: sqlite3.Connection, notifier: Notifier | None = None) -> None:
        req = require_row(conn, "budget_requests", self.request_id)
        if self.target_status not in ALLOWED.get(req["status"], set()):
            raise ConflictError(f"Cannot move a {req['status']} request to {self.target_status}")
        self._check(conn, req)
        conn.execute("UPDATE budget_requests SET status = ? WHERE id = ?",
                     (self.target_status, self.request_id))
        _log_event(conn, self.request_id, self.target_status, self.actor, self.note, self._payment_ref())
        conn.commit()
        if notifier is not None:
            self._notify(conn, req, notifier)

    def _notify(self, conn, req, notifier: Notifier) -> None:
        """Tell the requesting rama what happened. Runs only after the change is committed."""
        ronda_id = conn.execute("SELECT ronda_id FROM budgets WHERE id = ?", (req["budget_id"],)).fetchone()["ronda_id"]
        body = self.note
        if self._payment_ref():
            body = f"Payment reference: {self._payment_ref()}"
        notifier.notify(conn, rama_topic(ronda_id, req["rama"]),
                        f"Your request for {req['item']} was {self.target_status}", body)

    def _check(self, conn, req) -> None:
        """Extra rule for one specific command. Default: none."""

    def _payment_ref(self) -> str | None:
        return None


class Approve(RequestCommand):
    target_status = "approved"

    def _check(self, conn, req):
        if req["amount_cents"] > remaining_cents(conn, req["budget_id"]):
            raise ConflictError("Not enough budget left to approve this request")


class Reject(RequestCommand):
    target_status = "rejected"


class MarkPaid(RequestCommand):
    target_status = "paid"

    def __init__(self, request_id: int, payment_ref: str, actor: str | None = None, note: str | None = None):
        super().__init__(request_id, actor, note)
        self.payment_ref = require_text(payment_ref, "Payment reference")

    def _payment_ref(self):
        return self.payment_ref


def request_history(conn, request_id: int) -> list[dict]:
    require_row(conn, "budget_requests", request_id)
    rows = conn.execute(
        """SELECT action, actor, note, payment_ref, created_at
           FROM request_events WHERE request_id = ? ORDER BY id""",
        (request_id,),
    ).fetchall()
    return [dict(r) for r in rows]
        