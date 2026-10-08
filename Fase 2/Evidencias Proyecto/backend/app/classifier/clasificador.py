"""Clasifica un texto según las palabras clave definidas en palabras_clave.py."""
import re
import unicodedata
from dataclasses import dataclass, field

from app.classifier.palabras_clave import (
    BONO_TITULO,
    LINEAS_ENCABEZADO,
    MARCA_NUMERO,
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


def normalizar(texto: str) -> str:
    """Minúsculas, sin tildes y con espacios simples (el OCR deja muchos saltos raros)."""
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = texto.lower()
    return re.sub(r"[ \t]+", " ", texto)


def encabezado(texto: str) -> str:
    lineas = [l for l in texto.splitlines() if l.strip()]
    return "\n".join(lineas[:LINEAS_ENCABEZADO])


def tiene_titulo(patron: str, cabecera: str) -> bool:
    """El título cuenta si abre una línea o va seguido del número del documento."""
    al_inicio = re.search(rf"^\W*(?:{patron})", cabecera, re.MULTILINE)
    con_numero = re.search(rf"(?:{patron})(\s+electronica)?\s*{MARCA_NUMERO}", cabecera)
    return bool(al_inicio or con_numero)


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
    )
