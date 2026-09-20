import pytest
from src.errors import ConflictError, InvalidInputError, NotFoundError
from src.kraal import service


def test_create_ronda_rejects_duplicate_label(conn):
    service.create_ronda(conn, "Ronda Solar 11", "2026-09-01")
    with pytest.raises(ConflictError):
        service.create_ronda(conn, "Ronda Solar 11", "2026-09-01")


def test_add_volunteer_rejects_blank_name(conn):
    with pytest.raises(InvalidInputError):
        service.add_volunteer(conn, "   ")


def test_assign_role_prevents_duplicates(conn):
    ronda = service.create_ronda(conn, "Ronda Solar 11", "2026-09-01")
    a = service.add_volunteer(conn, "Alonso")
    b = service.add_volunteer(conn, "Caballero")
    service.assign_role(conn, ronda, a, "Presidenta")
    with pytest.raises(service.DuplicateRoleError):
        service.assign_role(conn, ronda, b, "Presidenta")


def test_assign_role_unknown_volunteer_is_not_found(conn):
    ronda = service.create_ronda(conn, "Ronda Solar 11", "2026-09-01")
    with pytest.raises(NotFoundError):
        service.assign_role(conn, ronda, 999, "Tesorera")