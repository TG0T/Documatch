"""Genera órdenes de compra, guías de despacho y facturas de prueba en formato chileno (PDF).

Tres juegos enlazados (la guía y la factura citan la OC en sus referencias):
  1. Conciliado: se despacha y factura lo pedido.
  2. Despacho parcial: llega menos de lo pedido y se factura lo recibido.
  3. Discrepancia: se factura una unidad más de lo recibido.

Empresas y RUT ficticios. Cada documento lleva "Documento de prueba - sin validez tributaria".
Uso: python generar_documentos.py <carpeta de salida>
"""
import sys
from pathlib import Path

import pymupdf

FUENTE = "C:/Windows/Fonts/arial.ttf"
FUENTE_NEGRITA = "C:/Windows/Fonts/arialbd.ttf"
ANCHO, ALTO = pymupdf.paper_size("letter")
MARGEN = 40

NEGRO = (0.07, 0.07, 0.09)
GRIS = (0.38, 0.4, 0.45)
GRIS_CLARO = (0.9, 0.91, 0.93)
ROJO_SII = (0.78, 0.1, 0.12)


def digito_verificador(numero: int) -> str:
    """Dígito verificador del RUT (módulo 11)."""
    suma, factor = 0, 2
    for d in reversed(str(numero)):
        suma += int(d) * factor
        factor = 2 if factor == 7 else factor + 1
    resto = 11 - suma % 11
    return {11: "0", 10: "K"}.get(resto, str(resto))


def rut(numero: int) -> str:
    return f"{numero:,}".replace(",", ".") + "-" + digito_verificador(numero)


def miles(n: int) -> str:
    return f"{n:,}".replace(",", ".")


PROVEEDOR = {
    "razon": "SUMINISTROS INDUSTRIALES CORDILLERA SpA",
    "rut": rut(76482915),
    "giro": "Venta al por mayor de materiales de construcción y ferretería",
    "direccion": "Av. Los Conquistadores 1820, Of. 304",
    "comuna": "Providencia",
    "ciudad": "Santiago",
    "telefono": "+56 2 2345 6789",
    "correo": "ventas@cordillera-demo.cl",
    "sii": "S.I.I. - SANTIAGO ORIENTE",
}

COMPRADOR = {
    "razon": "CONSTRUCTORA VALLE CENTRAL LTDA.",
    "rut": rut(77318204),
    "giro": "Construcción de edificios para uso residencial",
    "direccion": "Calle Las Acacias 455",
    "comuna": "Rancagua",
    "ciudad": "Rancagua",
    "telefono": "+56 72 223 4567",
    "despacho": "Obra Edificio Los Robles, Camino Los Robles 1200, Machalí",
}

# código: (descripción, unidad, precio unitario neto)
PRODUCTOS = {
    "CEM-25": ("Cemento especial saco 25 kg", "SACO", 5490),
    "PVC-110": ("Tubo PVC sanitario 110 mm x 6 m", "UN", 12990),
    "GUA-NIT": ("Guantes de nitrilo talla L (caja 100)", "CAJA", 8990),
    "FIE-8": ("Fierro estriado 8 mm x 6 m", "UN", 4290),
    "MAD-2X4": ('Pino dimensionado 2x4" x 3,2 m', "UN", 3790),
    "CAS-BL": ("Casco de seguridad blanco", "UN", 6490),
    "PIN-LT": ("Pintura látex blanca (galón)", "GL", 18990),
    "TOR-12": ('Tornillo hexagonal 1/2" x 2" (caja 50)', "CAJA", 15900),
}

JUEGOS = [
    {
        "nombre": "1_conciliado",
        "oc": ("4500018231", "03-11-2026"), "guia": ("58210", "06-11-2026"), "factura": ("31145", "07-11-2026"),
        "pedido": {"CEM-25": 40, "PVC-110": 12, "GUA-NIT": 5},
        "despachado": {"CEM-25": 40, "PVC-110": 12, "GUA-NIT": 5},
        "facturado": {"CEM-25": 40, "PVC-110": 12, "GUA-NIT": 5},
    },
    {
        "nombre": "2_despacho_parcial",
        "oc": ("4500018232", "04-11-2026"), "guia": ("58231", "08-11-2026"), "factura": ("31162", "09-11-2026"),
        "pedido": {"FIE-8": 120, "MAD-2X4": 60, "CAS-BL": 15},
        "despachado": {"FIE-8": 80, "MAD-2X4": 60, "CAS-BL": 15},
        "facturado": {"FIE-8": 80, "MAD-2X4": 60, "CAS-BL": 15},
    },
    {
        "nombre": "3_discrepancia",
        "oc": ("4500018233", "05-11-2026"), "guia": ("58247", "10-11-2026"), "factura": ("31170", "11-11-2026"),
        "pedido": {"PIN-LT": 10, "TOR-12": 8},
        "despachado": {"PIN-LT": 10, "TOR-12": 8},
        "facturado": {"PIN-LT": 11, "TOR-12": 8},
    },
]


