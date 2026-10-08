"""Palabras clave por tipo de documento.

Los patrones son expresiones regulares que se aplican sobre el texto normalizado
(minúsculas y sin tildes), por eso se escriben sin acentos: "guia", "electronica".

- "titulo": cómo se llama el documento. Suma BONO_TITULO si en el encabezado aparece al
  inicio de una línea o seguido del número del documento ("orden de compra n° 123").
  Así no cuenta una mención dentro de otra frase, como "direccion de envio factura".
- "prefijo": va antes del número del documento en su código ("OC-123", "G-123", "F-123").
- "claves": (patrón, peso). Cada patrón suma su peso una sola vez, aunque se repita.
  Usa pesos altos para frases exclusivas del tipo y bajos para términos compartidos.
"""

BONO_TITULO = 10

# Cantidad de líneas (no vacías) del inicio que se consideran "encabezado".
LINEAS_ENCABEZADO = 15

# Líneas del inicio donde se busca el número del documento. Son más que las del encabezado porque
# el OCR suele leer el recuadro del SII (título y número) después de los datos del emisor.
LINEAS_NUMERO = 40

# Puntaje mínimo para aceptar una clasificación; bajo esto se devuelve "desconocido".
PUNTAJE_MINIMO = 5

# Cómo se escribe "número" después del título. El OCR suele leer "N°" como "n*", "n'", "n”" o "n?".
MARCA_NUMERO = r"(n\s?[°º*'’\"”?.:]|nro\b|numero\b|folio\b)"

# El número del documento: "4521", "178.880", "876-329-SE22" (órdenes de Mercado Público).
NUMERO_DOCUMENTO = r"[a-z0-9]*\d[a-z0-9.]*(?:-[a-z0-9]+)*"

# El SII imprime "Nº" con la "º" chica y subrayada, y el OCR la lee como un 2 pegado al número:
# "Nº46" queda "n246". Solo se aplica a "n2" pegado al número, sin espacio.
MARCA_NUMERO_SII = r"n2(?=\d)"

# Cuántos caracteres puede haber entre el título y su número ("GUIA DE DESPACHO ELECTRONICA\nN° 46").
DISTANCIA_TITULO_NUMERO = 80

TIPOS_DOCUMENTO = {
    "factura": {
        "nombre": "Factura",
        "prefijo": "F",
        "titulo": r"\bfactura\b",
        "claves": [
            (r"factura\s+(electronica|afecta|exenta)", 6),
            (r"\bfactura\b", 3),
            (r"fecha\s+(de\s+)?vencimiento", 2),
            (r"\bcedible\b", 2),
            (r"acuse\s+de\s+recibo", 1),
            (r"\biva\b", 1),
            (r"monto\s+neto|\bneto\b", 1),
            (r"monto\s+exento|\bexento\b", 1),
            (r"\bgiro\b", 1),
        ],
    },
    "guia_despacho": {
        "nombre": "Guía de despacho",
        "prefijo": "G",
        "titulo": r"gu[i1l]a\s*de\s*despacho",
        "claves": [
            (r"gu[i1l]a\s+de\s+despacho", 6),
            (r"no\s+constituye\s+venta", 5),
            (r"(tipo|indicador|motivo)\s+de\s+traslado", 4),
            (r"\btraslado\b", 2),
            (r"\btransportista\b", 3),
            (r"\b(chofer|conductor)\b", 3),
            (r"\bpatente\b", 3),
            (r"direccion\s+de\s+(despacho|destino|entrega)", 2),
            (r"\bbultos?\b", 1),
            (r"\bdespacho\b", 1),
        ],
    },
    "orden_compra": {
        "nombre": "Orden de compra",
        "prefijo": "OC",
        "titulo": r"orden\s*de\s*compra",  # el OCR a veces lee "decompra"
        "claves": [
            (r"orden\s+de\s+compra", 5),
            (r"\bproveedor\b", 3),
            (r"(fecha|plazo|lugar)\s+(de\s+)?entrega", 3),
            (r"fecha\s+envio\s+o\.?c\b", 4),
            (r"unidad\s+de\s+compra", 4),
            (r"\bdemandante\b", 3),
            (r"disponibilidad\s+presupuestaria", 3),
            (r"mercado\s+publico|chilecompra", 2),
            (r"trato\s+directo|licitacion", 2),
            (r"condiciones?\s+de\s+pago", 2),
            (r"\b(comprador|solicitante|solicitado\s+por)\b", 2),
            (r"\b(aprobado|autorizado)\s+por\b", 2),
            (r"centro\s+de\s+costos?", 2),
            (r"\bcotizacion\b", 1),
        ],
    },
}
