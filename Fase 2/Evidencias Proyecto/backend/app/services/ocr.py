"""Extracción de texto desde imágenes y PDF escaneados usando Tesseract."""
import io
from dataclasses import dataclass

import numpy as np
import pymupdf
import pytesseract
from PIL import Image, ImageOps

from app import config

pytesseract.pytesseract.tesseract_cmd = config.TESSERACT_CMD

EXTENSIONES_IMAGEN = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}
EXTENSIONES_SOPORTADAS = EXTENSIONES_IMAGEN | {".pdf"}

# Desde este tono de gris (0 negro, 255 blanco) se considera fondo: el sombreado de las
# celdas de encabezado queda en ~190 y el texto y los bordes bajo ~100.
GRIS_FONDO = 170


@dataclass
class Palabra:
    """Una palabra con su caja en la página. Se usa para leer tablas por columnas."""
    texto: str
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def cx(self) -> float:
        return (self.x0 + self.x1) / 2

    @property
    def cy(self) -> float:
        return (self.y0 + self.y1) / 2

    @property
    def alto(self) -> float:
        return self.y1 - self.y0


@dataclass
class Extraccion:
    texto: str
    paginas: list[list[Palabra]]  # palabras de cada página, con su posición


def tramos_largos(oscuro: np.ndarray, largo: int) -> np.ndarray:
    """True en los píxeles que forman parte de un tramo horizontal de al menos `largo`
    píxeles oscuros seguidos (las líneas de una tabla; las letras nunca son tan anchas)."""
    alto, ancho = oscuro.shape
    if ancho < largo:
        return np.zeros_like(oscuro)
    # Suma acumulada por fila: la ventana [i, i + largo) es una línea si todos sus píxeles son oscuros.
    suma = np.zeros((alto, ancho + 1), np.int32)
    np.cumsum(oscuro, axis=1, out=suma[:, 1:])
    ventana_llena = (suma[:, largo:] - suma[:, :-largo]) == largo
    # Un píxel es línea si cae dentro de alguna ventana llena.
    llenas = np.zeros((alto, ventana_llena.shape[1] + 1), np.int32)
    np.cumsum(ventana_llena, axis=1, out=llenas[:, 1:])
    j = np.arange(ancho)
    hasta = np.minimum(j, ventana_llena.shape[1] - 1) + 1
    desde = np.maximum(j - largo + 1, 0)
    return (llenas[:, hasta] - llenas[:, desde]) > 0