class Hoja:
    """Página con ayudas para escribir texto, recuadros y tablas."""

    def __init__(self, doc: pymupdf.Document):
        self.p = doc.new_page(width=ANCHO, height=ALTO)
        self.p.insert_font(fontname="normal", fontfile=FUENTE)
        self.p.insert_font(fontname="negrita", fontfile=FUENTE_NEGRITA)
        self.fuentes = {"normal": pymupdf.Font(fontfile=FUENTE), "negrita": pymupdf.Font(fontfile=FUENTE_NEGRITA)}

    def ancho(self, texto, tam=9, negrita=False):
        return self.fuentes["negrita" if negrita else "normal"].text_length(texto, fontsize=tam)

    def texto(self, x, y, texto, tam=9, negrita=False, color=NEGRO, alinear="izq"):
        if alinear == "der":
            x -= self.ancho(texto, tam, negrita)
        elif alinear == "centro":
            x -= self.ancho(texto, tam, negrita) / 2
        self.p.insert_text((x, y), texto, fontsize=tam, fontname="negrita" if negrita else "normal", color=color)

    def recuadro(self, x0, y0, x1, y1, borde=NEGRO, relleno=None, grosor=0.8):
        self.p.draw_rect(pymupdf.Rect(x0, y0, x1, y1), color=borde, fill=relleno, width=grosor)

    def linea(self, x0, y0, x1, y1, color=NEGRO, grosor=0.6):
        self.p.draw_line((x0, y0), (x1, y1), color=color, width=grosor)

    def tabla(self, y, columnas, filas, alto_fila=17, filas_minimas=0):
        """columnas: [(título, ancho, alineación)]. Devuelve la y donde termina la tabla."""
        x_total = ANCHO - 2 * MARGEN
        escala = x_total / sum(c[1] for c in columnas)
        xs = [MARGEN]
        for c in columnas:
            xs.append(xs[-1] + c[1] * escala)
        alto_encabezado = 20
        self.recuadro(MARGEN, y, ANCHO - MARGEN, y + alto_encabezado, relleno=GRIS_CLARO)
        for (titulo, _, alinear), x0, x1 in zip(columnas, xs, xs[1:]):
            self.texto(*self._pos(x0, x1, y + 13.5, alinear), titulo, 8.5, negrita=True, alinear=alinear)
        n = max(len(filas), filas_minimas)
        fin = y + alto_encabezado + n * alto_fila
        self.recuadro(MARGEN, y, ANCHO - MARGEN, fin)
        for x in xs[1:-1]:
            self.linea(x, y, x, fin)
        for i, fila in enumerate(filas):
            base = y + alto_encabezado + i * alto_fila + 12
            for (_, _, alinear), x0, x1, valor in zip(columnas, xs, xs[1:], fila):
                self.texto(*self._pos(x0, x1, base, alinear), str(valor), 8.5, alinear=alinear)
        return fin

    @staticmethod
    def _pos(x0, x1, y, alinear):
        return ({"izq": x0 + 5, "der": x1 - 5, "centro": (x0 + x1) / 2}[alinear], y)

    def pie(self):
        self.texto(ANCHO / 2, ALTO - 22, "Documento de prueba generado para Documatch - sin validez tributaria",
                   7.5, color=GRIS, alinear="centro")


