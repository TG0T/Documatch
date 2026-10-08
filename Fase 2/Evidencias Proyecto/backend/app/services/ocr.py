"""Extracción de texto desde imágenes y PDF escaneados usando Tesseract."""
import io

import pymupdf
import pytesseract
from PIL import Image, ImageOps

from app import config

pytesseract.pytesseract.tesseract_cmd = config.TESSERACT_CMD

EXTENSIONES_IMAGEN = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}
EXTENSIONES_SOPORTADAS = EXTENSIONES_IMAGEN | {".pdf"}


def preprocesar(imagen: Image.Image) -> Image.Image:
    """Mejora la imagen para el OCR: escala de grises, contraste y tamaño mínimo."""
    imagen = ImageOps.exif_transpose(imagen)  # respeta la rotación de fotos de celular
    imagen = ImageOps.grayscale(imagen)
    imagen = ImageOps.autocontrast(imagen)
    # Tesseract funciona mejor con texto grande; escalamos imágenes pequeñas.
    if imagen.width < 1500:
        factor = 1500 / imagen.width
        imagen = imagen.resize((int(imagen.width * factor), int(imagen.height * factor)), Image.LANCZOS)
    return imagen


def ocr_imagen(imagen: Image.Image) -> str:
    return pytesseract.image_to_string(preprocesar(imagen), lang=config.OCR_LANG, config="--psm 3")


def extraer_texto_pdf(datos: bytes) -> str:
    paginas = []
    with pymupdf.open(stream=datos, filetype="pdf") as pdf:
        for pagina in pdf:
            # Si el PDF ya trae texto digital lo usamos directo (más rápido y exacto).
            texto = pagina.get_text().strip()
            if not texto:
                pix = pagina.get_pixmap(dpi=config.PDF_DPI)
                imagen = Image.open(io.BytesIO(pix.tobytes("png")))
                texto = ocr_imagen(imagen)
            paginas.append(texto)
    return "\n\n".join(paginas)


def extraer_texto(datos: bytes, extension: str) -> str:
    extension = extension.lower()
    if extension == ".pdf":
        return extraer_texto_pdf(datos)
    if extension in EXTENSIONES_IMAGEN:
        return ocr_imagen(Image.open(io.BytesIO(datos)))
    raise ValueError(f"Formato no soportado: {extension}")
