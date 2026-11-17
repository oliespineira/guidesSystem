from fastapi import APIRouter, Depends

from app.actas import albergues
from app.actas.schemas import BookingDone, BookingPlan
from app.api_models import ERROR_RESPONSES
from app.db import Connection, get_db
from app.messaging.notifier import Notifier
from app.messaging.routes import get_notifier

router = APIRouter(prefix="/api/actas", tags=["albergues"], responses=ERROR_RESPONSES)


@router.post("/calendar/{event_id}/booking", status_code=201)
def plan_booking(
    event_id: int, body: BookingPlan, conn: Connection = Depends(get_db), notifier: Notifier = Depends(get_notifier)
):
    return {"event_id": event_id, "book_by": albergues.plan_booking(conn, event_id, body.book_by, notifier)}


@router.post("/calendar/{event_id}/booking/done")
def mark_booked(
    event_id: int, body: BookingDone, conn: Connection = Depends(get_db), notifier: Notifier = Depends(get_notifier)
):
    albergues.mark_booked(conn, event_id, body.venue, body.request_id, notifier)
    return {"event_id": event_id, "status": "booked"}


@router.get("/bookings")
def list_bookings(ronda_id: int, conn: Connection = Depends(get_db)):
    return albergues.list_bookings(conn, ronda_id)