def recuadro_sii(h: Hoja, titulo: str, folio: str):
    """Recuadro rojo de los documentos tributarios electrónicos: RUT, tipo y folio."""
    x0, x1, y0 = ANCHO - MARGEN - 200, ANCHO - MARGEN, MARGEN
    h.recuadro(x0, y0, x1, y0 + 78, borde=ROJO_SII, grosor=2)
    centro = (x0 + x1) / 2
    h.texto(centro, y0 + 20, f"R.U.T.: {PROVEEDOR['rut']}", 11, True, ROJO_SII, "centro")
    h.texto(centro, y0 + 42, titulo, 11, True, ROJO_SII, "centro")
    h.texto(centro, y0 + 64, f"N° {folio}", 12, True, ROJO_SII, "centro")
    h.texto(centro, y0 + 92, PROVEEDOR["sii"], 8.5, True, ROJO_SII, "centro")


def emisor(h: Hoja):
    p = PROVEEDOR
    h.texto(MARGEN, MARGEN + 14, p["razon"], 12, True)
    for i, linea in enumerate([f"Giro: {p['giro']}", f"{p['direccion']}, {p['comuna']}, {p['ciudad']}",
                               f"Teléfono: {p['telefono']}   ·   {p['correo']}"]):
        h.texto(MARGEN, MARGEN + 32 + i * 12, linea, 8)


def datos_receptor(h: Hoja, y: float, derecha: list[tuple[str, str]]) -> float:
    """Bloque con los datos del cliente a la izquierda y fechas/condiciones a la derecha."""
    c = COMPRADOR
    izquierda = [("SEÑOR(ES)", c["razon"]), ("R.U.T.", c["rut"]), ("GIRO", c["giro"]),
                 ("DIRECCIÓN", c["direccion"]), ("COMUNA", c["comuna"]), ("CIUDAD", c["ciudad"])]
    alto = 14 * len(izquierda) + 10
    h.recuadro(MARGEN, y, ANCHO - MARGEN, y + alto)
    for i, (etiqueta, valor) in enumerate(izquierda):
        h.texto(MARGEN + 6, y + 15 + i * 14, f"{etiqueta}:", 8, True)
        h.texto(MARGEN + 70, y + 15 + i * 14, valor, 8.5)
    x = ANCHO / 2 + 30
    for i, (etiqueta, valor) in enumerate(derecha):
        h.texto(x, y + 15 + i * 14, f"{etiqueta}:", 8, True)
        h.texto(x + 105, y + 15 + i * 14, valor, 8.5)
    return y + alto


def referencias(h: Hoja, y: float, filas: list[tuple[str, str, str]]) -> float:
    h.texto(MARGEN, y + 12, "REFERENCIAS", 9, True)
    return h.tabla(y + 18, [("Tipo de documento", 3, "izq"), ("Folio", 2, "izq"), ("Fecha", 2, "izq")], filas, alto_fila=15)


def totales(h: Hoja, y: float, neto: int, con_exento=False) -> float:
    iva = round(neto * 0.19)
    filas = [("MONTO NETO", neto), ("I.V.A. 19%", iva), ("TOTAL", neto + iva)]
    if con_exento:
        filas.insert(1, ("MONTO EXENTO", 0))
    x0 = ANCHO - MARGEN - 200
    h.recuadro(x0, y, ANCHO - MARGEN, y + 8 + 16 * len(filas))
    for i, (etiqueta, valor) in enumerate(filas):
        ultima = i == len(filas) - 1
        h.texto(x0 + 8, y + 17 + i * 16, etiqueta, 9, ultima)
        h.texto(x0 + 110, y + 17 + i * 16, "$", 9, ultima)
        h.texto(ANCHO - MARGEN - 8, y + 17 + i * 16, miles(valor), 9, ultima, alinear="der")
    return y + 8 + 16 * len(filas)


def timbre(h: Hoja, y: float):
    """Espacio del timbre electrónico (simulado: un documento de prueba no tiene timbre real)."""
    x0 = MARGEN
    h.recuadro(x0, y, x0 + 190, y + 70, borde=GRIS)
    for i in range(0, 178, 6):  # trama que recuerda un código PDF417
        h.linea(x0 + 6 + i, y + 8, x0 + 6 + i, y + 48, color=GRIS_CLARO, grosor=3)
    h.texto(x0 + 95, y + 60, "Timbre electrónico simulado", 7.5, color=GRIS, alinear="centro")


