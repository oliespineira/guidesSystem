from src.db import require_row

def require_ronda(conn, ronda_id:int )-> None:
    """THE SEAM. The only place Domain 2 asks about Domain 1's data.
    If the domains were split into services, this becomes one HTTP call."""
    require_row(conn, "rondas", ronda_id)