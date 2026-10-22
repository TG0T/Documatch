import os
from pathlib import Path

# Carpeta raíz del backend (donde está requirements.txt)
BASE_DIR = Path(__file__).resolve().parent.parent

# Ruta al ejecutable de Tesseract. Se puede sobrescribir con la variable de entorno TESSERACT_CMD.
TESSERACT_CMD = os.getenv("TESSERACT_CMD", r"C:\Program Files\Tesseract-OCR\tesseract.exe")

# Idioma(s) para el OCR (deben estar instalados en tessdata).
OCR_LANG = os.getenv("OCR_LANG", "spa")

# Resolución con la que se renderizan las páginas de PDF antes del OCR.
PDF_DPI = 300

# Tamaño máximo de archivo aceptado (bytes).
MAX_FILE_SIZE = 20 * 1024 * 1024

# Carpeta donde se guardan los archivos subidos.
DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "data"))
ARCHIVOS_DIR = DATA_DIR / "archivos"

# Base de datos SQLite: el esquema (schema.sql) está en "Evidencias de Sistema/Base de Datos" y la
# base se crea en la misma carpeta. DB_PATH permite usar otro archivo (los tests usan uno temporal).
BASE_DATOS_DIR = BASE_DIR.parent.parent / "Base de Datos"
SCHEMA_PATH = BASE_DATOS_DIR / "schema.sql"
DB_PATH = Path(os.getenv("DB_PATH", BASE_DATOS_DIR / "documatch.db"))
DATABASE_URL = f"sqlite:///{DB_PATH.as_posix()}"
# Base de versiones anteriores (en DATA_DIR): si existe, sus documentos se copian a la nueva al crearla.
DB_ANTERIOR_PATH = DATA_DIR / "documentos.db"

# Orígenes permitidos para el frontend (Vite usa el puerto 5173 por defecto).
CORS_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]
