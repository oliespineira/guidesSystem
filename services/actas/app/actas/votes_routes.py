from app.db import Connection

from fastapi import APIRouter, Depends

from app.actas import votes
from app.actas.schemas import VoteCast, VoteOpen
from app.api_models import ERROR_RESPONSES
from app.db import get_db
from app.messaging.notifier import Notifier
from app.messaging.routes import get_notifier

router = APIRouter(prefix="/api/actas/decisions", tags=["votaciones"], responses=ERROR_RESPONSES)


@router.post("/{decision_id}/vote", status_code=201)
def open_vote(decision_id: int, body: VoteOpen, conn: Connection = Depends(get_db),
              notifier: Notifier = Depends(get_notifier)):
    votes.open_vote(conn, decision_id, body.closes_at, body.rule, notifier)
    return votes.tally(conn, decision_id)


@router.post("/{decision_id}/votes", status_code=201)
def cast_vote(decision_id: int, body: VoteCast, conn: Connection = Depends(get_db)):
    return {"id": votes.cast_vote(conn, decision_id, body.volunteer_id, body.choice)}


@router.get("/{decision_id}/votes")
def tally(decision_id: int, conn: Connection = Depends(get_db)):
    return votes.tally(conn, decision_id)


@router.post("/{decision_id}/vote/close")
def close_vote(decision_id: int, conn: Connection = Depends(get_db),
               notifier: Notifier = Depends(get_notifier)):
    return {"result": votes.close_vote(conn, decision_id, notifier)}