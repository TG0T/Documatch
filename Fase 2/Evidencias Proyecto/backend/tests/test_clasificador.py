from app.classifier.clasificador import DESCONOCIDO, clasificar, codigo, normalizar, numero_documento

FACTURA = """
R.U.T.: 76.123.456-7
FACTURA ELECTRÓNICA
N° 4521
S.I.I. - SANTIAGO CENTRO
Señor(es): Comercial Los Andes SpA
Giro: Venta de insumos
Forma de pago: Crédito 30 días
Fecha vencimiento: 15/11/2026
Referencias: Orden de Compra N° 8832
Monto Neto 100.000
IVA 19% 19.000
Total 119.000
CEDIBLE
"""

GUIA = """
R.U.T.: 76.123.456-7
GUÍA DE DESPACHO ELECTRÓNICA
N° 1203
Tipo de traslado: Operación constituye venta
Dirección de despacho: Av. Matta 1234, Santiago
Transportista: Transportes Sur Ltda.
Chofer: Juan Pérez   Patente: AB-CD-12
Bultos: 4
"""

ORDEN = """
ORDEN DE COMPRA N° 8832
Fecha: 01/10/2026
Proveedor: Distribuidora Central S.A.
Solicitante: Departamento de Logística
Centro de costo: 1050
Plazo de entrega: 5 días hábiles
Condiciones de pago: 30 días
Neto 100.000  IVA 19.000  Total 119.000
Aprobado por: Gerencia de Compras
"""


# Texto real del OCR de una OC de Mercado Público (documento público). Menciona "factura"
# varias veces en el encabezado y antes se clasificaba mal como factura.
ORDEN_MERCADO_PUBLICO = """
Rut: 60.101.000-3 Demandante : SECRETARIA GENERAL DE
GOBIERNO
Dirección TEATINOS N' 92,PISO 8, OF 853 Unidad de Compra: — Ministerio Secretaría General de
Toléfono : 56-2-26945301 Fecha Envio OC. : 12-08-2022 20:11:04
Estado : Aceptada
ORDEN DECOMPRA — N”: 876-329-SE22
SEÑOR (ES) : GO RESEARCH SPA
INOMBRE ORDEN DE COMPRA: — SC 1404 ESTUDIO ESTRATEGICO CUANTITATIVO
[FECHA ENTREGA PRODUCTOS :
DIRECCION DE ENVIO FACTURA: TEATINOS N'92,PISO 8, OF 853 Santiago Centro
DIRECCION DE DESPACHO :
METODO DE DESPACHO: Dospachar según programa adjuntado
FORMA DE PAGO: 30 días contra la recepción conforme de la factura
Disponibilidad Presupuestaria: Esta orden de compra cuenta con disponibilidad presupuestaria
ENVIAR XML A: DIPRESRECEPCIONACUSTODIUM.COM y FACTURA ELECTRÓNICA A: FACTURACIONAmsgg.g0b.cl
*ES IMPRESCINDIBLE QUE LA ORDEN DE COMPRA SEA ACEPTADA EN EL PORTAL POR PARTE DEL PROVEEDOR
Derechos del Proveedor del Mercado Público
"""


def test_orden_compra_mercado_publico():
    resultado = clasificar(ORDEN_MERCADO_PUBLICO)
    assert resultado.tipo == "orden_compra"
    # "factura" en "direccion de envio factura" no debe contar como título
    assert "[título en encabezado]" not in resultado.coincidencias["factura"]


def test_titulo_con_numero_en_medio_de_linea():
    # El OCR a veces junta el nombre del emisor y el título en la misma línea.
    texto = "Comercial Andes SpA   FACTURA ELECTRONICA N° 4521\nIVA 19%\nTotal 119.000"
    assert clasificar(texto).tipo == "factura"


def test_factura():
    # Aunque menciona una orden de compra en las referencias, debe ser factura.
    assert clasificar(FACTURA).tipo == "factura"


