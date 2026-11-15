import sqlite3
from fastapi import APIRouter, Depends

from app.db import get_db
from app.kraal import service
from app.kraal.schemas import RamaCreate, RamaMember, RoleAssign, RondaCreate, VolunteerCreate, RondaOut, Membership

router = APIRouter(prefix="/api/kraal", tags=["kraal"])


@router.post("/rondas", status_code=201)
def create_ronda(body: RondaCreate, conn: sqlite3.Connection = Depends(get_db)):
    return {"id": service.create_ronda(conn, body.year_label, body.start_date.isoformat())}


@router.get("/rondas")
def list_rondas(conn: sqlite3.Connection = Depends(get_db)):
    return service.list_rondas(conn)


@router.get("/volunteers")
def list_volunteers(conn: sqlite3.Connection = Depends(get_db)):
    return service.list_volunteers(conn)


@router.post("/volunteers", status_code=201)
def add_volunteer(body: VolunteerCreate, conn: sqlite3.Connection = Depends(get_db)):
    joined = body.joined_date.isoformat() if body.joined_date else None
    return {"id": service.add_volunteer(conn, body.name, joined)}

@router.post("/rondas/{ronda_id}/roles", status_code=201)
def assign_role(ronda_id: int, body: RoleAssign, conn: sqlite3.Connection = Depends(get_db)):
    return {"id": service.assign_role(conn, ronda_id, body.volunteer_id, body.role_name)}

@router.get("/rondas/{ronda_id}/roles")
def list_roles(ronda_id: int, conn: sqlite3.Connection = Depends(get_db)):
    return service.list_roles(conn, ronda_id)

@router.post("/rondas/{ronda_id}/ramas", status_code=201)
def create_rama(ronda_id: int, body: RamaCreate, conn: sqlite3.Connection = Depends(get_db)):
    return {"id": service.create_rama(conn, ronda_id, body.name)}



@router.get("/rondas/{ronda_id}/ramas")
def list_ramas(ronda_id: int, conn: sqlite3.Connection = Depends(get_db)):
    return service.list_ramas(conn, ronda_id)

@router.post("/ramas/{rama_id}/members", status_code=201)
def add_member(rama_id: int, body: RamaMember, conn: sqlite3.Connection = Depends(get_db)):
    return {"id": service.assign_to_rama(conn, rama_id, body.volunteer_id,
                                         body.availability_pct, body.notes)}


@router.get("/rondas/{ronda_id}/roster")
def roster(ronda_id: int, conn: sqlite3.Connection = Depends(get_db)):
    return service.get_roster(conn, ronda_id)


@router.get("/continuity")
def continuity(prev: int, new: int, conn: sqlite3.Connection = Depends(get_db)):
    return service.continuity_report(conn, prev, new)

#NEW FOR ASSIGNMENT 2:
@router.get("/rondas/{ronda_id}", response_model=RondaOut, responses={404: {"description": "Ronda not found"}})
def get_ronda(ronda_id: int, conn: sqlite3.Connection = Depends(get_db)):
    return service.get_ronda(conn, ronda_id)


@router.get("/rondas/{ronda_id}/members", response_model=list[int])
def ronda_members(ronda_id: int, conn: sqlite3.Connection = Depends(get_db)):
    return sorted(service.ronda_member_ids(conn, ronda_id))


@router.get(
    "/rondas/{ronda_id}/volunteers/{volunteer_id}/membership",
    response_model=Membership,
    responses={404: {"description": "Ronda or volunteer not found"}},
)
def membership(ronda_id: int, volunteer_id: int, conn: sqlite3.Connection = Depends(get_db)):
    return service.volunteer_membership(conn, ronda_id, volunteer_id)