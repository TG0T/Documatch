"""Conexión a la base de datos (SQLite por defecto)."""
from sqlalchemy import create_engine, inspect, text
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


def agregar_columnas_faltantes():
    """create_all no modifica tablas existentes: agrega las columnas nuevas de los modelos
    a una base creada con una versión anterior (sin perder los datos)."""
    inspector = inspect(engine)
    with engine.begin() as conexion:
        for tabla in Base.metadata.sorted_tables:
            if not inspector.has_table(tabla.name):
                continue
            existentes = {c["name"] for c in inspector.get_columns(tabla.name)}
            for columna in tabla.columns:
                if columna.name not in existentes:
                    tipo = columna.type.compile(engine.dialect)
                    conexion.execute(text(f'ALTER TABLE {tabla.name} ADD COLUMN "{columna.name}" {tipo}'))
