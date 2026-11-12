"""Genera un lote variado de documentos de prueba: varios proveedores, compradores, productos y
escenarios, y cada documento en un formato distinto (PDF digital, PNG, JPG escaneado o PDF
escaneado) para probar tanto la lectura de texto digital como el OCR.

Usa los diseños de generar_documentos.py. Es reproducible: la misma semilla da el mismo lote.
También escribe esperado.csv con lo que el sistema debería leer de cada documento.

Uso: python generar_lote.py <carpeta de salida> [cantidad de juegos] [semilla]
"""
import csv
import io
import random
import sys
from pathlib import Path

import numpy as np
import pymupdf
from PIL import Image, ImageFilter

import generar_documentos as gd

PROVEEDORES = [
    gd.PROVEEDOR,
    {"razon": "DISTRIBUIDORA AUSTRAL LTDA.", "rut": gd.rut(76915302),
     "giro": "Distribución de insumos industriales y de seguridad", "direccion": "Av. Pedro Montt 2450",
     "comuna": "Puerto Montt", "ciudad": "Puerto Montt", "telefono": "+56 65 225 8800",
     "correo": "contacto@austral-demo.cl", "sii": "S.I.I. - PUERTO MONTT"},
    {"razon": "COMERCIAL PACÍFICO NORTE SpA", "rut": gd.rut(77204581),
     "giro": "Venta al por mayor de artículos de ferretería", "direccion": "Calle Baquedano 870",
     "comuna": "Antofagasta", "ciudad": "Antofagasta", "telefono": "+56 55 241 3300",
     "correo": "ventas@pacificonorte-demo.cl", "sii": "S.I.I. - ANTOFAGASTA"},
    {"razon": "INSUMOS TÉCNICOS DEL MAULE LTDA.", "rut": gd.rut(76630147),
     "giro": "Comercialización de materiales eléctricos y de construcción", "direccion": "1 Sur 1350",
     "comuna": "Talca", "ciudad": "Talca", "telefono": "+56 71 261 4400",
     "correo": "ventas@maule-demo.cl", "sii": "S.I.I. - TALCA"},
]

COMPRADORES = [
    gd.COMPRADOR,
    {"razon": "MINERA CERRO ALTO SpA", "rut": gd.rut(76118920), "giro": "Extracción de minerales de cobre",
     "direccion": "Camino a Mina km 12", "comuna": "Calama", "ciudad": "Calama", "telefono": "+56 55 234 9000",
     "despacho": "Bodega central faena Cerro Alto, Camino a Mina km 12, Calama"},
    {"razon": "AGRÍCOLA LOS NOGALES LTDA.", "rut": gd.rut(77455013), "giro": "Cultivo de frutales",
     "direccion": "Parcela 14, Camino Lo Herrera", "comuna": "San Fernando", "ciudad": "San Fernando",
     "telefono": "+56 72 271 5500", "despacho": "Packing Los Nogales, Parcela 14, San Fernando"},
]

MAS_PRODUCTOS = {
    "CAB-25": ("Cable eléctrico THHN 2,5 mm (rollo 100 m)", "ROLLO", 42990),
    "INT-SIM": ("Interruptor simple embutido", "UN", 2190),
    "LED-18": ("Tubo LED T8 18 W", "UN", 3490),
    "ZAP-SEG": ("Zapato de seguridad punta acero", "PAR", 32990),
    "LEN-SEG": ("Lentes de seguridad claros", "UN", 2490),
    "MAN-34": ('Manguera de riego 3/4" (rollo 25 m)', "ROLLO", 19990),
    "FER-UR": ("Fertilizante urea saco 25 kg", "SACO", 21490),
    "TER-RG": ("Terciado ranurado 15 mm 1,22 x 2,44 m", "UN", 27990),
}
gd.PRODUCTOS.update(MAS_PRODUCTOS)

# Escenario: cómo se despacha y factura lo pedido
ESCENARIOS = ["conciliado", "despacho_parcial", "discrepancia", "pendiente", "sin_factura", "dos_guias"]
ESTADO_ESPERADO = {"conciliado": "ok", "despacho_parcial": "parcial", "discrepancia": "discrepancia",
                   "pendiente": "pendiente", "sin_factura": "pendiente", "dos_guias": "ok"}

FORMATOS = ["pdf", "png", "jpg_escaneado", "pdf_escaneado"]


def fecha(dia: int) -> str:
    return f"{dia:02d}-11-2026"


