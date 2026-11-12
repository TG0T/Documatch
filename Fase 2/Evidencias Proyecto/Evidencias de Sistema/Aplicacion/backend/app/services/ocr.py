"""Extracción de texto desde imágenes y PDF escaneados usando Tesseract."""
import io
import re
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

# Inclinación máxima (grados) que se corrige en un escaneo. Más que esto es una página girada a
# propósito (se respeta la orientación EXIF de las fotos) y no un escaneo chueco.
INCLINACION_MAXIMA = 3

# Confianza mínima (0-100) para usar una palabra de la segunda lectura (texto disperso). Las
# celdas bien leídas quedan sobre 90 y la basura de timbres y bordes bajo 80.
CONFIANZA_SEGUNDA_LECTURA = 85

# Bajo esta confianza una palabra corta se vuelve a leer como número (las palabras bien leídas de
# una tabla, como "UN" o "CAJA", quedan sobre 90; un "7" mal leído como "TA" queda en ~40).
CONFIANZA_DUDOSA = 70

# Separación máxima (en altos de letra) entre dos pedazos de un número que Tesseract partió. Un
# espacio normal entre palabras mide ~0,4 altos de letra; un número partido queda casi pegado.
ESPACIO_NUMERO_PARTIDO = 0.3


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
        region = a[y0:y1, x0:x1].astype(float)
        if (region < GRIS_FONDO).mean() >= 0.5:  # de verdad es un relleno oscuro
            # Inversión gradual: el fondo de la franja queda blanco y el texto (más claro) negro,
            # conservando el borde suavizado de las letras. Pasarlo a blanco y negro puro deformaba
            # las letras finas ("Total" se leía "Teral", "Descripción" como "Descr-pcitan").
            fondo = np.median(region)
            a[y0:y1, x0:x1] = np.clip(255 - (region - fondo) * 255 / max(255 - fondo, 1), 0, 255).astype(np.uint8)


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


def nitidez_horizontal(muestra: Image.Image, angulo: float) -> int:
    """Qué tan marcadas quedan las líneas de texto al girar la muestra: con el texto derecho cada
    renglón es una franja oscura seguida de una clara, y los saltos entre filas son máximos."""
    oscuro = np.array(muestra.rotate(angulo, resample=Image.NEAREST, fillcolor=255)) < 128
    perfil = oscuro.sum(axis=1).astype(np.int64)
    return int(np.sum(np.diff(perfil) ** 2))


def angulo_inclinacion(imagen: Image.Image) -> float:
    """Ángulo (en grados) que endereza una página escaneada algo chueca, hasta INCLINACION_MAXIMA.
    Se busca primero de a 0,25° y después se afina de a 0,05° (sobre una copia chica: es rápido)."""
    muestra = imagen.copy()
    muestra.thumbnail((1000, 1000))
    grueso = max(np.arange(-INCLINACION_MAXIMA, INCLINACION_MAXIMA + 0.01, 0.25),
                 key=lambda a: nitidez_horizontal(muestra, a))
    return float(max(np.arange(grueso - 0.25, grueso + 0.26, 0.05), key=lambda a: nitidez_horizontal(muestra, a)))


def enderezar(imagen: Image.Image) -> Image.Image:
    """Endereza un escaneo torcido. Con 1° de giro, en una tabla ancha la cantidad queda ~15 px más
    arriba que su descripción y se leían como filas distintas; las líneas de la tabla tampoco
    se podían borrar."""
    angulo = angulo_inclinacion(imagen)
    if abs(angulo) < 0.1:
        return imagen
    return imagen.rotate(angulo, resample=Image.BICUBIC, fillcolor=255)


