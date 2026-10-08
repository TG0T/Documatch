"""Extrae las mercancías (ítems) de un documento: su cantidad y su valor total.

Trabaja sobre las palabras con su posición en la página y no sobre el texto plano, porque el
OCR no respeta las columnas: en "Tubo PVC 110 12 3.500 42.000" no se sabe cuál número es la
cantidad. Por eso se busca la fila de encabezado de la tabla que tiene la columna "Cantidad"
y, en cada fila de abajo, se lee el número que queda bajo esa columna (y bajo la del valor
total de la línea, si existe) hasta llegar a los totales del documento ("Neto", "Total", ...).

Los patrones se aplican sobre texto normalizado (minúsculas y sin tildes).
"""
import math
import re
from dataclasses import dataclass
from statistics import median

from app.classifier.clasificador import normalizar
from app.services.ocr import Palabra

# Encabezado de la columna de cantidad: "Cantidad", "Cant.", "CANT", "Qty".
# Basta con que la palabra lo contenga: el OCR a veces pega el borde de la celda o lee mal
# el final ("ICanTIDACI", "Cantldad"). Exigir otro encabezado en la fila evita falsos positivos.
ENCABEZADO_CANTIDAD = r"cant|qty"

# Encabezado de la columna con el nombre de la mercancía ("descr" porque el OCR lee "Descr:pción").
ENCABEZADO_DESCRIPCION = r"\b(descr|detalle|producto|articulo|glosa|mercaderia|mercancia|nombre)"

# Encabezado de la columna con el valor total de cada línea: "Total", "Valor", "Precio Total",
# "Monto". "tota" porque el OCR lee "Totar". Se descartan los unitarios ("Valor Unitario").
ENCABEZADO_TOTAL = r"tota|valor|monto|importe"
ENCABEZADO_UNITARIO = r"unit"

# Otros encabezados típicos de una tabla de ítems. Se exige al menos uno (o la descripción)
# para no confundir la tabla con una línea suelta como "Cantidad de bultos: 4".
OTROS_ENCABEZADOS = r"\b(codigo|cod\b|item|precio|valor|unitario|unit\b|total|monto|unidad|u\.?m\b|dcto|descuento)"

# Primera línea después de la tabla: ahí terminan los ítems.
FIN_TABLA = (
    r"^\W*(sub\s*-?\s*total|total|monto|neto|iva\b|exento|son\s*:|observaci|timbre|"
    r"referencias?\b|forma\s+de\s+pago|recibi)"
)

# Etiqueta del monto neto o subtotal del documento, para verificar la suma de los ítems.
ETIQUETA_NETO = r"neto|sub-?total"

# Un número con separadores de miles o decimales: "20", "1.500", "2,5", "51,600.00".
NUMERO = re.compile(r"\d+(?:[.,]\d+)*")

# Números que delatan el formato del documento. En Chile "51.600,00" (coma decimal), pero hay
# documentos en formato estadounidense "51,600.00" (punto decimal), donde "503,600" son miles.
FORMATO_CHILENO = re.compile(r"\d{1,3}(?:\.\d{3})+,\d{1,2}|\d+,\d{2}")
FORMATO_PUNTO_DECIMAL = re.compile(r"\d{1,3}(?:,\d{3})+\.\d{1,2}|\d+\.\d{2}")

# Bordes de la tabla que el OCR pega a las palabras ("|12", "[CGA900"), y el signo peso.
BORDES = "|[](){}:;¡!$"

# Si entre una fila y la siguiente hay más espacio que esto (en altos de letra), la tabla terminó.
SALTO_MAXIMO = 4

# Separación máxima (en altos de letra) entre palabras de un mismo encabezado, como "Precio Unitario"
# (o "Cant" + "idad" cuando el OCR parte la palabra).
ESPACIO_ENTRE_PALABRAS = 1.0


@dataclass
class Item:
    descripcion: str
    cantidad: float
    total: float | None = None  # valor total de la línea, si la tabla tiene esa columna


@dataclass
class Fila:
    palabras: list[Palabra]

    @property
    def cy(self) -> float:
        return sum(p.cy for p in self.palabras) / len(self.palabras)

    @property
    def y0(self) -> float:
        return min(p.y0 for p in self.palabras)

    @property
    def y1(self) -> float:
        return max(p.y1 for p in self.palabras)

    @property
    def texto(self) -> str:
        return normalizar(" ".join(p.texto for p in self.palabras))


