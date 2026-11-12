"""Reglas que combinan las dos lecturas de Tesseract y corrigen sus errores típicos. Las cajas y
confianzas son las que dio Tesseract en documentos de prueba escaneados."""
from PIL import Image, ImageDraw, ImageFont

from app.services.ocr import Leida, Palabra, angulo_inclinacion, combinar, unir_numeros_partidos

RENGLON = (1, 1, 1)


def leida(texto, x0, y0, x1, y1, confianza, renglon=RENGLON):
    return Leida(Palabra(texto, x0, y0, x1, y1), confianza, renglon)


def textos(leidas):
    return [l.palabra.texto for l in leidas]


def test_agrega_la_celda_que_la_lectura_normal_se_salto():
    # El folio de la OC en la tabla de referencias de una guía
    normal = [leida("Orden", 111, 749, 160, 770, 92)]
    dispersa = [leida("4500019020", 669, 749, 790, 770, 96)]
    assert textos(combinar(normal, dispersa)) == ["Orden", "4500019020"]


def test_no_agrega_basura_de_timbres():
    normal = [leida("Orden", 111, 749, 160, 770, 92)]
    dispersa = [leida("Ea", 2337, 2300, 2370, 2330, 26), leida("a", 2319, 2400, 2330, 2420, 66),
                leida("=", 2274, 2274, 2290, 2290, 96)]
    assert textos(combinar(normal, dispersa)) == ["Orden"]


def test_numero_de_varias_cifras_con_confianza_media_se_agrega():
    # El total "849.000" de una línea, leído solo por la dispersa con confianza 79
    dispersa = [leida("849.000", 1405, 59, 1467, 80, 79)]
    assert textos(combinar([], dispersa)) == ["849.000"]


def test_corrige_un_digito_mal_leido_con_la_lectura_mas_confiable():
    normal = [leida("f", 2090, 1550, 2105, 1576, 52), leida("<", 2088, 1691, 2107, 1717, 63)]
    dispersa = [leida("7", 2089, 1550, 2107, 1576, 96), leida("4", 2088, 1691, 2107, 1717, 96)]
    assert textos(combinar(normal, dispersa)) == ["7", "4"]


def test_un_signo_se_reemplaza_por_el_numero_aunque_la_caja_sea_distinta():
    # "4" leído como "-": la caja del guion es mucho más baja que la del dígito
    normal = [leida("-", 2088, 1490, 2107, 1494, 89)]
    dispersa = [leida("4", 2088, 1479, 2107, 1505, 96)]
    assert textos(combinar(normal, dispersa)) == ["4"]


def test_no_reemplaza_una_palabra_por_un_pedazo_de_ella():
    # La dispersa leyó "lad" (el final de "Cantidad") con más confianza
    normal = [leida("Cantidad", 820, 518, 920, 540, 80)]
    dispersa = [leida("lad", 881, 518, 920, 540, 90)]
    assert textos(combinar(normal, dispersa)) == ["Cantidad"]


def test_reemplaza_un_numero_partido_por_la_lectura_entera():
    normal = [leida("N°", 1197, 204, 1231, 228, 69), leida("450001", 1242, 204, 1348, 229, 80),
              leida("9030", 1354, 204, 1426, 229, 78)]
    dispersa = [leida("4500019030", 1242, 204, 1426, 229, 96)]
    assert textos(combinar(normal, dispersa)) == ["N°", "4500019030"]


def test_une_numeros_partidos_pegados():
    partes = [leida("450001", 1242, 204, 1348, 229, 80), leida("9030", 1354, 204, 1426, 229, 78)]
    assert textos(unir_numeros_partidos(partes)) == ["4500019030"]


def test_no_une_numeros_separados_por_un_espacio_normal():
    # Un teléfono y dos columnas de una tabla
    telefono = [leida("72", 760, 204, 785, 229, 95), leida("271", 790 + 8, 204, 830, 229, 95)]
    columnas = [leida("20", 2069, 1690, 2107, 1717, 96), leida("4.290", 2300, 1690, 2380, 1717, 96)]
    assert textos(unir_numeros_partidos(telefono)) == ["72", "271"]
    assert textos(unir_numeros_partidos(columnas)) == ["20", "4.290"]


def test_detecta_la_inclinacion_de_un_escaneo():
    imagen = Image.new("L", (1400, 1000), 255)
    dibujo = ImageDraw.Draw(imagen)
    fuente = ImageFont.truetype("arial.ttf", 28)
    for i in range(15):
        dibujo.text((60, 60 + i * 55), "Tubo PVC sanitario 110 mm x 6 m      12      UN      12.990", font=fuente, fill=0)
    assert abs(angulo_inclinacion(imagen)) < 0.1  # derecho: no se toca
    torcida = imagen.rotate(1.0, fillcolor=255)
    assert abs(angulo_inclinacion(torcida) + 1.0) <= 0.15  # se endereza girando al revés
