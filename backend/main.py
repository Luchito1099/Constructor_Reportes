"""Punto de entrada FastAPI del Panel de Luchito.

Sirve la API (/api/*) y el frontend estático (Reportes.dc.html + support.js).
Correr en local:  uvicorn main:app --reload
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from ai_proxy import router as ai_router
from config import PROJECT_DIR
from db import init_db
from routes_admin import router as admin_router
from routes_auth import router as auth_router
from routes_data import router as data_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()          # crea tablas y aplica migraciones ligeras al arrancar
    yield


app = FastAPI(title="Panel de Luchito", lifespan=lifespan)

app.include_router(auth_router)
app.include_router(data_router)
app.include_router(ai_router)
app.include_router(admin_router)


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


# --- Frontend estático -------------------------------------------------------
FRONT_DIR = Path(PROJECT_DIR)
APP_FILE = FRONT_DIR / "Reportes.dc.html"


@app.get("/")
def index() -> FileResponse:
    return FileResponse(APP_FILE)


# El resto de archivos (support.js, etc.) se sirven como estáticos. Se monta al
# final para no pisar las rutas /api/*.
app.mount("/", StaticFiles(directory=str(FRONT_DIR), html=False), name="static")