def filas_items(cantidades: dict[str, int], con_valores: bool):
    filas, neto = [], 0
    for codigo, cantidad in cantidades.items():
        descripcion, unidad, precio = PRODUCTOS[codigo]
        total = cantidad * precio
        neto += total
        fila = [codigo, descripcion, miles(cantidad), unidad]
        if con_valores:
            fila += [miles(precio), miles(total)]
        filas.append(fila)
    return filas, neto


def orden_de_compra(juego) -> pymupdf.Document:
    numero, fecha = juego["oc"]
    doc = pymupdf.open()
    h = Hoja(doc)
    c = COMPRADOR
    h.texto(MARGEN, MARGEN + 14, c["razon"], 12, True)
    h.texto(MARGEN, MARGEN + 30, f"R.U.T.: {c['rut']}   ·   Giro: {c['giro']}", 8)
    h.texto(MARGEN, MARGEN + 42, f"{c['direccion']}, {c['comuna']}   ·   Teléfono: {c['telefono']}", 8)
    x0 = ANCHO - MARGEN - 200
    h.recuadro(x0, MARGEN, ANCHO - MARGEN, MARGEN + 52, grosor=1.5)
    h.texto((x0 + ANCHO - MARGEN) / 2, MARGEN + 22, "ORDEN DE COMPRA", 12, True, alinear="centro")
    h.texto((x0 + ANCHO - MARGEN) / 2, MARGEN + 42, f"N° {numero}", 12, True, alinear="centro")

    y = MARGEN + 70
    p = PROVEEDOR
    proveedor = [("PROVEEDOR", p["razon"]), ("R.U.T.", p["rut"]), ("DIRECCIÓN", f"{p['direccion']}, {p['comuna']}"),
                 ("CONTACTO", f"{p['telefono']} · {p['correo']}")]
    h.recuadro(MARGEN, y, ANCHO - MARGEN, y + 66)
    for i, (etiqueta, valor) in enumerate(proveedor):
        h.texto(MARGEN + 6, y + 15 + i * 14, f"{etiqueta}:", 8, True)
        h.texto(MARGEN + 75, y + 15 + i * 14, valor, 8.5)
    x = ANCHO / 2 + 30
    for i, (etiqueta, valor) in enumerate([("FECHA EMISIÓN", fecha), ("CONDICIONES DE PAGO", "30 días"),
                                           ("PLAZO DE ENTREGA", "5 días hábiles"), ("CENTRO DE COSTO", "CC-2104 Obra Los Robles")]):
        h.texto(x, y + 15 + i * 14, f"{etiqueta}:", 8, True)
        h.texto(x + 110, y + 15 + i * 14, valor, 8.5)
    y += 76
    h.texto(MARGEN, y + 10, f"LUGAR DE ENTREGA: {c['despacho']}", 8.5)

    filas, neto = filas_items(juego["pedido"], con_valores=True)
    y = h.tabla(y + 20, [("Código", 1.3, "izq"), ("Descripción", 4.2, "izq"), ("Cantidad", 1.1, "der"),
                         ("Unidad", 1, "centro"), ("Precio Unit.", 1.4, "der"), ("Total", 1.5, "der")],
                filas, filas_minimas=8)
    totales(h, y + 12, neto)
    h.texto(MARGEN, y + 26, "Observaciones: indicar el número de esta orden de compra en la guía de", 8, color=GRIS)
    h.texto(MARGEN, y + 38, "despacho y en la factura. No se recibirán despachos sin guía.", 8, color=GRIS)

    y_firma = ALTO - 120
    for x, rol in ((MARGEN + 30, "Solicitado por: Bodega de obra"), (ANCHO / 2 + 40, "Aprobado por: Jefe de Adquisiciones")):
        h.linea(x, y_firma, x + 190, y_firma)
        h.texto(x + 95, y_firma + 12, rol, 8, alinear="centro")
    h.pie()
    return doc


