from pathlib import Path

import pymupdf

from app.extraccion.mercancias import (
    Item,
    a_numero,
    extraer_items,
    montos_netos,
    separador_decimal,
    verificar_valores,
)
from app.services.ocr import Palabra, extraer

ALTO = 20
FIXTURES = Path(__file__).parent / "fixtures"


def pagina(*filas: list[tuple[str, int]], interlineado: int = 40) -> list[Palabra]:
    """Arma las palabras de una página como las entregaría el OCR: cada fila es una lista
    de (texto, x). Las palabras con espacios se separan como lo hace Tesseract."""
    palabras = []
    for n, fila in enumerate(filas):
        y = 100 + n * interlineado
        for texto, x in fila:
            for parte in texto.split():
                ancho = len(parte) * 10
                palabras.append(Palabra(parte, x, y, x + ancho, y + ALTO))
                x += ancho + 6
    return palabras


ENCABEZADO = [("Código", 0), ("Descripción", 100), ("Cantidad", 500), ("Precio Unitario", 650), ("Total", 850)]


def resumen(paginas):
    return [(i.descripcion, i.cantidad) for i in extraer_items(paginas)]


def test_lee_la_cantidad_bajo_su_columna():
    palabras = pagina(
        ENCABEZADO,
        # La descripción y los precios también tienen números: solo vale el de la columna Cantidad.
        [("A-1", 0), ("Tubo PVC 110 mm", 100), ("12", 520), ("3.500", 660), ("42.000", 850)],
        [("B-2", 0), ("Cemento 25 kg", 100), ("1.500", 510), ("120", 660), ("180.000", 850)],
        [("Neto", 650), ("222.000", 850)],
        [("Total", 650), ("264.180", 850)],
    )
    assert resumen([palabras]) == [("Tubo PVC 110 mm", 12), ("Cemento 25 kg", 1500)]
    # El valor total de cada línea sale de la columna "Total", no del precio unitario.
    assert [i.total for i in extraer_items([palabras])] == [42000, 180000]


def test_descripcion_en_varias_lineas():
    palabras = pagina(
        ENCABEZADO,
        [("A-1", 0), ("Cable eléctrico", 100), ("2,5", 520), ("45.000", 660), ("112.500", 850)],
        [("color rojo", 100)],
        [("Subtotal", 650), ("112.500", 850)],
    )
    assert resumen([palabras]) == [("Cable eléctrico color rojo", 2.5)]


def test_ignora_lineas_sueltas_con_cantidad():
    # "Cantidad de bultos" no es el encabezado de una tabla de ítems.
    palabras = pagina([("Cantidad de bultos: 4", 0)], [("Transportista: Sur", 0)])
    assert extraer_items([palabras]) == []


def test_sin_tabla_no_hay_items():
    assert extraer_items([pagina([("Hola, esta es una carta cualquiera.", 0)])]) == []
    assert extraer_items([[]]) == []


def test_cantidad_antes_de_la_descripcion():
    # Formato de guía de despacho: "Cant. | Unidad | Detalle"
    palabras = pagina(
        [("Cant.", 0), ("Unidad", 100), ("Detalle", 250)],
        [("10", 10), ("UN", 100), ("Pallet madera 120x100", 250)],
        [("3", 10), ("CJ", 100), ("Guantes nitrilo talla 8", 250)],
    )
    assert resumen([palabras]) == [("Pallet madera 120x100", 10), ("Guantes nitrilo talla 8", 3)]


def test_la_tabla_termina_con_un_salto_grande():
    palabras = pagina(
        ENCABEZADO,
        [("A-1", 0), ("Clavos", 100), ("5", 520), ("1.000", 660), ("5.000", 850)],
        [], [], [], [],  # espacio en blanco
        [("Notas internas 99", 100), ("7", 520)],
    )
    assert resumen([palabras]) == [("Clavos", 5)]


def test_items_de_varias_paginas():
    p1 = pagina(ENCABEZADO, [("A-1", 0), ("Clavos", 100), ("5", 520), ("1.000", 660), ("5.000", 850)])
    p2 = pagina(ENCABEZADO, [("B-2", 0), ("Martillo", 100), ("2", 520), ("8.000", 660), ("16.000", 850)])
    assert resumen([p1, p2]) == [("Clavos", 5), ("Martillo", 2)]