def preprocesar(imagen: Image.Image) -> Image.Image:
    """Mejora la imagen para el OCR: escala de grises, contraste, tamaño mínimo y sin líneas de tabla."""
    imagen = ImageOps.exif_transpose(imagen)  # respeta la rotación de fotos de celular
    # Gris = promedio entre la luminancia y el canal más oscuro, para que el texto de color quede
    # más oscuro. Con solo la luminancia un título rojo ("GUIA DE DESPACHO") quedaba gris claro y
    # Tesseract lo omitía; con solo el canal más oscuro se perdía la fila de un ítem.
    luminancia = np.array(ImageOps.grayscale(imagen), np.uint16)
    canal_minimo = np.array(imagen.convert("RGB")).min(axis=2)
    imagen = Image.fromarray(((luminancia + canal_minimo) // 2).astype(np.uint8))
    imagen = ImageOps.autocontrast(imagen)
    # Tesseract funciona mejor con texto grande; escalamos imágenes pequeñas.
    if imagen.width < 1500:
        factor = 1500 / imagen.width
        imagen = imagen.resize((int(imagen.width * factor), int(imagen.height * factor)), Image.LANCZOS)
    return quitar_lineas(enderezar(imagen))


@dataclass
class Leida:
    """Palabra leída por Tesseract, con su confianza (0-100) y el renglón al que pertenece."""
    palabra: Palabra
    confianza: float
    renglon: tuple  # (bloque, párrafo, línea) de Tesseract


def leer(imagen: Image.Image, psm: int) -> list[Leida]:
    datos = pytesseract.image_to_data(imagen, lang=config.OCR_LANG, config=f"--psm {psm}",
                                      output_type=pytesseract.Output.DICT)
    leidas = []
    for i, texto in enumerate(datos["text"]):
        texto = texto.strip()
        if not texto:
            continue
        x, y = datos["left"][i], datos["top"][i]
        leidas.append(Leida(Palabra(texto, x, y, x + datos["width"][i], y + datos["height"][i]),
                            float(datos["conf"][i]),
                            (datos["block_num"][i], datos["par_num"][i], datos["line_num"][i])))
    return leidas


def area(p: Palabra) -> float:
    return (p.x1 - p.x0) * (p.y1 - p.y0)


def interseccion(a: Palabra, b: Palabra) -> float:
    ancho = min(a.x1, b.x1) - max(a.x0, b.x0)
    alto = min(a.y1, b.y1) - max(a.y0, b.y0)
    return ancho * alto if ancho > 0 and alto > 0 else 0


def solapan(a: Palabra, b: Palabra) -> bool:
    """Una caja cubre más de la mitad de la otra: esa zona ya se leyó."""
    return interseccion(a, b) > 0.5 * min(area(a), area(b))


def misma_caja(a: Palabra, b: Palabra) -> bool:
    """Las dos lecturas cubren la misma zona (y no un pedazo: "lad" dentro de "Cantidad")."""
    comun = interseccion(a, b)
    return comun > 0.6 * (area(a) + area(b) - comun)


def es_numero(texto: str) -> bool:
    """Número de al menos dos cifras, con o sin separadores: "4500019020", "849.000", "12,5"."""
    return bool(re.fullmatch(r"\d+(?:[.,]\d+)*", texto)) and sum(c.isdigit() for c in texto) >= 2


def combinar(principal: list[Leida], disperso: list[Leida]) -> list[Leida]:
    """Completa la lectura normal con la de texto disperso. La normal (--psm 3) entiende el diseño
    de la página pero a veces se salta celdas sueltas de una tabla (el folio de una OC en las
    referencias) o lee mal un número solo en su celda ("7" como "f", "4" como "<"); la dispersa
    (--psm 11) lee bien esas celdas, aunque agrega basura de los timbres y bordes.
    - Palabra que la normal no leyó: se agrega si la dispersa la leyó con confianza alta.
    - Palabra que leyeron las dos (en la misma caja): queda la de mayor confianza, si la dispersa
      no es dudosa ("249.000" con 51 se corrige a "849.000" con 80)."""
    resultado = list(principal)
    agregadas = []
    for extra in disperso:
        if not re.search(r"\w", extra.palabra.texto):
            continue
        iguales = [i for i, l in enumerate(resultado) if solapan(l.palabra, extra.palabra)]
        if not iguales:
            # Algo que la normal no vio: solo con confianza alta, porque la dispersa lee basura en
            # timbres y bordes ("a", "Ea", "TA"). Un número de varias cifras no es basura: basta
            # con que no sea dudoso (el total "849.000" de una línea, leído con 79).
            minimo = CONFIANZA_DUDOSA if es_numero(extra.palabra.texto) else CONFIANZA_SEGUNDA_LECTURA
            if extra.confianza >= minimo:
                agregadas.append(Leida(extra.palabra, extra.confianza, ("disperso",) + extra.renglon))
        elif len(iguales) == 1:
            original = resultado[iguales[0]]
            if (extra.confianza >= CONFIANZA_DUDOSA and extra.confianza > original.confianza
                    # Misma caja, o la normal leyó solo un signo donde había un número ("4" como "-")
                    and (misma_caja(extra.palabra, original.palabra) or not re.search(r"\w", original.palabra.texto))):
                resultado[iguales[0]] = Leida(extra.palabra, extra.confianza, original.renglon)
        else:
            # La dispersa leyó entero lo que la normal partió en varias palabras ("4500019030" contra
            # "450001" + "9030"): si cubre la misma zona y tiene más confianza que todas, la reemplaza.
            partes = [resultado[i] for i in iguales]
            union = Palabra("", min(p.palabra.x0 for p in partes), min(p.palabra.y0 for p in partes),
                            max(p.palabra.x1 for p in partes), max(p.palabra.y1 for p in partes))
            if (extra.confianza >= CONFIANZA_DUDOSA and extra.confianza > max(p.confianza for p in partes)
                    and misma_caja(extra.palabra, union)):
                resultado[iguales[0]] = Leida(extra.palabra, extra.confianza, partes[0].renglon)
                resultado = [l for i, l in enumerate(resultado) if i not in iguales[1:]]
    return resultado + agregadas


def releer_como_numero(imagen: Image.Image, leida: Leida) -> Leida:
    """Vuelve a leer una palabra dudosa recortando solo su celda y permitiendo solo dígitos. Un
    número solo en su celda es lo más difícil para Tesseract ("7" como "TA" o "f"); leído aislado
    y sabiendo que es un número, sale bien. Si tampoco así se lee con confianza, queda como estaba."""
    p = leida.palabra
    recorte = imagen.crop((max(p.x0 - 4, 0), max(p.y0 - 4, 0), min(p.x1 + 4, imagen.width), min(p.y1 + 4, imagen.height)))
    recorte = ImageOps.expand(recorte, border=20, fill=255)  # aire alrededor: Tesseract lo necesita
    datos = pytesseract.image_to_data(recorte, lang=config.OCR_LANG, output_type=pytesseract.Output.DICT,
                                      config="--psm 7 -c tessedit_char_whitelist=0123456789.,")
    partes = [(t.strip(), float(c)) for t, c in zip(datos["text"], datos["conf"]) if t.strip()]
    texto = "".join(t for t, _ in partes)
    confianza = min((c for _, c in partes), default=0)
    if re.fullmatch(r"\d+(?:[.,]\d+)*", texto) and confianza >= CONFIANZA_SEGUNDA_LECTURA:
        return Leida(Palabra(texto, p.x0, p.y0, p.x1, p.y1), confianza, leida.renglon)
    return leida


def es_dudosa(leida: Leida) -> bool:
    """Palabra corta leída con poca confianza: puede ser un número mal leído."""
    return leida.confianza < CONFIANZA_DUDOSA and len(leida.palabra.texto) <= 3


def unir_numeros_partidos(leidas: list[Leida]) -> list[Leida]:
    """Une un número que Tesseract partió en dos palabras pegadas ("450001" + "9030" del folio en
    negrita "4500019030"). Solo si las dos son dígitos, van seguidas en el mismo renglón y casi
    sin espacio: los números de columnas distintas o de un teléfono ("+56 72 271") van separados
    por un espacio normal, que es más ancho."""
    unidas: list[Leida] = []
    for leida in leidas:
        anterior = unidas[-1] if unidas else None
        if (anterior and anterior.renglon == leida.renglon
                and re.fullmatch(r"\d[\d.,]*", anterior.palabra.texto) and re.fullmatch(r"\d[\d.,]*", leida.palabra.texto)
                and leida.palabra.x0 - anterior.palabra.x1 < ESPACIO_NUMERO_PARTIDO * anterior.palabra.alto):
            a, b = anterior.palabra, leida.palabra
            unidas[-1] = Leida(Palabra(a.texto + b.texto, a.x0, min(a.y0, b.y0), b.x1, max(a.y1, b.y1)),
                               min(anterior.confianza, leida.confianza), anterior.renglon)
        else:
            unidas.append(leida)
    return unidas


def ocr_imagen(imagen: Image.Image) -> tuple[str, list[Palabra]]:
    """Devuelve el texto y las palabras con posición, combinando dos lecturas de Tesseract y
    releyendo como número las palabras cortas dudosas."""
    imagen = preprocesar(imagen)
    leidas = [releer_como_numero(imagen, l) if es_dudosa(l) else l
              for l in combinar(leer(imagen, 3), leer(imagen, 11))]
    leidas = unir_numeros_partidos(leidas)
    palabras = [l.palabra for l in leidas]
    lineas: dict[tuple, list[str]] = {}
    for l in leidas:
        lineas.setdefault(l.renglon, []).append(l.palabra.texto)

    # Reconstruye el texto como lo haría image_to_string: una línea por renglón y una línea en
    # blanco entre bloques. Lo que solo leyó la lectura dispersa va al final, en su propio bloque.
    partes, bloque_anterior = [], None
    for renglon, linea in lineas.items():
        bloque = renglon[:-2]
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
