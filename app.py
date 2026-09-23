import os
from contextlib import asynccontextmanager

from pathlib import Path#python's modern way of handling file paths, used to point at the web/ folder regardless of which OS someone is in

import uvicorn#server that runs FastAPI. listens to real network connections and calls fastAPI code when a request comes in.

from fastapi import FastAPI, Request #fastapi is instantiated when the app is created. request is a type hint used for error handling

from fastapi.responses import FileResponse, JSONResponse #fileresponse sends a file as a response and jsonresponse builds a json response by hand
from src.actas.routes import router as actas_router
from src.kraal.routes import router as kraal_router
from src.db import get_connection, init_db #get connection opens a SQLite connection and init_db runs schema.sql
from src.errors import DomainError #all errors are inherited.


WEB_DIR = Path(__file__).parent / "web"

@asynccontextmanager
async def lifespan(app: FastAPI): #defines an asynchronous generator function that takes the app instance as a parameter
    conn=get_connection()
    init_db(conn) #the schema is created on every start.no manual setup
    conn.close()
    yield #nothing behind so shutdown does nothing extra.


app = FastAPI(title="Guias Torrelodones", lifespan=lifespan)

app.include_router(kraal_router) #including routes created
app.include_router(actas_router)

#central error handler: runs whenever any route raises a domain error and doesn't catch it itself
@app.exception_handler(DomainError)
async def domain_error_handler(request: Request, exc: DomainError):
    return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})#each errror carries its own http status. hence no need for try and except in routes, they are managed here.


@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/")
def index():
    return FileResponse(WEB_DIR / "index.html")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
    
