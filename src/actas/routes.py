import sqlite3
from fastapi import APIRouter, Depends


from src.actas import service
from src.actas.schemas import(
    AgendaItemCreate,
    CalendarEventCreate,
    DecisionCreate,
    MeetingCreate,
)#used to validate incoming requests.

from src.db import get_db #the generator function opens a connection, yields it and closes it in a finally block once the request is done.

router = APIRouter(prefix="/api/actas", tags=["actas"])

@router.post("/meetings", status_code=201)
def create_meeting(body:MeetingCreate, conn: sqlite3.Connection = Depends(get_db)):
    return {"id": service.create_meeting(conn, body.ronda_id, body.date.isoformat(), body.title)}

@router.get("/meetings")
def list_meetings(ronda_id: int, conn: sqlite3.Connection = Depends(get_db)):
    return service.list_meetings(conn, ronda_id)

@router.get("/meetings/{meeting_id}")
def meeting_summary(meeting_id: int, conn: sqlite3.Connection = Depends(get_db)):
    return service.meeting_summary(conn, meeting_id)

@router.post("/meetings/{meeting_id}/agenda", status_code=201)
def add_agenda_item(meeting_id: int, body: AgendaItemCreate, conn: sqlite3.Connection = Depends(get_db)):
    item_id = service.add_agenda_item(conn, meeting_id, body.section_title, body.content, body.position)
    return {"id": item_id}

@router.post("/agenda/{agenda_item_id}/decisions", status_code=201)
def record_decision(agenda_item_id: int, body: DecisionCreate, conn: sqlite3.Connection = Depends(get_db)):
    decision_id = service.record_decision(conn, agenda_item_id, body.description, body.vote_result)
    return {"id": decision_id}


@router.post("/calendar", status_code=201)
def add_calendar_event(body: CalendarEventCreate, conn: sqlite3.Connection = Depends(get_db)):
    event_id = service.add_calendar_event(
        conn, body.ronda_id, body.start_date.isoformat(), body.activity_type,
        body.end_date.isoformat() if body.end_date else None,
        body.assigned_volunteers,
    )
    return {"id": event_id}

@router.get("/calendar")
def list_calendar(ronda_id: int, conn: sqlite3.Connection = Depends(get_db)):
    return service.list_calendar(conn, ronda_id)