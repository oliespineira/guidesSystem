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

def test_continuity_report_detects_join_leave_stay_and_move(conn):
    r1=service.create_ronda(conn, "2025", "2025-09-01")
    r2=service.create_ronda(conn, "2026", "2026-09-01")
    carla, arturo, alonso, cayetana=(service.add_volunteer(conn, n) for n in ("Carla", "Arturo", "Alonso", "Cayetana"))

    g1,a1=service.create_rama(conn, r1, "Guias"), service.create_rama(conn, r1, "Alitas")
    g2, a2 = service.create_rama(conn, r2, "Guias"), service.create_rama(conn, r2, "Alitas")

    service.assign_to_rama(conn, g1,carla)
    service.assign_to_rama(conn, g1,arturo)
    service.assign_to_rama(conn, a1,alonso) #leaves
    service.assign_to_rama(conn, g2, carla)
    service.assign_to_rama(conn, a2, arturo)
    service.assign_to_rama(conn, a2, cayetana)

    report = service.continuity_report(conn, r1, r2)

    assert report.joined == ["Cayetana"]
    assert report.left == ["Alonso"]
    assert report.stayed == ["Arturo", "Carla"]
    assert report.moved == {"Arturo": ("Guias", "Alitas")}

# in test_kraal_service.py
def test_get_roster_groups_by_rama(conn):
    ronda = service.create_ronda(conn, "2026", "2026-09-01")
    rama = service.create_rama(conn, ronda, "Guias")
    v = service.add_volunteer(conn, "Ana")
    service.assign_to_rama(conn, rama, v)
    roster = service.get_roster(conn, ronda)
    assert roster == {"Guias": ["Ana"]}


def test_list_rondas_returns_all(conn):
    service.create_ronda(conn, "2025", "2025-09-01")
    service.create_ronda(conn, "2026", "2026-09-01")
    assert len(service.list_rondas(conn)) == 2


def test_create_rama_rejects_blank_name(conn):
    ronda = service.create_ronda(conn, "2026", "2026-09-01")
    with pytest.raises(InvalidInputError):
        service.create_rama(conn, ronda, "   ")


def test_assign_to_rama_rejects_invalid_availability(conn):
    ronda = service.create_ronda(conn, "2026", "2026-09-01")
    rama = service.create_rama(conn, ronda, "Guias")
    v = service.add_volunteer(conn, "Ana")
    with pytest.raises(service.InvalidAvailabilityError):
        service.assign_to_rama(conn, rama, v, availability_pct=150)


def test_assign_to_rama_rejects_second_rama_same_ronda(conn):
    ronda = service.create_ronda(conn, "2026", "2026-09-01")
    guias = service.create_rama(conn, ronda, "Guias")
    alitas = service.create_rama(conn, ronda, "Alitas")
    v = service.add_volunteer(conn, "Ana")
    service.assign_to_rama(conn, guias, v)
    with pytest.raises(ConflictError):
        service.assign_to_rama(conn, alitas, v)
def test_continuity_report_unknown_ronda_is_not_found(conn):
    ronda = service.create_ronda(conn, "2026", "2026-09-01")
    with pytest.raises(NotFoundError):
        service.continuity_report(conn, ronda, 999)
