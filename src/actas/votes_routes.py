import sqlite3

from fastapi import APIRouter, Depends

from src.actas import votes
from src.actas.schemas import VoteCast, VoteOpen
from src.db import get_db
from src.messaging.notifier import Notifier
from src.messaging.routes import get_notifier

router = APIRouter(prefix="/api/actas/decisions", tags=["votaciones"])


@router.post("/{decision_id}/vote", status_code=201)
def open_vote(decision_id: int, body: VoteOpen, conn: sqlite3.Connection = Depends(get_db),
              notifier: Notifier = Depends(get_notifier)):
    votes.open_vote(conn, decision_id, body.closes_at, body.rule, notifier)
    return votes.tally(conn, decision_id)


@router.post("/{decision_id}/votes", status_code=201)
def cast_vote(decision_id: int, body: VoteCast, conn: sqlite3.Connection = Depends(get_db)):
    return {"id": votes.cast_vote(conn, decision_id, body.volunteer_id, body.choice)}


@router.get("/{decision_id}/votes")
def tally(decision_id: int, conn: sqlite3.Connection = Depends(get_db)):
    return votes.tally(conn, decision_id)


@router.post("/{decision_id}/vote/close")
def close_vote(decision_id: int, conn: sqlite3.Connection = Depends(get_db),
               notifier: Notifier = Depends(get_notifier)):
    return {"result": votes.close_vote(conn, decision_id, notifier)}