def test_guia_despacho():
    assert clasificar(GUIA).tipo == "guia_despacho"


def test_orden_compra():
    assert clasificar(ORDEN).tipo == "orden_compra"


def test_texto_sin_relacion():
    assert clasificar("Hola, esta es una carta cualquiera.").tipo == DESCONOCIDO


def test_tolera_errores_de_ocr_en_guia():
    # Tesseract a veces lee la "í" de guía como "1" o "l".
    assert clasificar("GU1A DE DESPACHO\nTransportista: X").tipo == "guia_despacho"


# Texto del OCR de una factura cuyo título quedó al final de una línea (venía en un recuadro) y
# con un recuadro de referencias a la OC que la originó antes de la tabla de ítems.
FACTURA_CON_REFERENCIAS = """
NILO & ARROYO CHILELIFT LTDA R.U.T.: 76.345.095-3
CHILELIFT VENTA Y DISTRIBUCION DE EQUIPOS — FACTURA ELECTRONICA
CASA MATRIZ: AV. AMERICO VESPUCIO 1380
QUILICURA - SANTIAGO N° 15962
S.I.I - SANTIAGO PONIENTE
Señor(es): Comercial Ejemplo Ltda Fecha: 18 de noviembre de 2021
Rut: 77.111.111-1 Forma de pago: Credito
Giro: Comercializacion de neumaticos
REFERENCIAS
ORDEN DE COMPRA FOLIO 22438 DEL 2021-11-18
FICHA Descripción Cantidad Precio Unit. Descuento Total
CGA900 EQUIPO PARA LA CORRECION DE CAMBER 1 849.000 849.000
Monto Neto: 849.000
Exento: 0
19% IVA: 161.310
"""


def test_referencia_a_orden_de_compra_no_es_el_titulo():
    resultado = clasificar(FACTURA_CON_REFERENCIAS)
    assert resultado.tipo == "factura"
    assert "[título en encabezado]" not in resultado.coincidencias["orden_compra"]


def test_numero_de_cada_tipo():
    assert clasificar(FACTURA).numero == "4521"
    assert clasificar(GUIA).numero == "1203"
    assert clasificar(ORDEN).numero == "8832"


def test_numero_con_guiones_y_letras():
    # No confunde el número de la OC con el de la dirección ("TEATINOS N' 92").
    assert clasificar(ORDEN_MERCADO_PUBLICO).numero == "876-329-SE22"


def test_numero_en_otra_linea_y_con_puntos_de_miles():
    # En los recuadros del SII el título y el número van en líneas distintas.
    texto = "R.U.T.: 96.502.540-5\nGUIA DE DESPACHO ELECTRONICA\nN° 178.880\nS.I.I. - SANTIAGO ORIENTE"
    assert clasificar(texto).numero == "178880"


def test_numero_de_la_referencia_no_cuenta():
    # El "N° 15962" de la factura, no el folio de la OC de las referencias.
    assert clasificar(FACTURA_CON_REFERENCIAS).numero == "15962"


def test_codigo_con_prefijo_del_tipo():
    assert codigo("orden_compra", "123") == "OC-123"
    assert codigo("guia_despacho", "123") == "G-123"
    assert codigo("factura", "123") == "F-123"
    assert codigo("factura", None) is None
    assert codigo(DESCONOCIDO, "123") is None


def test_numero_del_recuadro_sii_leido_por_el_ocr():
    # Texto real del OCR: la "º" chica de "Nº1" se lee como un 2 ("n21"), y el número queda al
    # final de una línea de la columna de la izquierda.
    texto = """R.U.T.:77.777.777-0
EMPRESA DE SEVICIOS ABC
SPA FACTURA DE COMPRA
Giro:SERVICIOS RELACIONADOS CON LA ELECTRONICA
ACUICULTURA MARINA
CALLE FALSA 123 508- SANTIAGO N21
S.I.I. - SANTIAGO CENTRO"""
    assert numero_documento("factura", normalizar(texto)) == "1"
