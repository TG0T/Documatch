"""Conexión a la base de datos (SQLite por defecto)."""
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app import config

config.DATA_DIR.mkdir(parents=True, exist_ok=True)
config.ARCHIVOS_DIR.mkdir(parents=True, exist_ok=True)

# check_same_thread=False: FastAPI usa varios hilos y SQLite por defecto no lo permite.
engine = create_engine(config.DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_db():
    """Dependencia de FastAPI: abre una sesión por request y la cierra al terminar."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
