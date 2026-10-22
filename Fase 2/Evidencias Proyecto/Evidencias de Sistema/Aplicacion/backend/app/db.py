"""Conexión a la base de datos SQLite. El esquema está en "Base de Datos/schema.sql"."""
import hashlib
import logging
import sqlite3
from contextlib import closing

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app import config

log = logging.getLogger(__name__)

config.DATA_DIR.mkdir(parents=True, exist_ok=True)
config.ARCHIVOS_DIR.mkdir(parents=True, exist_ok=True)
config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# check_same_thread=False: FastAPI usa varios hilos y SQLite por defecto no lo permite.
engine = create_engine(config.DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False)


@event.listens_for(engine, "connect")
def activar_claves_foraneas(conexion, _):
    """SQLite solo revisa las claves foráneas (el enlace de guías y facturas con su OC) si se
    activa en cada conexión."""
    cursor = conexion.cursor()
    cursor.execute("PRAGMA foreign_keys = ON")
    cursor.close()


class Base(DeclarativeBase):
    pass


def get_db():
    """Dependencia de FastAPI: abre una sesión por request y la cierra al terminar."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def hash_archivo(datos: bytes) -> str:
    """Huella del archivo (SHA-256): dos subidas del mismo archivo tienen la misma."""
    return hashlib.sha256(datos).hexdigest()


def crear_base():
    """Crea las tablas, índices, triggers y vistas de schema.sql sin tocar los datos que ya existan.
    Al crear la base por primera vez copia los documentos de la base anterior (data/documentos.db)."""
    nueva = not config.DB_PATH.exists()
    agregar_columnas_faltantes()  # antes del esquema: sus índices pueden usar las columnas nuevas
    with closing(sqlite3.connect(config.DB_PATH)) as conexion:
        conexion.executescript(config.SCHEMA_PATH.read_text(encoding="utf-8"))
        if nueva and config.DB_ANTERIOR_PATH.exists():
            importar_base_anterior(conexion)


def agregar_columnas_faltantes():
    """CREATE TABLE IF NOT EXISTS no modifica tablas existentes: agrega las columnas nuevas de los
    modelos a una base creada con una versión anterior (sin perder los datos)."""
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


def importar_base_anterior(conexion: sqlite3.Connection):
    """Copia los documentos de la base anterior con sus mismos id. Los duplicados (mismo archivo, o
    mismo tipo y número) se omiten: queda el enlazado a su OC o, si no, el primero que se subió."""
    with closing(sqlite3.connect(config.DB_ANTERIOR_PATH)) as anterior:
        anterior.row_factory = sqlite3.Row
        # Primero las OC, para que las guías y facturas tengan a qué enlazarse; entre duplicados queda
        # el que estaba enlazado a su OC
        filas = anterior.execute("SELECT * FROM documentos ORDER BY tipo <> 'orden_compra', orden_id IS NULL, id"
                                 ).fetchall()
    columnas = {c[1] for c in conexion.execute("PRAGMA table_info(documentos)")}
    ordenes, omitidos = set(), 0
    for fila in filas:
        datos = {k: fila[k] for k in fila.keys() if k in columnas}
        datos["finalizada"] = datos.get("finalizada") or 0
        datos["dummy"] = datos.get("dummy") or 0
        if datos.get("orden_id") not in ordenes:  # su OC era un duplicado y no se copió
            datos["orden_id"] = None
        archivo = config.ARCHIVOS_DIR / datos["nombre_guardado"]
        if not datos["dummy"] and archivo.is_file():
            datos["hash_archivo"] = hash_archivo(archivo.read_bytes())
        try:
            conexion.execute(f"INSERT INTO documentos ({', '.join(datos)}) VALUES ({', '.join('?' * len(datos))})",
                             list(datos.values()))
        except sqlite3.IntegrityError:
            omitidos += 1
            continue
        if datos["tipo"] == "orden_compra":
            ordenes.add(datos["id"])
    conexion.commit()
    log.warning("Se copiaron %d documentos de %s (%d duplicados omitidos)",
                len(filas) - omitidos, config.DB_ANTERIOR_PATH, omitidos)