def invertir_franjas(a: np.ndarray, largo: int) -> None:
    """Las franjas oscuras gruesas (encabezados de tabla con texto blanco sobre color) se
    invierten para que el texto quede negro sobre blanco. Las líneas finas no se tocan."""
    franja = tramos_largos(a < GRIS_FONDO, largo)
    filas = np.flatnonzero(franja.any(axis=1))
    if filas.size == 0:
        return
    alto_minimo = max(a.shape[1] // 150, 6)  # más grueso que cualquier borde de tabla
    # Grupos de filas consecutivas con tramos oscuros largos.
    cortes = np.flatnonzero(np.diff(filas) > 1) + 1
    for grupo in np.split(filas, cortes):
        y0, y1 = grupo[0], grupo[-1] + 1
        if y1 - y0 < alto_minimo:
            continue
        columnas = np.flatnonzero(franja[y0:y1].any(axis=0))
        x0, x1 = columnas[0], columnas[-1] + 1
        region = a[y0:y1, x0:x1]
        if (region < GRIS_FONDO).mean() >= 0.5:  # de verdad es un relleno oscuro
            # Lo más claro que el fondo de la franja es el texto: queda negro y el resto blanco.
            umbral = (int(np.median(region)) + 255) // 2
            a[y0:y1, x0:x1] = np.where(region > umbral, 0, 255)


def quitar_lineas(imagen: Image.Image) -> Image.Image:
    """Borra los bordes y el sombreado gris de las tablas. Con ellos Tesseract confunde las
    celdas con dibujos y se salta su contenido (en una OC dejaba fuera toda la fila del ítem)."""
    a = np.array(imagen)
    largo = max(imagen.width // 25, 30)
    invertir_franjas(a, largo)
    # Sombreado y bordes grises: tramos largos (horizontales o verticales) de gris claro. Solo se
    # blanquean esos píxeles grises, para no adelgazar el borde suavizado de las letras en el
    # resto de la página. Un borde gris pegado a un número hacía leer "849.000|" como "249.000".
    no_blanco = a < 235
    gris = tramos_largos(no_blanco, largo) | tramos_largos(no_blanco.T, largo).T
    a[gris & (a >= GRIS_FONDO)] = 255
    oscuro = a < GRIS_FONDO
    horizontales = tramos_largos(oscuro, largo)
    verticales = tramos_largos(oscuro.T, largo).T
    # El borde suavizado de cada línea queda un píxel a cada lado.
    horizontales |= np.roll(horizontales, 1, 0) | np.roll(horizontales, -1, 0)
    verticales |= np.roll(verticales, 1, 1) | np.roll(verticales, -1, 1)
    a[horizontales | verticales] = 255
    return Image.fromarray(a)


def preprocesar(imagen: Image.Image) -> Image.Image:
    """Mejora la imagen para el OCR: escala de grises, contraste, tamaño mínimo y sin líneas de tabla."""
    imagen = ImageOps.exif_transpose(imagen)  # respeta la rotación de fotos de celular
    imagen = ImageOps.grayscale(imagen)
    imagen = ImageOps.autocontrast(imagen)
    # Tesseract funciona mejor con texto grande; escalamos imágenes pequeñas.
    if imagen.width < 1500:
        factor = 1500 / imagen.width
        imagen = imagen.resize((int(imagen.width * factor), int(imagen.height * factor)), Image.LANCZOS)
    return quitar_lineas(imagen)


def ocr_imagen(imagen: Image.Image) -> tuple[str, list[Palabra]]:
    """Devuelve el texto y las palabras con posición en una sola pasada de Tesseract."""
    datos = pytesseract.image_to_data(
        preprocesar(imagen), lang=config.OCR_LANG, config="--psm 3", output_type=pytesseract.Output.DICT
    )
    palabras = []
    lineas: dict[tuple, list[str]] = {}
    for i, texto in enumerate(datos["text"]):
        texto = texto.strip()
        if not texto:
            continue
        x, y = datos["left"][i], datos["top"][i]
        palabras.append(Palabra(texto, x, y, x + datos["width"][i], y + datos["height"][i]))
        lineas.setdefault((datos["block_num"][i], datos["par_num"][i], datos["line_num"][i]), []).append(texto)

    # Reconstruye el texto como lo haría image_to_string: una línea por renglón y una
    # línea en blanco entre bloques.
    partes, bloque_anterior = [], None
    for (bloque, _, _), linea in lineas.items():
        if bloque_anterior is not None and bloque != bloque_anterior:
            partes.append("")
        partes.append(" ".join(linea))
        bloque_anterior = bloque
    return "\n".join(partes), palabras


def extraer_pdf(datos: bytes) -> Extraccion:
    textos, paginas = [], []
    with pymupdf.open(stream=datos, filetype="pdf") as pdf:
        for pagina in pdf:
            # Si el PDF ya trae texto digital lo usamos directo (más rápido y exacto).
            texto = pagina.get_text().strip()
            if texto:
                palabras = [Palabra(p[4], *p[:4]) for p in pagina.get_text("words")]
            else:
                pix = pagina.get_pixmap(dpi=config.PDF_DPI)
                texto, palabras = ocr_imagen(Image.open(io.BytesIO(pix.tobytes("png"))))
            textos.append(texto)
            paginas.append(palabras)
    return Extraccion("\n\n".join(textos), paginas)


def extraer(datos: bytes, extension: str) -> Extraccion:
    extension = extension.lower()
    if extension == ".pdf":
        return extraer_pdf(datos)
    if extension in EXTENSIONES_IMAGEN:
        texto, palabras = ocr_imagen(Image.open(io.BytesIO(datos)))
        return Extraccion(texto, [palabras])
    raise ValueError(f"Formato no soportado: {extension}")
