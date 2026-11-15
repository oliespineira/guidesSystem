import asyncio
import contextlib
import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.actas.albergues_routes import router as albergues_router
from app.actas.albergues_task import booking_reminder_loop
from app.actas.policies import get_policy
from app.actas.routes import router as actas_router
from app.actas.tesoreria_routes import router as tesoreria_router
from app.actas.votes_routes import router as votes_router
from app.db import get_connection, init_db
from app.errors import DomainError
from app.messaging.broker import Broker
from app.messaging.notifier import BrokerNotifier
from app.messaging.routes import router as avisos_router
#Now we need 3 terminal all starting from GuidesSystem, both services can't use port 8000 at the same time, so each one gets ist own port
#keeps 3 things that the main.py had before because they belong to actas: the broker and notifier, the reminder loop and the shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    conn = get_connection()
    init_db(conn)
    conn.close()
    get_policy()
    broker = Broker(asyncio.get_running_loop())
    app.state.broker = broker
    app.state.notifier = BrokerNotifier(broker)
    reminders = asyncio.create_task(booking_reminder_loop(app.state.notifier))
    yield
    reminders.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await reminders
    broker.close()


app = FastAPI(title="Guias Torrelodones - Actas", lifespan=lifespan)
app.include_router(actas_router)
app.include_router(tesoreria_router)
app.include_router(avisos_router)
app.include_router(votes_router)
app.include_router(albergues_router)


@app.exception_handler(DomainError)
async def domain_error_handler(request: Request, exc: DomainError):
    return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port, timeout_graceful_shutdown=3)