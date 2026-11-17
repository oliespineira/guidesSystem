from fastapi import APIRouter, Depends

from app.api_models import ERROR_RESPONSES, CreatedOut
from app.db import Connection, get_db
from app.kraal import service
from app.kraal.schemas import Membership, RamaCreate, RamaMember, RoleAssign, RondaCreate, RondaOut, VolunteerCreate

router = APIRouter(prefix="/api/kraal", tags=["kraal"], responses=ERROR_RESPONSES)


@router.post("/rondas", status_code=201, response_model=CreatedOut)
def create_ronda(body: RondaCreate, conn: Connection = Depends(get_db)):
    return {"id": service.create_ronda(conn, body.year_label, body.start_date.isoformat())}


@router.get("/rondas")
def list_rondas(conn: Connection = Depends(get_db)):
    return service.list_rondas(conn)


@router.get("/volunteers")
def list_volunteers(conn: Connection = Depends(get_db)):
    return service.list_volunteers(conn)


@router.post("/volunteers", status_code=201, response_model=CreatedOut)
def add_volunteer(body: VolunteerCreate, conn: Connection = Depends(get_db)):
    joined = body.joined_date.isoformat() if body.joined_date else None
    return {"id": service.add_volunteer(conn, body.name, joined)}


@router.post("/rondas/{ronda_id}/roles", status_code=201, response_model=CreatedOut)
def assign_role(ronda_id: int, body: RoleAssign, conn: Connection = Depends(get_db)):
    return {"id": service.assign_role(conn, ronda_id, body.volunteer_id, body.role_name)}


@router.get("/rondas/{ronda_id}/roles")
def list_roles(ronda_id: int, conn: Connection = Depends(get_db)):
    return service.list_roles(conn, ronda_id)


@router.post("/rondas/{ronda_id}/ramas", status_code=201, response_model=CreatedOut)
def create_rama(ronda_id: int, body: RamaCreate, conn: Connection = Depends(get_db)):
    return {"id": service.create_rama(conn, ronda_id, body.name)}


@router.get("/rondas/{ronda_id}/ramas")
def list_ramas(ronda_id: int, conn: Connection = Depends(get_db)):
    return service.list_ramas(conn, ronda_id)


@router.post("/ramas/{rama_id}/members", status_code=201, response_model=CreatedOut)
def add_member(rama_id: int, body: RamaMember, conn: Connection = Depends(get_db)):
    return {"id": service.assign_to_rama(conn, rama_id, body.volunteer_id,
                                         body.availability_pct, body.notes)}


@router.get("/rondas/{ronda_id}/roster")
def roster(ronda_id: int, conn: Connection = Depends(get_db)):
    return service.get_roster(conn, ronda_id)


@router.get("/continuity")
def continuity(prev: int, new: int, conn: Connection = Depends(get_db)):
    return service.continuity_report(conn, prev, new)


# Read endpoints actas calls across the seam (their shapes are the contract in openapi.json).
@router.get("/rondas/{ronda_id}", response_model=RondaOut)
def get_ronda(ronda_id: int, conn: Connection = Depends(get_db)):
    return service.get_ronda(conn, ronda_id)


@router.get("/rondas/{ronda_id}/members", response_model=list[int])
def ronda_members(ronda_id: int, conn: Connection = Depends(get_db)):
    return sorted(service.ronda_member_ids(conn, ronda_id))


@router.get("/rondas/{ronda_id}/volunteers/{volunteer_id}/membership", response_model=Membership)
def membership(ronda_id: int, volunteer_id: int, conn: Connection = Depends(get_db)):
    return service.volunteer_membership(conn, ronda_id, volunteer_id)