import sqlite3
from fastapi import APIRouter, Depends

from src.db import get_db
from src.kraal import service
from src.kraal.schemas import RamaCreate, RamaMember, RoleAssign, RondaCreate, VolunteerCreate

router = APIRouter(prefix="/api/kraal", tags=["kraal"])


@router.post("/rondas", status_code=201)
def create_ronda(body: RondaCreate, conn: sqlite3.Connection = Depends(get_db)):
    return {"id": service.create_ronda(conn, body.year_label, body.start_date.isoformat())}


@router.get("/rondas")
def list_rondas(conn: sqlite3.Connection = Depends(get_db)):
    return service.list_rondas(conn)

@router.post("/volunteers", status_code=201)
def add_volunteer(body: VolunteerCreate, conn: sqlite3.Connection = Depends(get_db)):
    joined = body.joined_date.isoformat() if body.joined_date else None
    return {"id": service.add_volunteer(conn, body.name, joined)}

@router.post("/rondas/{ronda_id}/roles", status_code=201)
def assign_role(ronda_id: int, body: RoleAssign, conn: sqlite3.Connection = Depends(get_db)):
    return {"id": service.assign_role(conn, ronda_id, body.volunteer_id, body.role_name)}

@router.post("/rondas/{ronda_id}/ramas", status_code=201)
def create_rama(ronda_id: int, body: RamaCreate, conn: sqlite3.Connection = Depends(get_db)):
    return {"id": service.create_rama(conn, ronda_id, body.name)}


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