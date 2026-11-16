import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.db import wait_for_db
from app.errors import DomainError
from app.kraal.routes import router as kraal_router
from app.migrate import run_migrations


@asynccontextmanager
async def lifespan(app: FastAPI):
    conn = wait_for_db()        # retries while the database starts or resumes from pause
    run_migrations(conn)        # applies only the migrations not yet recorded in schema_migrations
    conn.close()
    yield


app = FastAPI(title="Guias Torrelodones - Kraal", lifespan=lifespan)
app.include_router(kraal_router)


@app.exception_handler(DomainError)
async def domain_error_handler(request: Request, exc: DomainError):
    return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)