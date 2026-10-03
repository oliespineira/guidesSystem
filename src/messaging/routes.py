import asyncio
import json
import sqlite3

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import StreamingResponse

from src.db import get_connection, get_db, require_row
from src.kraal.service import topics_for_volunteer
from src.messaging.notifier import Notifier, notices_since
from src.messaging.schemas import NoticeCreate
from src.messaging.topics import notice_topic

router = APIRouter(prefix="/api/avisos", tags=["avisos"])

def get_notifier( request: Request)-> Notifier:
    """FastAPI dependency: the one Notifier created at startup (see lifespan in app.py)."""
    return request.app.state.notifier

@router.post("", status_code=201)
def post_notice(body: NoticeCreate, conn: sqlite3.Connection = Depends(get_db),
                notifier: Notifier = Depends(get_notifier)):
    require_row(conn, "rondas", body.ronda_id)
    topic = notice_topic(body.ronda_id, body.audience, body.target)
    return {"id": notifier.notify(conn, topic, body.title, body.body), "topic": topic}


@router.get("/topics")
def my_topics(ronda_id: int, volunteer_id: int, conn: sqlite3.Connection = Depends(get_db)):
    return topics_for_volunteer(conn, ronda_id, volunteer_id)


def _sse(notice: dict) -> str:
    # Server-Sent Events format: an id line, an event name, the data, then a blank line.
    return f"id: {notice['id']}\nevent: notice\ndata: {json.dumps(notice)}\n\n"


@router.get("/stream")
async def stream(request: Request, ronda_id: int, volunteer_id: int,
                 last_event_id: int | None = Header(default=None)):
    broker = request.app.state.broker
    # A short-lived connection of our own, not Depends(get_db): a stream stays open for
    # minutes, and get_db would keep its connection open for the stream's whole life.
    conn = get_connection()
    try:
        patterns = topics_for_volunteer(conn, ronda_id, volunteer_id)
        sub = broker.subscribe(patterns)                              # 1. subscribe FIRST...
        backlog = notices_since(conn, patterns, last_event_id or 0)   # 2. ...then read what was missed
    finally:
        conn.close()

    async def events():
        sent = last_event_id or 0
        try:
            yield "retry: 3000\n\n"                            # browser: reconnect after 3 s if cut
            for notice in backlog:
                yield _sse(notice)
                sent = notice["id"]
            while True:
                try:
                    notice = await asyncio.wait_for(sub.queue.get(), timeout=15)
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"                   # comment line keeps the connection alive
                    continue
                if notice is None:                             # broker.close() on shutdown
                    break
                if notice["id"] > sent:                        # skip anything the backlog already sent
                    yield _sse(notice)
                    sent = notice["id"]
        finally:
            broker.unsubscribe(sub)                            # tab closed: stop delivering to it

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache"})
