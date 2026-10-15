import os
import tempfile

# Las pruebas usan una base y carpeta de archivos temporales, nunca data/ real.
# Debe definirse antes de que se importe app.config.
os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="capstone_test_")
