#business logic for the second functionality of the system. 
#overall it takes a database connection, s it needs no web server. Its job is to validate input, write to the tables meetings, agenda_items, decisions and calendar_events, and read a meeting back as one nested structure.
import sqlite3 #pythion's built in database library
from datetime import date#used to check that date string is really a date and to compare start and end dates.

from src.db import require_row #fetches a row by id or raises "not found"
from src.errors import InvalidInputError #error typr for pad input (HTTP 400N)


class InvalidDateRangeError(InvalidInputError):
    """A calendar event ends before it starts."""


def _require_ronda(conn: sqlite3.Connection, ronda_id: int) -> None:
    # THE SEAM. This is the only place Domain 2 asks about Domain 1's data.
    # If the domains were split into services, this one function becomes an HTTP call.
    require_row(conn, "rondas", ronda_id)


def _parse_date(value: str, field: str) -> str:
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        raise InvalidInputError(f"{field} must be an ISO date (YYYY-MM-DD)") from None


def create_meeting(conn, ronda_id: int, meeting_date: str, title: str) -> int:
    _require_ronda(conn, ronda_id)
    if not title or not title.strip():
        raise InvalidInputError("Meeting title cannot be empty")
    cur = conn.execute(
        "INSERT INTO meetings (ronda_id, date, title) VALUES (?, ?, ?)",
        (ronda_id, _parse_date(meeting_date, "date"), title.strip()),
    )
    conn.commit()
    return cur.lastrowid


def list_meetings(conn, ronda_id: int) -> list[dict]:
    _require_ronda(conn, ronda_id)
    rows = conn.execute(
        "SELECT id, date, title FROM meetings WHERE ronda_id = ? ORDER BY date DESC, id DESC",
        (ronda_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def add_agenda_item(conn, meeting_id: int, section_title: str,
                    content: str | None = None, position: int | None = None) -> int:
    require_row(conn, "meetings", meeting_id)
    if not section_title or not section_title.strip():
        raise InvalidInputError("Section title cannot be empty")
    if position is None:
        position = conn.execute(
            "SELECT COALESCE(MAX(position), -1) + 1 AS next_pos FROM agenda_items WHERE meeting_id = ?",
            (meeting_id,),
        ).fetchone()["next_pos"]
    cur = conn.execute(
        "INSERT INTO agenda_items (meeting_id, section_title, content, position) VALUES (?, ?, ?, ?)",
        (meeting_id, section_title.strip(), content, position),
    )
    conn.commit()
    return cur.lastrowid


def record_decision(conn, agenda_item_id: int, description: str, vote_result: str | None = None) -> int:
    require_row(conn, "agenda_items", agenda_item_id)
    if not description or not description.strip():
        raise InvalidInputError("Decision description cannot be empty")
    cur = conn.execute(
        "INSERT INTO decisions (agenda_item_id, description, vote_result) VALUES (?, ?, ?)",
        (agenda_item_id, description.strip(), vote_result),
    )
    conn.commit()
    return cur.lastrowid


def add_calendar_event(conn, ronda_id: int, start_date: str, activity_type: str,
                       end_date: str | None = None, assigned_volunteers: str | None = None) -> int:
    _require_ronda(conn, ronda_id)
    if not activity_type or not activity_type.strip():
        raise InvalidInputError("Activity type cannot be empty")
    start = _parse_date(start_date, "start_date")
    end = _parse_date(end_date, "end_date") if end_date else None
    if end is not None and end < start:
        raise InvalidDateRangeError("end_date cannot be before start_date")
    cur = conn.execute(
        """INSERT INTO calendar_events (ronda_id, start_date, end_date, activity_type, assigned_volunteers)
           VALUES (?, ?, ?, ?, ?)""",
        (ronda_id, start, end, activity_type.strip(), assigned_volunteers),
    )
    conn.commit()
    return cur.lastrowid


def list_calendar(conn, ronda_id: int) -> list[dict]:
    _require_ronda(conn, ronda_id)
    rows = conn.execute(
        "SELECT * FROM calendar_events WHERE ronda_id = ? ORDER BY start_date", (ronda_id,)
    ).fetchall()
    return [dict(r) for r in rows]


def meeting_summary(conn, meeting_id: int) -> dict:
    meeting = require_row(conn, "meetings", meeting_id)
    items = conn.execute(
        "SELECT * FROM agenda_items WHERE meeting_id = ? ORDER BY position, id", (meeting_id,)
    ).fetchall()
    decisions = conn.execute(
        """SELECT d.* FROM decisions d
           JOIN agenda_items a ON a.id = d.agenda_item_id
           WHERE a.meeting_id = ? ORDER BY d.id""",
        (meeting_id,),
    ).fetchall()

    by_item: dict[int, list[dict]] = {}
    for d in decisions:
        by_item.setdefault(d["agenda_item_id"], []).append(
            {"id": d["id"], "description": d["description"], "vote_result": d["vote_result"]}
        )
    return {
        "id": meeting["id"],
        "date": meeting["date"],
        "title": meeting["title"],
        "agenda": [
            {
                "id": it["id"],
                "position": it["position"],
                "section_title": it["section_title"],
                "content": it["content"],
                "decisions": by_item.get(it["id"], []),
            }
            for it in items
        ],
    }