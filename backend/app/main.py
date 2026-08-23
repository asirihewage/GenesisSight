"""FastAPI application entry point."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import health, persons, search, setup, videos, ws
from app.config import settings
from app.core.worker import worker
from app.database import init_db

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logger = logging.getLogger("app")

# File logging: the packaged (windowed) app has no console, so everything goes
# to <storage>/logs/app.log as well.
try:
    _logs_dir = Path(settings.storage_dir) / "logs"
    _logs_dir.mkdir(parents=True, exist_ok=True)
    _file_handler = logging.FileHandler(_logs_dir / "app.log", encoding="utf-8")
    _file_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"))
    for _lg_name in ("", "app", "uvicorn", "uvicorn.error", "uvicorn.access"):
        logging.getLogger(_lg_name).addHandler(_file_handler)
        logging.getLogger(_lg_name).propagate = True
except Exception:
    logger.exception("Could not set up file logging")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    await worker.start()
    logger.info("%s started (device: %s, DB: %s)",
                settings.app_name, settings.torch_device, settings.database_url)
    yield
    await worker.stop()


app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        f"http://localhost:{settings.frontend_port}",
        f"http://127.0.0.1:{settings.frontend_port}",
        f"http://localhost:{settings.api_port}",
        f"http://127.0.0.1:{settings.api_port}",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(videos.router)
app.include_router(persons.router)
app.include_router(search.router)
app.include_router(health.router)
app.include_router(ws.router)
app.include_router(setup.router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# Media (frames, crops, event images)
_storage = Path(settings.storage_dir)
_storage.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=_storage), name="media")


# Built frontend (prod mode / single binary): serve SPA with API/media priority.
_dist = None
_candidates = [
    Path(__file__).resolve().parents[2] / "frontend" / "dist",  # dev (repo layout)
]
try:
    import sys as _sys

    if getattr(_sys, "_MEIPASS", None):  # PyInstaller onedir -> _internal/
        _candidates.insert(0, Path(_sys._MEIPASS) / "frontend" / "dist")
except Exception:
    pass
if os.getenv("FRONTEND_DIST"):
    _candidates.insert(0, Path(os.environ["FRONTEND_DIST"]))
for _cand in _candidates:
    if _cand.exists() and _cand.is_dir():
        _dist = _cand
        break
del _cand, _candidates
if _dist is not None:
    app.mount("/assets", StaticFiles(directory=_dist / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        candidate = (_dist / full_path).resolve()
        if full_path and candidate.is_file() and str(candidate).startswith(str(_dist.resolve())):
            return FileResponse(candidate)
        index = _dist / "index.html"
        return FileResponse(index) if index.exists() else JSONResponse(
            status_code=404, content={"detail": "Frontend build missing — run: npm run build"}
        )
else:
    @app.get("/", include_in_schema=False)
    async def root():
        return {"app": settings.app_name, "docs": "/docs", "message": "API is running. Start the frontend with `python start.py` or `npm run dev`."}