@dataclass
class Columna:
    izquierda: float
    derecha: float
    centro: float

    def contiene(self, palabra: Palabra) -> bool:
        return self.izquierda <= palabra.cx <= self.derecha

    def numero(self, fila: "Fila", decimal: str) -> float | None:
        """El número de la fila que cae en la columna; si hay varios, el más cercano al centro."""
        numeros = [p for p in fila.palabras if self.contiene(p) and a_numero(p.texto, decimal) is not None]
        elegida = min(numeros, key=lambda p: abs(p.cx - self.centro), default=None)
        return a_numero(elegida.texto, decimal) if elegida else None


@dataclass
class Tabla:
    cantidad: Columna
    descripcion: Columna | None
    total: Columna | None
    filas_encabezado: int  # cuántas filas ocupa el encabezado (sigue abajo: "Precio" / "Total")


def a_numero(texto: str, decimal: str = ",") -> float | None:
    """Convierte un número del documento. `decimal` es el separador decimal del documento
    ("," en Chile); solo decide los casos ambiguos como "503,600" o "1.500"."""
    texto = texto.strip(BORDES)
    if not NUMERO.fullmatch(texto):
        return None
    separadores = re.findall(r"[.,]", texto)
    if len(set(separadores)) == 2:
        decimal = separadores[-1]  # "2,580.00" / "2.580,00": el último separa los decimales
    elif separadores:
        sep = separadores[0]
        grupos_de_mil = re.fullmatch(rf"\d{{1,3}}(?:{re.escape(sep)}\d{{3}})+", texto)
        if len(separadores) > 1:
            # "1.234.567" son miles; si el último grupo no es de 3 cifras, el OCR leyó mal la
            # coma de los miles ("2.790.00") y el último separa los decimales.
            decimal = "" if grupos_de_mil else sep
        elif sep != decimal and not grupos_de_mil:
            decimal = sep  # "1.5" con coma decimal: no puede ser de miles
        elif sep != decimal:
            decimal = ""  # "1.500" en Chile, "503,600" con punto decimal: miles
    if decimal and decimal in texto:
        entero, _, fraccion = texto.rpartition(decimal)
        texto = re.sub(r"[.,]", "", entero) + "." + fraccion
    else:
        texto = re.sub(r"[.,]", "", texto)
    return float(texto)


def separador_decimal(palabras: list[Palabra]) -> str:
    """El separador decimal que usa el documento, según los números que tienen decimales."""
    textos = [p.texto.strip(BORDES) for p in palabras]
    chilenos = sum(1 for t in textos if FORMATO_CHILENO.fullmatch(t))
    punto = sum(1 for t in textos if FORMATO_PUNTO_DECIMAL.fullmatch(t))
    return "." if punto > chilenos else ","


def agrupar_filas(palabras: list[Palabra], alto: float) -> list[Fila]:
    """Agrupa las palabras que están a la misma altura (el OCR a veces separa las columnas
    de una misma fila en bloques distintos)."""
    filas: list[Fila] = []
    for palabra in sorted(palabras, key=lambda p: p.cy):
        if filas and abs(palabra.cy - filas[-1].cy) <= alto / 2:
            filas[-1].palabras.append(palabra)
        else:
            filas.append(Fila([palabra]))
    for fila in filas:
        fila.palabras.sort(key=lambda p: p.x0)
    return filas


def celdas_encabezado(fila: Fila, alto: float) -> list[Palabra]:
    """Junta las palabras cercanas del encabezado en una sola celda ("Precio Unitario")."""
    celdas: list[Palabra] = []
    for p in fila.palabras:
        if celdas and p.x0 - celdas[-1].x1 <= alto * ESPACIO_ENTRE_PALABRAS:
            ultima = celdas[-1]
            celdas[-1] = Palabra(f"{ultima.texto} {p.texto}", ultima.x0, min(ultima.y0, p.y0), p.x1, max(ultima.y1, p.y1))
        else:
            celdas.append(Palabra(p.texto, p.x0, p.y0, p.x1, p.y1))
    return celdas


def es_encabezado(texto: str) -> bool:
    return any(re.search(patron, texto) for patron in
               (ENCABEZADO_CANTIDAD, ENCABEZADO_DESCRIPCION, ENCABEZADO_TOTAL, OTROS_ENCABEZADOS))


def completar_encabezado(celdas: list[Palabra], segunda: Fila) -> None:
    """Suma a cada celda la palabra de la segunda línea que tiene debajo ("Precio" + "Total")."""
    for p in segunda.palabras:
        solape = [min(c.x1, p.x1) - max(c.x0, p.x0) for c in celdas]
        i = max(range(len(celdas)), key=solape.__getitem__)
        if solape[i] > 0:
            c = celdas[i]
            celdas[i] = Palabra(f"{c.texto} {p.texto}", min(c.x0, p.x0), c.y0, max(c.x1, p.x1), max(c.y1, p.y1))