def test_a_numero_formato_chileno():
    assert a_numero("1.500") == 1500
    assert a_numero("2.000,50") == 2000.5
    assert a_numero("2,5") == 2.5
    assert a_numero("1.5") == 1.5
    assert a_numero("|12|") == 12
    assert a_numero("UN") is None
    assert a_numero("A-100") is None
    assert a_numero("1.234.567") == 1234567


def test_a_numero_con_punto_decimal():
    # Documentos en formato estadounidense: "51,600.00"
    assert a_numero("51,600.00", ".") == 51600
    assert a_numero("2,580.00") == 2580  # con ambos separadores el formato es evidente
    assert a_numero("503,600", ".") == 503600  # ambiguo: depende del formato del documento
    assert a_numero("503,600", ",") == 503.6
    assert a_numero("12.50", ".") == 12.5
    assert a_numero("2.790.00", ".") == 2790  # el OCR leyó la coma de los miles como punto


def test_separador_decimal_del_documento():
    assert separador_decimal(pagina([("2,580.00 51,600.00 503,600", 0)])) == "."
    assert separador_decimal(pagina([("1034,26 13.445", 0)])) == ","
    assert separador_decimal(pagina([("20 50", 0)])) == ","  # sin pistas: formato chileno


def test_pdf_con_texto_digital():
    pdf = pymupdf.open()
    hoja = pdf.new_page()
    lineas = [
        (["Código", "Descripción", "Cantidad", "Total"], 100),
        (["A-1", "Clavos 2 pulgadas", "40", "8.000"], 130),
        (["B-2", "Martillo", "3", "24.000"], 160),
        (["", "", "Total", "32.000"], 210),
    ]
    for celdas, y in lineas:
        for x, texto in zip([40, 110, 330, 450], celdas):
            if texto:
                hoja.insert_text((x, y), texto, fontsize=10)
    extraccion = extraer(pdf.tobytes(), ".pdf")
    assert resumen(extraccion.paginas) == [("Clavos 2 pulgadas", 40), ("Martillo", 3)]



def test_tabla_con_bordes_y_encabezado_gris():
    # Recorte de una orden de compra real hecha en Word (solo la tabla de productos). Con los
    # bordes y el sombreado gris, Tesseract se saltaba la fila del ítem completa.
    datos = (FIXTURES / "oc_tabla_bordes.png").read_bytes()
    items = extraer_items(extraer(datos, ".png").paginas)
    assert [(i.descripcion, i.cantidad) for i in items] == [("KOMBUCHA BETARRAGA BOTELLON", 13)]
    # "Precio" / "Total*" en dos líneas
    assert items[0].total == 13445


def test_borde_de_celda_pegado_al_encabezado():
    # Plantilla de factura del SII (datos ficticios). El OCR lee el encabezado "CANTIDAD"
    # como "ICanTIDACI" porque el borde vertical de la celda se pega a la palabra.
    datos = (FIXTURES / "factura_borde_en_encabezado.png").read_bytes()
    items = extraer_items(extraer(datos, ".png").paginas)
    assert [i.cantidad for i in items] == [2, 1, 10]
    assert [i.total for i in items] == [10000, 20000, 70000]  # columna "VALOR"
    assert items[2].descripcion.startswith("Producto 3")
    assert "SubProducto 3.a" in items[2].descripcion  # la descripción sigue en las líneas de abajo


def test_encabezado_con_texto_blanco_sobre_color():
    # Recorte de una factura real: encabezado de tabla con letras blancas sobre una franja azul
    # y la cantidad alineada a la derecha de su columna, lejos del centro del encabezado.
    datos = (FIXTURES / "factura_encabezado_azul.png").read_bytes()
    items = extraer_items(extraer(datos, ".png").paginas)
    assert [i.cantidad for i in items] == [1]
    # El total (849.000) no se revisa aquí: en este recorte Tesseract lee el 8 como 2 por lo
    # pequeño de la letra; en la factura completa lo lee bien.
    assert items[0].total is not None
    assert "CORRECION DE CAMBER" in items[0].descripcion
    assert "GH-900" in items[0].descripcion  # segunda línea de la descripción, bajo la cantidad
    assert "FICHA" not in items[0].descripcion  # enlace "Ver ficha" de una columna sin encabezado