def guia_de_despacho(juego) -> pymupdf.Document:
    numero, fecha = juego["guia"]
    oc, fecha_oc = juego["oc"]
    doc = pymupdf.open()
    h = Hoja(doc)
    emisor(h)
    recuadro_sii(h, "GUÍA DE DESPACHO ELECTRÓNICA", numero)
    y = datos_receptor(h, MARGEN + 108, [("FECHA EMISIÓN", fecha), ("TIPO DE TRASLADO", "Operación constituye venta"),
                                         ("TRANSPORTISTA", "Transportes Ruta Sur Ltda."), ("CHOFER", "Conductor asignado"),
                                         ("PATENTE", "KXLT-42")])
    h.texto(MARGEN, y + 14, f"DIRECCIÓN DE DESPACHO: {COMPRADOR['despacho']}", 8.5)
    y = referencias(h, y + 20, [("Orden de Compra", oc, fecha_oc)])

    filas, _ = filas_items(juego["despachado"], con_valores=False)
    y = h.tabla(y + 14, [("Código", 1.3, "izq"), ("Descripción", 5.2, "izq"), ("Cantidad", 1.2, "der"), ("Unidad", 1, "centro")],
                filas, filas_minimas=8)
    bultos = sum(juego["despachado"].values())
    h.texto(MARGEN, y + 16, f"Total de bultos: {miles(bultos)}", 9, True)
    timbre(h, y + 30)

    # Acuse de recibo del cliente
    x0 = ANCHO / 2 + 10
    h.recuadro(x0, y + 30, ANCHO - MARGEN, y + 130)
    h.texto(x0 + 8, y + 44, "ACUSE DE RECIBO", 8.5, True)
    for i, campo in enumerate(["Nombre:", "R.U.T.:", "Fecha:", "Recinto:", "Firma:"]):
        h.texto(x0 + 8, y + 60 + i * 15, campo, 8)
        h.linea(x0 + 50, y + 61 + i * 15, ANCHO - MARGEN - 10, y + 61 + i * 15, color=GRIS, grosor=0.4)
    h.pie()
    return doc


def factura(juego) -> pymupdf.Document:
    numero, fecha = juego["factura"]
    oc, fecha_oc = juego["oc"]
    guia, fecha_guia = juego["guia"]
    doc = pymupdf.open()
    h = Hoja(doc)
    emisor(h)
    recuadro_sii(h, "FACTURA ELECTRÓNICA", numero)
    dia, mes, anio = fecha.split("-")
    vencimiento = f"{int(dia):02d}-{int(mes) + 1:02d}-{anio}" if int(mes) < 12 else f"{dia}-01-{int(anio) + 1}"
    y = datos_receptor(h, MARGEN + 108, [("FECHA EMISIÓN", fecha), ("FECHA VENCIMIENTO", vencimiento),
                                         ("CONDICIÓN DE VENTA", "Crédito 30 días"), ("FORMA DE PAGO", "Transferencia")])
    y = referencias(h, y + 6, [("Orden de Compra", oc, fecha_oc), ("Guía de Despacho Electrónica", guia, fecha_guia)])

    filas, neto = filas_items(juego["facturado"], con_valores=True)
    y = h.tabla(y + 14, [("Código", 1.3, "izq"), ("Descripción", 4.2, "izq"), ("Cantidad", 1.1, "der"),
                         ("Unidad", 1, "centro"), ("Precio Unit.", 1.4, "der"), ("Valor", 1.5, "der")],
                filas, filas_minimas=8)
    fin_totales = totales(h, y + 12, neto, con_exento=True)
    timbre(h, y + 12)
    h.texto(MARGEN, fin_totales + 30, "Res. y fecha de autorización: documento de prueba, sin resolución del SII", 7.5, color=GRIS)
    h.texto(ANCHO - MARGEN, ALTO - 40, "CEDIBLE", 11, True, ROJO_SII, "der")
    h.pie()
    return doc


def main(salida: Path):
    salida.mkdir(parents=True, exist_ok=True)
    for juego in JUEGOS:
        carpeta = salida / juego["nombre"]
        carpeta.mkdir(exist_ok=True)
        for nombre, generar in ((f"OC_{juego['oc'][0]}", orden_de_compra),
                                (f"Guia_{juego['guia'][0]}", guia_de_despacho),
                                (f"Factura_{juego['factura'][0]}", factura)):
            doc = generar(juego)
            doc.set_metadata({"title": nombre.replace("_", " "), "subject": "Documento de prueba - sin validez tributaria",
                              "creator": "Documatch"})
            doc.subset_fonts()  # solo las letras usadas: cada PDF pesa KB en vez de MB
            doc.save(carpeta / f"{nombre}.pdf", garbage=3, deflate=True)
            print("creado", carpeta.name, f"{nombre}.pdf")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
