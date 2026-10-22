from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import config, models  # noqa: F401  (models registra las tablas en Base)
from app.api import dashboard, documentos
from app.db import crear_base

# Crea la base (Base de Datos/schema.sql) si no existe
crear_base()

app = FastAPI(title="Clasificador de documentos")

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documentos.router)
app.include_router(dashboard.router)


@app.get("/api/salud")
def salud():
    return {"estado": "ok"}
