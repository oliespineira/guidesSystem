import os
import sqlite3
from datetime import date, timedelta

from src.actas.seam import require_ronda
from src.db import require_row
from src.errors import ConflictError, InvalidInputError
from src.messaging.notifier import Notifier
from src.messaging.topics import all_topic
from src.validation import require_text


def _lead_days() -> int:
    return int(os.environ.get("BOOKING_LEAD_DAYS", "90"))      # how far ahead albergues must be booked


def _remind_days() -> int:
    return int(os.environ.get("BOOKING_REMIND_DAYS", "14"))    # start reminding this close to the deadline


def _parse(value: str, field: str) -> date:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise InvalidInputError(f"{field} must be an ISO date (YYYY-MM-DD)") from None


def plan_booking(conn: sqlite3.Connection, event_id: int, book_by: str | None = None,
                 notifier: Notifier | None = None) -> str:
    """Say that an outing needs an albergue, and by when it must be booked."""
    event = require_row(conn, "calendar_events", event_id)
    start = date.fromisoformat(event["start_date"])
    deadline = _parse(book_by, "book_by") if book_by else start - timedelta(days=_lead_days())
    if deadline >= start:
        raise InvalidInputError("book_by must be before the outing starts")
    try:
        conn.execute("INSERT INTO bookings (event_id, book_by) VALUES (?, ?)", (event_id, deadline.isoformat()))
    except sqlite3.IntegrityError:
        raise ConflictError("This outing already has a booking plan") from None
    conn.commit()
    if notifier is not None:
        notifier.notify(conn, all_topic(event["ronda_id"]),
                        f"Albergue needed: {event['activity_type']} on {event['start_date']}",
                        f"Book before {deadline.isoformat()}.")
    return deadline.isoformat()


def mark_booked(conn: sqlite3.Connection, event_id: int, venue: str, request_id: int | None = None,
                notifier: Notifier | None = None) -> None:
    booking = conn.execute("SELECT * FROM bookings WHERE event_id = ?", (event_id,)).fetchone()
    if booking is None:
        require_row(conn, "calendar_events", event_id)          # 404 if the outing itself doesn't exist
        raise ConflictError("Plan the booking first")
    if booking["status"] == "booked":
        raise ConflictError("This outing is already booked")
    venue = require_text(venue, "Venue")
    if request_id is not None:
        require_row(conn, "budget_requests", request_id)        # link the payment, if there is one
    conn.execute("UPDATE bookings SET status = 'booked', venue = ?, request_id = ? WHERE event_id = ?",
                 (venue, request_id, event_id))
    conn.commit()
    if notifier is not None:
        event = require_row(conn, "calendar_events", event_id)
        notifier.notify(conn, all_topic(event["ronda_id"]),
                        f"Albergue booked for {event['activity_type']}: {venue}", None)


def list_bookings(conn: sqlite3.Connection, ronda_id: int, today: date | None = None) -> list[dict]:
    require_ronda(conn, ronda_id)
    today = today or date.today()
    rows = conn.execute(
        """SELECT b.*, e.start_date, e.activity_type FROM bookings b
           JOIN calendar_events e ON e.id = b.event_id
           WHERE e.ronda_id = ? ORDER BY b.book_by""",
        (ronda_id,),
    ).fetchall()
    result = []
    for r in rows:
        days_left = (date.fromisoformat(r["book_by"]) - today).days
        result.append({**dict(r), "days_left": days_left,
                       "urgent": r["status"] == "pending" and days_left <= _remind_days()})
    return result


def send_reminders(conn: sqlite3.Connection, notifier: Notifier, today: date | None = None) -> int:
    """Remind the kraal about every pending booking whose deadline is close or past.
    At most one reminder per booking per day. Returns how many were sent."""
    today = today or date.today()
    horizon = (today + timedelta(days=_remind_days())).isoformat()
    rows = conn.execute(
        """SELECT b.event_id, b.book_by, e.ronda_id, e.activity_type, e.start_date
           FROM bookings b JOIN calendar_events e ON e.id = b.event_id
           WHERE b.status = 'pending' AND b.book_by <= ?
             AND (b.last_reminded IS NULL OR b.last_reminded < ?)""",
        (horizon, today.isoformat()),
    ).fetchall()
    for r in rows:
        days_left = (date.fromisoformat(r["book_by"]) - today).days
        when = f"{days_left} days left" if days_left >= 0 else f"{-days_left} days OVERDUE"
        notifier.notify(conn, all_topic(r["ronda_id"]),
                        f"Reminder: book the albergue for {r['activity_type']} ({r['start_date']})",
                        f"Deadline {r['book_by']}: {when}.")
        conn.execute("UPDATE bookings SET last_reminded = ? WHERE event_id = ?", (today.isoformat(), r["event_id"]))
    conn.commit()
    return len(rows)