def mitad_de_encabezado(fila: Fila, otra: Fila, alto: float) -> bool:
    """`otra` es parte del mismo encabezado que `fila`: en una foto algo torcida el encabezado
    queda partido en dos filas casi a la misma altura ("Codigo Cant." / "Descripcion Total")."""
    solape = min(fila.y1, otra.y1) - max(fila.y0, otra.y0)
    return (solape > alto / 2
            and all(a_numero(p.texto) is None for p in otra.palabras)
            and es_encabezado(otra.texto))


def leer_encabezado(filas: list[Fila], i: int, alto: float) -> Tabla | None:
    """Si filas[i] es el encabezado de una tabla de ítems devuelve sus columnas; si no, None."""
    fila = filas[i]
    unidas = 0  # filas siguientes que eran parte de este mismo encabezado
    palabras = list(fila.palabras)
    if i > 0 and mitad_de_encabezado(fila, filas[i - 1], alto):
        palabras += filas[i - 1].palabras
    if i + 1 < len(filas) and mitad_de_encabezado(fila, filas[i + 1], alto):
        palabras += filas[i + 1].palabras
        unidas = 1
    if len(palabras) > len(fila.palabras):
        fila = Fila(sorted(palabras, key=lambda p: p.x0))
    i += unidas
    celdas = celdas_encabezado(fila, alto)
    textos = [normalizar(c.texto) for c in celdas]
    i_cantidad = next((j for j, t in enumerate(textos) if re.search(ENCABEZADO_CANTIDAD, t)), None)
    if i_cantidad is None:
        return None

    # Encabezado en dos líneas: la segunda está pegada a la primera, no trae números y tiene
    # palabras de encabezado ("Unitario*", "Total*").
    filas_encabezado = 1 + unidas
    if i + 1 < len(filas):
        segunda = filas[i + 1]
        if (segunda.y0 - fila.y1 < alto
                and all(a_numero(p.texto) is None for p in segunda.palabras)
                and es_encabezado(segunda.texto)):
            completar_encabezado(celdas, segunda)
            textos = [normalizar(c.texto) for c in celdas]
            filas_encabezado += 1

    i_descripcion = next(
        (j for j, t in enumerate(textos) if j != i_cantidad and re.search(ENCABEZADO_DESCRIPCION, t)), None
    )
    otros = any(re.search(OTROS_ENCABEZADOS, t) for j, t in enumerate(textos) if j != i_cantidad)
    if i_descripcion is None and not otros:
        return None
    # Si hay varias columnas de total ("Subtotal", "Total"), la de más a la derecha.
    i_total = next((j for j in reversed(range(len(textos)))
                    if j not in (i_cantidad, i_descripcion)
                    and re.search(ENCABEZADO_TOTAL, textos[j])
                    and not re.search(ENCABEZADO_UNITARIO, textos[j])), None)

    def columna(j: int, derecha_hasta_el_borde: bool) -> Columna:
        """La columna llega por la izquierda hasta el borde de la celda vecina y por la derecha
        hasta el borde o hasta la mitad del espacio con la siguiente."""
        izquierda = celdas[j - 1].x1 if j > 0 else -math.inf
        derecha = celdas[j + 1].x0 if j < len(celdas) - 1 else math.inf
        if not derecha_hasta_el_borde:
            derecha = (celdas[j].x1 + derecha) / 2
        return Columna(izquierda, derecha, celdas[j].cx)

    # Los encabezados suelen ir centrados, pero el texto de la descripción va alineado a la
    # izquierda y los números a la derecha, lejos del centro: por eso las columnas llegan hasta
    # el borde de sus vecinas (entre varios números se elige el más cercano al centro). A la
    # derecha de la descripción solo hasta la mitad, para no sumarle texto de columnas sin
    # encabezado, como un enlace "Ver ficha".
    return Tabla(
        cantidad=columna(i_cantidad, derecha_hasta_el_borde=True),
        descripcion=columna(i_descripcion, derecha_hasta_el_borde=False) if i_descripcion is not None else None,
        total=columna(i_total, derecha_hasta_el_borde=True) if i_total is not None else None,
        filas_encabezado=filas_encabezado,
    )


