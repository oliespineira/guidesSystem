import asyncio
import contextlib
import os
import time
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.actas.albergues_routes import router as albergues_router
from app.actas.albergues_task import booking_reminder_loop
from app.actas.policies import get_policy
from app.actas.routes import router as actas_router
from app.actas.tesoreria_routes import router as tesoreria_router
from app.actas.votes_routes import router as votes_router
from app.api_models import HealthOut
from app.db import get_connection, wait_for_db
from app.errors import DomainError
from app.messaging.broker import Broker
from app.messaging.notifier import BrokerNotifier
from app.messaging.routes import router as avisos_router
from app.migrate import run_migrations


@asynccontextmanager
async def lifespan(app: FastAPI):
    conn = wait_for_db()  # retries while the database starts or resumes from pause
    run_migrations(conn)  # applies only the migrations not yet recorded
    conn.close()
    get_policy()  # fail at startup if APPROVAL_POLICY is invalid
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.environ.get("UI_ORIGIN", "http://localhost:8080")],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Last-Event-ID"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        duration_ms = (time.perf_counter() - start) * 1000
        print(f"{request.method} {request.url.path} {status} {duration_ms:.0f}ms", flush=True)


@app.exception_handler(DomainError)
async def domain_error_handler(request: Request, exc: DomainError):
    return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})


@app.get(
    "/health",
    response_model=HealthOut,
    responses={503: {"model": HealthOut, "description": "Cannot read and write its own database"}},
)
def health():
    version = os.environ.get("GIT_SHA", "local")
    try:
        conn = get_connection(attempts=1)
        try:
            conn.execute("INSERT INTO schema_migrations (version) VALUES ('health-probe')")
            conn.execute("SELECT version FROM schema_migrations WHERE version = 'health-probe'").fetchone()
        finally:
            conn.rollback()
            conn.close()
    except Exception:
        return JSONResponse(status_code=503, content={"status": "error", "db": "error", "version": version})
    return {"status": "ok", "db": "ok", "version": version}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port, timeout_graceful_shutdown=3, access_log=False)
