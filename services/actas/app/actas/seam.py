import os

import httpx

from app.errors import ConflictError, ForbiddenError, NotFoundError, ServiceUnavailableError
from app.messaging.topics import slug

# THE SEAM : the only module in actass that asks about kraal's data
# each function is now one http call to the kraal service.

KRAAL_DOWN = "El servicio Kraal no está disponible; inténtalo de nuevo"


def _kraal_get(path: str):
    """
    This is the heart of the seam, every Kraal goes through it, so the failure handling lives in one place.

    """
    base_url = os.environ.get(
        "KRAAL_URL", "http://kraal:8000"
    )  # no hardcoded host, it reads them on everycall, so tests can change them with monkeypatch.setenv.
    timeout = float(os.environ.get("KRAAL_TIMEOUT_S", "2"))  # is kraal doesnt answer in 2 seconds, give up
    try:
        response = httpx.get(f"{base_url}{path}", timeout=timeout)
    except httpx.RequestError as exc:
        raise ServiceUnavailableError(KRAAL_DOWN) from exc
    if response.status_code == 404:
        raise NotFoundError(response.json()["detail"])
    if response.status_code != 200:
        raise ServiceUnavailableError(KRAAL_DOWN)
    return response.json()


def require_ronda(conn, ronda_id: int) -> None:
    _kraal_get(f"/api/kraal/rondas/{ronda_id}")


def electorate(conn, ronda_id: int) -> set[int]:
    """Ids of the volunteers who may vote in this ronda (the whole kraal that year)."""
    return set(_kraal_get(f"/api/kraal/rondas/{ronda_id}/members"))


def require_voter(conn, ronda_id: int, volunteer_id: int) -> None:
    if volunteer_id not in electorate(conn, ronda_id):
        raise ConflictError(f"Volunteer {volunteer_id} is not in the kraal for this ronda")


def role_holders(conn, ronda_id: int, role_name: str) -> set[int]:
    """Ids of the volunteers holding this role in this ronda (compared as slugs)."""
    roles = _kraal_get(f"/api/kraal/rondas/{ronda_id}/roles")
    return {r["volunteer_id"] for r in roles if slug(r["role_name"]) == slug(role_name)}


def membership(conn, ronda_id: int, volunteer_id: int) -> dict:
    """Name, rama and roles of one volunteer in this ronda."""
    return _kraal_get(f"/api/kraal/rondas/{ronda_id}/volunteers/{volunteer_id}/membership")


def require_role(conn, ronda_id: int, volunteer_id: int, role_name: str) -> dict:
    member = membership(conn, ronda_id, volunteer_id)
    if slug(role_name) not in {slug(r) for r in member["roles"]}:
        raise ForbiddenError(f"Only the {role_name} of this ronda can do this")
    return member


def check_ronda_if_available(conn, ronda_id: int) -> None:
    """For reads: check the ronda when Kraal answers, but still serve our own data when it is down."""
    try:
        require_ronda(conn, ronda_id)
    except ServiceUnavailableError:
        pass
