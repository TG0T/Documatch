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

# Carpeta donde se guardan los archivos subidos y la base de datos SQLite.
DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "data"))
ARCHIVOS_DIR = DATA_DIR / "archivos"
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{(DATA_DIR / 'documentos.db').as_posix()}")

# Orígenes permitidos para el frontend (Vite usa el puerto 5173 por defecto).
CORS_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]
