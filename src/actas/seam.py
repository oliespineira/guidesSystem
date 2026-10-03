from src.db import require_row
from src.errors import ConflictError
from src.kraal.service import ronda_member_ids

# THE SEAM: the only module in Domain 2 that asks about Domain 1's data.
# If the domains were split into services, each function here becomes one HTTP call.


def require_ronda(conn, ronda_id: int) -> None:
    require_row(conn, "rondas", ronda_id)


def electorate(conn, ronda_id: int) -> set[int]:
    """Ids of the volunteers who may vote in this ronda (the whole kraal that year)."""
    return ronda_member_ids(conn, ronda_id)


def require_voter(conn, ronda_id: int, volunteer_id: int) -> None:
    if volunteer_id not in electorate(conn, ronda_id):
        raise ConflictError(f"Volunteer {volunteer_id} is not in the kraal for this ronda")