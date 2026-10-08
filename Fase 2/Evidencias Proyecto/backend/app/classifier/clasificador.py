"""Clasifica un texto según las palabras clave definidas en palabras_clave.py."""
import re
import unicodedata
from dataclasses import dataclass, field

from app.classifier.palabras_clave import (
    BONO_TITULO,
    DISTANCIA_TITULO_NUMERO,
    LINEAS_ENCABEZADO,
    LINEAS_NUMERO,
    MARCA_NUMERO,
    MARCA_NUMERO_SII,
    NUMERO_DOCUMENTO,
    PUNTAJE_MINIMO,
    TIPOS_DOCUMENTO,
)

DESCONOCIDO = "desconocido"


@dataclass
class Resultado:
    tipo: str
    nombre: str
    confianza: float  # 0 a 1: qué parte del puntaje total se llevó el tipo ganador
    puntajes: dict[str, int] = field(default_factory=dict)
    coincidencias: dict[str, list[str]] = field(default_factory=dict)
    numero: str | None = None  # número del documento ("876-329-SE22"), si se encontró


def codigo(tipo: str, numero: str | None) -> str | None:
    """Código del documento: prefijo del tipo y número ("OC-123", "G-123", "F-123")."""
    if tipo not in TIPOS_DOCUMENTO or not numero:
        return None
    return f"{TIPOS_DOCUMENTO[tipo]['prefijo']}-{numero}"


def normalizar(texto: str) -> str:
    """Minúsculas, sin tildes y con espacios simples (el OCR deja muchos saltos raros)."""
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = texto.lower()
    return re.sub(r"[ \t]+", " ", texto)


def encabezado(texto: str, lineas_maximas: int = LINEAS_ENCABEZADO) -> str:
    lineas = [l for l in texto.splitlines() if l.strip()]
    # Las referencias a otros documentos no son el título: en una factura, "Referencias: Orden de
    # Compra N° 8832" o un recuadro "REFERENCIAS" con "ORDEN DE COMPRA FOLIO 22438" debajo.
    sin_referencias = []
    for i, linea in enumerate(lineas):
        es_referencia = re.search(r"\breferencias?\b", linea)
        bajo_referencias = i > 0 and re.fullmatch(r"\W*referencias?\W*", lineas[i - 1])
        if not (es_referencia or bajo_referencias):
            sin_referencias.append(linea)
    return "\n".join(sin_referencias[:lineas_maximas])


def tiene_titulo(patron: str, cabecera: str) -> bool:
    """El título cuenta si abre una línea o va seguido del número del documento."""
    al_inicio = re.search(rf"^\W*(?:{patron})", cabecera, re.MULTILINE)
    con_numero = re.search(rf"(?:{patron})(\s+electronica)?\s*{MARCA_NUMERO}", cabecera)
    return bool(al_inicio or con_numero)


def numero_documento(tipo: str, inicio: str) -> str | None:
    """El número del documento, buscado en este orden:
    1. Pegado al título: "orden de compra n°: 876-329-se22", "factura electronica n° 4521".
    2. Al final de una línea: en los recuadros del SII el número va en su propia línea ("N° 46"),
       pero el OCR suele pegarle el texto de la columna de la izquierda ("calle falsa 123 n°1").
       Una dirección ("teatinos n' 92, piso 8") no queda al final de la línea.
    3. Hasta DISTANCIA_TITULO_NUMERO caracteres después del título."""
    marca = rf"(?<![a-z])(?:{MARCA_NUMERO}\s*:?\s*|{MARCA_NUMERO_SII})"
    numero = rf"{marca}(?P<numero>{NUMERO_DOCUMENTO})"
    titulo = rf"(?:{TIPOS_DOCUMENTO[tipo]['titulo']})"
    match = (re.search(rf"{titulo}(?:\s+electronica)?\W{{0,3}}{numero}", inicio)
             or re.search(rf"{numero}\W*$", inicio, re.MULTILINE)
             or re.search(rf"{titulo}[\s\S]{{0,{DISTANCIA_TITULO_NUMERO}}}?{numero}", inicio))
    if not match:
        return None
    # Sin los puntos de miles ("178.880") y en mayúsculas, como se imprime ("SE22").
    return match.group("numero").replace(".", "").upper() or None


def clasificar(texto: str) -> Resultado:
    texto = normalizar(texto)
    cabecera = encabezado(texto)

    puntajes: dict[str, int] = {}
    coincidencias: dict[str, list[str]] = {}

    for tipo, definicion in TIPOS_DOCUMENTO.items():
        puntaje = 0
        encontradas = []
        if tiene_titulo(definicion["titulo"], cabecera):
            puntaje += BONO_TITULO
            encontradas.append("[título en encabezado]")
        for patron, peso in definicion["claves"]:
            match = re.search(patron, texto)
            if match:
                puntaje += peso
                encontradas.append(match.group(0))
        puntajes[tipo] = puntaje
        coincidencias[tipo] = encontradas

    ganador = max(puntajes, key=puntajes.get)
    total = sum(puntajes.values())

    if puntajes[ganador] < PUNTAJE_MINIMO:
        return Resultado(DESCONOCIDO, "Desconocido", 0.0, puntajes, coincidencias)

    return Resultado(
        tipo=ganador,
        nombre=TIPOS_DOCUMENTO[ganador]["nombre"],
        confianza=round(puntajes[ganador] / total, 2),
        puntajes=puntajes,
        coincidencias=coincidencias,
        numero=numero_documento(ganador, encabezado(texto, LINEAS_NUMERO)),
    )