def armar_juego(n: int, escenario: str, azar: random.Random) -> dict:
    codigos = azar.sample(sorted(gd.PRODUCTOS), azar.randint(2, 4))
    pedido = {c: azar.choice([5, 8, 10, 12, 15, 20, 24, 30, 40, 50, 60]) for c in codigos}
    dia = 2 + n % 20
    juego = {
        "proveedor": azar.choice(PROVEEDORES),
        "comprador": azar.choice(COMPRADORES),
        "oc": (f"45000190{n:02d}", fecha(dia)),
        "pedido": pedido,
        "guias": [],
        "factura": None,
    }
    if escenario == "pendiente":
        return juego
    despachado = dict(pedido)
    if escenario == "despacho_parcial":
        primero = codigos[0]
        despachado[primero] = pedido[primero] // 2
    if escenario == "dos_guias":
        # Mitad de cada producto en la primera guía y el resto en la segunda
        primera = {c: q // 2 for c, q in pedido.items()}
        segunda = {c: q - primera[c] for c, q in pedido.items()}
        juego["guias"] = [(f"590{n:02d}1", fecha(dia + 2), primera), (f"590{n:02d}2", fecha(dia + 4), segunda)]
    else:
        juego["guias"] = [(f"590{n:02d}1", fecha(dia + 2), despachado)]
    if escenario == "sin_factura":
        return juego
    facturado = dict(despachado)
    if escenario == "discrepancia":
        facturado[codigos[-1]] += 1  # se cobra una unidad más de lo recibido
    juego["factura"] = (f"320{n:02d}", fecha(dia + 5), facturado)
    return juego


def con_empresas(juego):
    """Los diseños usan el proveedor y comprador del módulo: se cambian para este juego."""
    gd.PROVEEDOR, gd.COMPRADOR = juego["proveedor"], juego["comprador"]


def documentos(juego):
    """(tipo, folio, pymupdf.Document, cantidades, con valores) de cada documento del juego."""
    con_empresas(juego)
    oc, fecha_oc = juego["oc"]
    base = {"oc": juego["oc"], "pedido": juego["pedido"]}
    salida = [("OC", oc, gd.orden_de_compra(base), juego["pedido"], True)]
    for folio, fecha_guia, cantidades in juego["guias"]:
        salida.append(("Guia", folio, gd.guia_de_despacho({**base, "guia": (folio, fecha_guia), "despachado": cantidades}),
                       cantidades, False))
    if juego["factura"]:
        folio, fecha_factura, cantidades = juego["factura"]
        primera_guia = juego["guias"][0][:2]
        salida.append(("Factura", folio, gd.factura({**base, "guia": primera_guia, "factura": (folio, fecha_factura),
                                                     "facturado": cantidades}), cantidades, True))
    return salida


def escanear(doc: pymupdf.Document, azar: random.Random) -> bytes:
    """Imita un escaneo: gris, levemente torcido, con ruido y algo de desenfoque (JPG)."""
    pix = doc[0].get_pixmap(dpi=200, colorspace=pymupdf.csGRAY)
    imagen = Image.frombytes("L", (pix.width, pix.height), pix.samples)
    imagen = imagen.rotate(azar.uniform(-1.2, 1.2), resample=Image.BICUBIC, fillcolor=255)
    ruido = np.random.default_rng(azar.randint(0, 10**6)).normal(0, 7, (imagen.height, imagen.width))
    imagen = Image.fromarray(np.clip(np.asarray(imagen, dtype=float) + ruido, 0, 255).astype(np.uint8))
    imagen = imagen.filter(ImageFilter.GaussianBlur(0.6))
    salida = io.BytesIO()
    imagen.save(salida, format="JPEG", quality=72)
    return salida.getvalue()


def guardar(doc: pymupdf.Document, formato: str, ruta: Path, azar: random.Random) -> Path:
    if formato == "pdf":
        doc.subset_fonts()
        ruta = ruta.with_suffix(".pdf")
        doc.save(ruta, garbage=3, deflate=True)
    elif formato == "png":
        ruta = ruta.with_suffix(".png")
        doc[0].get_pixmap(dpi=150).save(ruta)
    elif formato == "jpg_escaneado":
        ruta = ruta.with_suffix(".jpg")
        ruta.write_bytes(escanear(doc, azar))
    else:  # pdf_escaneado: el escaneo dentro de un PDF, sin texto digital
        ruta = ruta.with_suffix(".pdf")
        escaneado = pymupdf.open()
        pagina = escaneado.new_page(width=gd.ANCHO, height=gd.ALTO)
        pagina.insert_image(pagina.rect, stream=escanear(doc, azar))
        escaneado.save(ruta, garbage=3, deflate=True)
    return ruta


def main(salida: Path, cantidad: int = 12, semilla: int = 2026):
    azar = random.Random(semilla)
    salida.mkdir(parents=True, exist_ok=True)
    filas = []
    for n in range(1, cantidad + 1):
        escenario = ESCENARIOS[(n - 1) % len(ESCENARIOS)]
        juego = armar_juego(n, escenario, azar)
        docs = documentos(juego)
        # Formatos mezclados: cada documento del juego en uno distinto, rotando entre juegos
        formatos = [FORMATOS[(n + i) % len(FORMATOS)] for i in range(len(docs))]
        carpeta = salida / f"{n:02d}_{escenario}"
        carpeta.mkdir(exist_ok=True)
        for orden, ((tipo, folio, doc, cantidades, con_valores), formato) in enumerate(zip(docs, formatos), 1):
            ruta = guardar(doc, formato, carpeta / f"{orden}_{tipo}_{folio}_{formato}", azar)
            neto = sum(q * gd.PRODUCTOS[c][2] for c, q in cantidades.items())
            filas.append({
                "juego": carpeta.name, "orden_de_carga": orden, "archivo": ruta.name, "formato": formato,
                "tipo": {"OC": "orden_compra", "Guia": "guia_despacho", "Factura": "factura"}[tipo],
                "folio": folio, "oc": juego["oc"][0], "cantidad_total": sum(cantidades.values()),
                "valor_neto": neto if con_valores else "", "estado_esperado_oc": ESTADO_ESPERADO[escenario],
                "proveedor": juego["proveedor"]["razon"], "comprador": juego["comprador"]["razon"],
            })
        print("creado", carpeta.name, " ".join(formatos))
    with open(salida / "esperado.csv", "w", newline="", encoding="utf-8-sig") as f:
        escritor = csv.DictWriter(f, fieldnames=list(filas[0]), delimiter=";")
        escritor.writeheader()
        escritor.writerows(filas)
    print(f"{len(filas)} documentos en {cantidad} juegos · esperado.csv")


if __name__ == "__main__":
    main(Path(sys.argv[1]), *(int(a) for a in sys.argv[2:4]))
