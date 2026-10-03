import sqlite3
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from datetime import datetime

from src.actas.seam import electorate, require_voter
from src.db import require_row
from src.errors import ConflictError, InvalidInputError
from src.messaging.notifier import Notifier
from src.messaging.topics import all_topic

CHOICES = ("yes", "no", "abstain")


@dataclass(frozen=True)
class Tally:
    yes: int
    no: int
    abstain: int
    electorate: int


class CountingRule(ABC):
    @abstractmethod
    def passes(self, t: Tally) -> bool: ...


class MajorityOfCast(CountingRule):
    """More yes than no among the people who voted. Abstentions don't count either way."""
    def passes(self, t):
        return t.yes > t.no


class MajorityOfKraal(CountingRule):
    """More than half of the WHOLE kraal must vote yes, so not voting counts against."""
    def passes(self, t):
        return t.yes * 2 > t.electorate


_RULES = {"majority_of_cast": MajorityOfCast, "majority_of_kraal": MajorityOfKraal}


def rule_from_name(name: str) -> CountingRule:
    try:
        return _RULES[name]()
    except KeyError:
        raise InvalidInputError(f"rule must be one of {', '.join(_RULES)}") from None


def _parse_datetime(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        raise InvalidInputError("closes_at must be an ISO date-time, e.g. 2026-10-05T20:00") from None


def _ronda_of_decision(conn, decision_id: int) -> int:
    row = conn.execute(
        """SELECT m.ronda_id FROM decisions d
           JOIN agenda_items a ON a.id = d.agenda_item_id
           JOIN meetings m ON m.id = a.meeting_id
           WHERE d.id = ?""",
        (decision_id,),
    ).fetchone()
    return row["ronda_id"]


def open_vote(conn: sqlite3.Connection, decision_id: int, closes_at: str, rule: str = "majority_of_cast",
              notifier: Notifier | None = None, now: datetime | None = None) -> None:
    decision = require_row(conn, "decisions", decision_id)
    rule_from_name(rule)                                   # reject unknown rules before saving
    closes = _parse_datetime(closes_at)
    if closes <= (now or datetime.now()):
        raise InvalidInputError("closes_at must be in the future")
    try:
        conn.execute("INSERT INTO votings (decision_id, closes_at, rule) VALUES (?, ?, ?)",
                     (decision_id, closes.isoformat(timespec="minutes"), rule))
    except sqlite3.IntegrityError:
        raise ConflictError("A vote is already open for this decision") from None
    conn.commit()
    if notifier is not None:
        notifier.notify(conn, all_topic(_ronda_of_decision(conn, decision_id)),
                        f"Vote open: {decision['description']}",
                        f"Vote before {closes.isoformat(sep=' ', timespec='minutes')}, even if you can't attend.")


def cast_vote(conn: sqlite3.Connection, decision_id: int, volunteer_id: int, choice: str,
              now: datetime | None = None) -> int:
    voting = _require_voting(conn, decision_id)
    if voting["closed"] or (now or datetime.now()) >= datetime.fromisoformat(voting["closes_at"]):
        raise ConflictError("This vote is closed")
    if choice not in CHOICES:
        raise InvalidInputError(f"choice must be one of {', '.join(CHOICES)}")
    require_voter(conn, _ronda_of_decision(conn, decision_id), volunteer_id)
    try:
        cur = conn.execute("INSERT INTO votes (decision_id, volunteer_id, choice) VALUES (?, ?, ?)",
                           (decision_id, volunteer_id, choice))
    except sqlite3.IntegrityError:
        raise ConflictError("This volunteer has already voted on this decision") from None
    conn.commit()
    return cur.lastrowid


def _require_voting(conn, decision_id: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM votings WHERE decision_id = ?", (decision_id,)).fetchone()
    if row is None:
        require_row(conn, "decisions", decision_id)        # 404 if the decision itself doesn't exist
        raise ConflictError("No vote has been opened for this decision")
    return row


def tally(conn: sqlite3.Connection, decision_id: int) -> dict:
    voting = _require_voting(conn, decision_id)
    rows = conn.execute("SELECT volunteer_id, choice FROM votes WHERE decision_id = ? ORDER BY id",
                        (decision_id,)).fetchall()
    counts = {c: 0 for c in CHOICES}
    for r in rows:
        counts[r["choice"]] += 1
    t = Tally(**counts, electorate=len(electorate(conn, _ronda_of_decision(conn, decision_id))))
    return {**asdict(t), "rule": voting["rule"], "closes_at": voting["closes_at"],
            "closed": bool(voting["closed"]),
            "voters": [{"volunteer_id": r["volunteer_id"], "choice": r["choice"]} for r in rows]}


def close_vote(conn: sqlite3.Connection, decision_id: int, notifier: Notifier | None = None,
               now: datetime | None = None) -> str:
    voting = _require_voting(conn, decision_id)
    if voting["closed"]:
        raise ConflictError("This vote is already closed")
    if (now or datetime.now()) < datetime.fromisoformat(voting["closes_at"]):
        raise ConflictError("The vote is still open; it closes at " + voting["closes_at"])
    result = tally(conn, decision_id)
    t = Tally(result["yes"], result["no"], result["abstain"], result["electorate"])
    outcome = "approved" if rule_from_name(voting["rule"]).passes(t) else "rejected"
    summary = f"{outcome} ({t.yes} yes, {t.no} no, {t.abstain} abstain, {t.electorate} in kraal; {voting['rule']})"
    conn.execute("UPDATE decisions SET vote_result = ? WHERE id = ?", (summary, decision_id))
    conn.execute("UPDATE votings SET closed = 1 WHERE decision_id = ?", (decision_id,))
    conn.commit()
    if notifier is not None:
        description = require_row(conn, "decisions", decision_id)["description"]
        notifier.notify(conn, all_topic(_ronda_of_decision(conn, decision_id)),
                        f"Vote result: {description}", summary)
    return summary