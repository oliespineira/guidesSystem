import sqlite3
from dataclasses import dataclass

from src.actas.policies import ApprovalPolicy, Verdict
from src.actas.seam import require_ronda 
from src.db import require_row
from src.errors import ConflictError, InvalidInputError
from src.validation import require_text

def _normalize(item: str) -> str:
    return " ".join(item.lower().split())


def _log_event(conn, request_id, action, actor=None, note=None, payment_ref=None) -> None:
    # No commit here: the event is saved in the same transaction as the change it records.
    conn.execute(
        "INSERT INTO request_events (request_id, action, actor, note, payment_ref) VALUES (?, ?, ?, ?, ?)",
        (request_id, action, actor, note, payment_ref),
    )

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
                   policy: ApprovalPolicy) -> SubmitResult:                             #validates dataa, looks for duplicates, asks for veredict, saves request with that state.
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
    return SubmitResult(cur.lastrowid, verdict, similar)