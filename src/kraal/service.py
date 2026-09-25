import sqlite3

from src.db import require_row
from src.errors import ConflictError, InvalidInputError
from dataclasses import dataclass


class DuplicateRoleError(ConflictError):
    """The role is already held by someone this ronda."""


class InvalidAvailabilityError(InvalidInputError):
    """availability_pct outside 0-100."""


def create_ronda(conn: sqlite3.Connection, year_label: str, start_date: str) -> int:
    if not year_label or not year_label.strip():
        raise InvalidInputError("Ronda label cannot be empty")
    try:
        cur = conn.execute(
            "INSERT INTO rondas (year_label, start_date) VALUES (?, ?)",
            (year_label.strip(), start_date),
        )
    except sqlite3.IntegrityError:
        raise ConflictError(f"Ronda '{year_label}' already exists") from None
    conn.commit()
    return cur.lastrowid


def list_rondas(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT * FROM rondas ORDER BY start_date DESC").fetchall()
    return [dict(r) for r in rows]


def add_volunteer(conn: sqlite3.Connection, name: str, joined_date: str | None = None) -> int:
    if not name or not name.strip():
        raise InvalidInputError("Volunteer name cannot be empty")
    cur = conn.execute(
        "INSERT INTO volunteers (name, joined_date) VALUES (?, ?)",
        (name.strip(), joined_date),
    )
    conn.commit()
    return cur.lastrowid


def assign_role(conn: sqlite3.Connection, ronda_id: int, volunteer_id: int, role_name: str) -> int:
    require_row(conn, "rondas", ronda_id)
    require_row(conn, "volunteers", volunteer_id)
    if not role_name or not role_name.strip():
        raise InvalidInputError("Role name cannot be empty")
    existing = conn.execute(
        "SELECT id FROM roles WHERE ronda_id = ? AND role_name = ?",
        (ronda_id, role_name.strip()),
    ).fetchone()
    if existing is not None:
        raise DuplicateRoleError(f"Role '{role_name}' is already assigned for this ronda")
    cur = conn.execute(
        "INSERT INTO roles (ronda_id, volunteer_id, role_name) VALUES (?, ?, ?)",
        (ronda_id, volunteer_id, role_name.strip()),
    )
    conn.commit()
    return cur.lastrowid

def create_rama(conn: sqlite3.Connection, ronda_id: int, name: str) -> int:
    require_row(conn, "rondas", ronda_id)
    if not name or not name.strip():
        raise InvalidInputError("Rama name cannot be empty")
    try:
        cur = conn.execute(
            "INSERT INTO ramas (ronda_id, name) VALUES (?, ?)", (ronda_id, name.strip())
        )
    except sqlite3.IntegrityError:
        raise ConflictError(f"Rama '{name}' already exists in this ronda") from None
    conn.commit()
    return cur.lastrowid


def assign_to_rama(
    conn: sqlite3.Connection,
    rama_id: int,
    volunteer_id: int,
    availability_pct: int | None = None,
    notes: str | None = None,
) -> int:
    rama = require_row(conn, "ramas", rama_id)
    require_row(conn, "volunteers", volunteer_id)
    if availability_pct is not None and not (0 <= availability_pct <= 100):
        raise InvalidAvailabilityError("availability_pct must be between 0 and 100")

    # Business rule: one rama per volunteer per ronda. The UNIQUE(ronda_id, volunteer_id)
    # constraint is the guarantee; this check gives a friendlier message.
    clash = conn.execute(
        """SELECT r.name FROM rama_assignments ra JOIN ramas r ON r.id = ra.rama_id
           WHERE ra.ronda_id = ? AND ra.volunteer_id = ?""",
        (rama["ronda_id"], volunteer_id),
    ).fetchone()
    if clash is not None:
        raise ConflictError(f"Volunteer is already in rama '{clash['name']}' this ronda")

    cur = conn.execute(
        """INSERT INTO rama_assignments (ronda_id, rama_id, volunteer_id, availability_pct, notes)
           VALUES (?, ?, ?, ?, ?)""",
        (rama["ronda_id"], rama_id, volunteer_id, availability_pct, notes),
    )
    conn.commit()
    return cur.lastrowid


def get_roster(conn: sqlite3.Connection, ronda_id: int) -> dict[str, list[str]]:
    require_row(conn, "rondas", ronda_id)
    rows = conn.execute(
        """SELECT r.name AS rama_name, v.name AS volunteer_name
           FROM rama_assignments ra
           JOIN ramas r ON r.id = ra.rama_id
           JOIN volunteers v ON v.id = ra.volunteer_id
           WHERE ra.ronda_id = ?
           ORDER BY r.name, v.name""",
        (ronda_id,),
    ).fetchall()
    roster: dict[str, list[str]] = {}
    for row in rows:
        roster.setdefault(row["rama_name"], []).append(row["volunteer_name"])
    return roster


@dataclass
class ContinuityReport:
    joined: list[str]
    left: list[str]
    stayed: list[str]
    moved: dict[str, tuple[str, str]]


def continuity_report(conn: sqlite3.Connection, prev_ronda_id: int, new_ronda_id: int) -> ContinuityReport:
    require_row(conn, "rondas", prev_ronda_id)
    require_row(conn, "rondas", new_ronda_id)
    prev = _volunteer_rama_map(conn, prev_ronda_id)
    new = _volunteer_rama_map(conn, new_ronda_id)

    prev_ids, new_ids = set(prev), set(new)
    stayed_ids = prev_ids & new_ids
    return ContinuityReport(
        joined=sorted(new[i][0] for i in new_ids - prev_ids),
        left=sorted(prev[i][0] for i in prev_ids - new_ids),
        stayed=sorted(new[i][0] for i in stayed_ids),
        moved={new[i][0]: (prev[i][1], new[i][1]) for i in stayed_ids if prev[i][1] != new[i][1]},
    )


def _volunteer_rama_map(conn: sqlite3.Connection, ronda_id: int) -> dict[int, tuple[str, str]]:
    rows = conn.execute(
        """SELECT v.id AS volunteer_id, v.name AS volunteer_name, r.name AS rama_name
           FROM rama_assignments ra
           JOIN ramas r ON r.id = ra.rama_id
           JOIN volunteers v ON v.id = ra.volunteer_id
           WHERE ra.ronda_id = ?""",
        (ronda_id,),
    ).fetchall()
    return {row["volunteer_id"]: (row["volunteer_name"], row["rama_name"]) for row in rows}