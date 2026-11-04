"""FastAPI application: fully local, one process. Run from backend:
    python -m uvicorn app.main:app --port 8000
"""
from __future__ import annotations

import contextlib

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import pg
from .routers import consents, ingest, omr_api, read, system, write


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    pg.database_uri()  # start or attach to the local PostgreSQL
    pg.apply_schema()  # no-op when already applied
    yield


app = FastAPI(title="Pragati backend", version="0.1", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=[], allow_origin_regex=r"^http://(localhost|127\.0\.0\.1)(:\d+)?$",
                   allow_methods=["*"], allow_headers=["*"], allow_credentials=False)

app.include_router(system.router)
app.include_router(system.router, prefix="/api/v1")
app.include_router(omr_api.router)
app.include_router(ingest.router)
app.include_router(write.router)
app.include_router(consents.router)
app.include_router(read.router)
