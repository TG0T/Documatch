from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import config, models  # noqa: F401  (models registra las tablas en Base)
from app.api import documentos
from app.db import Base, engine

# Crea las tablas si no existen (suficiente para SQLite en desarrollo)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Clasificador de documentos")

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documentos.router)


@app.get("/api/salud")
def salud():
    return {"estado": "ok"}