def leer_items(filas: list[Fila], tabla: Tabla, alto: float, encabezado: Fila, decimal: str) -> list[Item]:
    # (fila, cantidad, total, partes de la descripción como (y, texto))
    con_cantidad: list[tuple[Fila, float, float | None, list[tuple[float, str]]]] = []
    sueltas: list[tuple[Fila, str]] = []  # filas con descripción pero sin cantidad
    anterior = encabezado
    for fila in filas:
        if fila.y0 - anterior.y1 > alto * SALTO_MAXIMO or re.match(FIN_TABLA, fila.texto):
            break
        anterior = fila

        cantidad = tabla.cantidad.numero(fila, decimal)

        if tabla.descripcion:
            palabras = [p for p in fila.palabras if tabla.descripcion.contiene(p)]
        else:
            # Sin columna de descripción: todo lo que tenga letras (la cantidad no tiene).
            palabras = [p for p in fila.palabras if re.search(r"[^\W\d_]", p.texto)]
        texto = " ".join(t for t in (p.texto.strip(BORDES) for p in palabras) if t)

        if cantidad is not None:
            total = tabla.total.numero(fila, decimal) if tabla.total else None
            con_cantidad.append((fila, cantidad, total, [(fila.cy, texto)] if texto else []))
        elif texto:
            sueltas.append((fila, texto))

    # Una fila sin cantidad es parte de la descripción de un ítem que ocupa varias líneas. Va con el
    # ítem de arriba ("Producto 3" / "- SubProducto 3.a"), salvo que el de abajo esté claramente
    # más cerca: en celdas de varias líneas la cantidad suele ir centrada, debajo de la primera.
    for fila, texto in sueltas:
        arriba = [c for c in con_cantidad if c[0].cy < fila.cy]
        abajo = [c for c in con_cantidad if c[0].cy > fila.cy]
        previo = arriba[-1] if arriba else None
        siguiente = abajo[0] if abajo else None
        if siguiente and (not previo or siguiente[0].cy - fila.cy < (fila.cy - previo[0].cy) / 2):
            siguiente[3].append((fila.cy, texto))
        elif previo:
            previo[3].append((fila.cy, texto))
    return [Item(" ".join(t for _, t in sorted(partes)), cantidad, total)
            for _, cantidad, total, partes in con_cantidad]


def extraer_items(paginas: list[list[Palabra]]) -> list[Item]:
    """Ítems de todas las páginas (la tabla puede seguir en la página siguiente)."""
    items: list[Item] = []
    for palabras in paginas:
        if not palabras:
            continue
        alto = median(p.alto for p in palabras)
        filas = agrupar_filas(palabras, alto)
        decimal = separador_decimal(palabras)
        for i in range(len(filas)):
            tabla = leer_encabezado(filas, i, alto)
            if tabla:
                fin_encabezado = i + tabla.filas_encabezado
                items += leer_items(filas[fin_encabezado:], tabla, alto, filas[fin_encabezado - 1], decimal)
                break
    return items


def montos_netos(paginas: list[list[Palabra]]) -> list[float]:
    """Montos que el documento imprime como neto o subtotal ("Monto Neto 100.000", "Sub-Total
    503,600"): el número a la derecha de la etiqueta, en la misma línea."""
    montos = []
    for palabras in paginas:
        if not palabras:
            continue
        alto = median(p.alto for p in palabras)
        decimal = separador_decimal(palabras)
        for fila in agrupar_filas(palabras, alto):
            textos = [normalizar(p.texto) for p in fila.palabras]
            for i, texto in enumerate(textos):
                # "neto" también encuentra lecturas del OCR como "MENTONETO" (Monto Neto)
                es_etiqueta = re.search(ETIQUETA_NETO, texto) or (
                    texto.startswith("total") and i > 0 and textos[i - 1].endswith("sub"))
                if not es_etiqueta:
                    continue
                etiqueta = fila.palabras[i]
                a_la_derecha = [p for p in fila.palabras if p.x0 > etiqueta.x1]
                valor = next((v for v in (a_numero(p.texto, decimal) for p in a_la_derecha) if v is not None), None)
                if valor is not None:
                    montos.append(valor)
                break
    return montos


def verificar_valores(items: list[Item], netos: list[float]) -> tuple[bool | None, float | None]:
    """Compara la suma de los valores de los ítems con el neto (o subtotal) impreso en el
    documento, para detectar errores de lectura del OCR. Devuelve (coinciden, neto):
    coinciden es None si no hay con qué comparar y False si falta el valor de algún ítem."""
    if not items or not netos:
        return None, netos[0] if netos else None
    if any(i.total is None for i in items):
        return False, netos[0]
    suma = sum(i.total for i in items)
    # Cada total puede venir redondeado al peso ("13 x 1034,26 = 13.445").
    tolerancia = len(items)
    for neto in netos:  # subtotal antes de un descuento global, o neto después de él
        if abs(suma - neto) <= tolerancia:
            return True, neto
    return False, netos[0]