def test_encabezado_en_dos_lineas():
    palabras = pagina(
        [("Descripción", 100), ("Cant.", 500), ("Precio", 650), ("Precio", 850)],
        [("Unitario", 640), ("Total", 850)],
        [("Clavos", 100), ("5", 520), ("1.000", 660), ("5.000", 850)],
        [("Martillo", 100), ("2", 520), ("8.000", 660), ("16.000", 850)],
        interlineado=30,
    )
    items = extraer_items([palabras])
    assert [(i.descripcion, i.cantidad, i.total) for i in items] == [("Clavos", 5, 5000), ("Martillo", 2, 16000)]


def test_valor_unitario_no_es_el_total():
    palabras = pagina(
        [("Descripción", 100), ("Cantidad", 500), ("Valor Unitario", 650), ("Valor Total", 900)],
        [("Clavos", 100), ("5", 520), ("1.000", 680), ("5.000", 920)],
    )
    assert [i.total for i in extraer_items([palabras])] == [5000]


def test_sin_columna_de_total():
    palabras = pagina(
        [("Cant.", 0), ("Unidad", 100), ("Detalle", 250)],
        [("10", 10), ("UN", 100), ("Pallet madera", 250)],
    )
    assert [i.total for i in extraer_items([palabras])] == [None]


def test_orden_de_compra_con_punto_decimal():
    # Recorte de una orden de compra real: montos en formato "51,600.00" y neto "503,600".
    datos = (FIXTURES / "oc_punto_decimal.png").read_bytes()
    extraccion = extraer(datos, ".png")
    items = extraer_items(extraccion.paginas)
    assert [(i.cantidad, i.total) for i in items] == [(20, 51600), (10, 253000), (50, 139500), (50, 59500)]
    # "Sub-Total 503,600" y "Neto Afecto 503,600" (no 503,6)
    assert montos_netos(extraccion.paginas) == [503600, 503600]
    assert verificar_valores(items, montos_netos(extraccion.paginas)) == (True, 503600)


def test_montos_netos_a_la_derecha_de_la_etiqueta():
    palabras = pagina(
        [("Forma de Pago: 60 dias", 0), ("Sub-Total", 600), ("503.600", 800)],
        [("Monto Neto $", 600), ("100.000", 800)],
        [("IVA 19%", 600), ("19.000", 800)],
    )
    # El "60" de la forma de pago está a la izquierda de la etiqueta: no cuenta.
    assert montos_netos([palabras]) == [503600, 100000]


def test_verificar_valores():
    items = [Item("A", 2, 10000), Item("B", 13, 13445)]
    assert verificar_valores(items, [23445]) == (True, 23445)
    assert verificar_valores(items, [23446]) == (True, 23446)  # redondeo de los totales por línea
    # Un dígito mal leído por el OCR (849.000 -> 249.000) no cuadra con el neto
    assert verificar_valores(items, [83445]) == (False, 83445)
    # Subtotal antes de un descuento global y neto después: basta con que coincida uno
    assert verificar_valores(items, [23445, 20000]) == (True, 23445)
    # Sin neto en el documento no hay con qué comparar
    assert verificar_valores(items, []) == (None, None)
    # Si falta el valor de algún ítem, hay que revisar
    assert verificar_valores([Item("A", 2, None)], [100]) == (False, 100)


def test_encabezado_partido_en_dos_filas_por_foto_torcida():
    # En una foto algo torcida el OCR deja "Codigo Cant." y "Descripcion Total" en filas distintas,
    # y el total del ítem queda un poco más arriba que su cantidad: no debe leerse como cantidad.
    palabras = pagina(
        [("Descripcion", 400), ("P.Unitario", 700), ("Total", 900)],
        [("138.693", 900)],
        [("KYO-TK-3462", 0), ("1", 250), ("TONER NEGRO", 300)],
        interlineado=12,
    )
    palabras += pagina([("Codigo", 0), ("Cant.", 250)], interlineado=12)[:2]
    for p in palabras[-2:]:
        p.y0 += 6
        p.y1 += 6
    assert resumen([palabras]) == [("TONER NEGRO", 1)]
