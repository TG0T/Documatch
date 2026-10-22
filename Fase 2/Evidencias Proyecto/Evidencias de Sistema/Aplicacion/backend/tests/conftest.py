import os
import tempfile

# Las pruebas usan una base y carpeta de archivos temporales, nunca las reales.
# Debe definirse antes de que se importe app.config.
os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="capstone_test_")
os.environ["DB_PATH"] = os.path.join(os.environ["DATA_DIR"], "documatch.db")
