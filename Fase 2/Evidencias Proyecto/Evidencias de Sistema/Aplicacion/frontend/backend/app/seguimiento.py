"""Compara lo pedido en una orden de compra con lo despachado (guías) y lo facturado.

Se comparan las cantidades totales de cada documento: los ítems no se pueden emparejar uno a
uno porque el OCR lee las descripciones de forma distinta en cada documento.
"""
from dataclasses import dataclass

PENDIENTE = "pendiente"  # falta la guía o la factura, sin diferencias hasta ahora
OK = "ok"  # todo coincide
PARCIAL = "parcial"  # se despachó menos de lo pedido (y se facturó lo despachado)
DISCREPANCIA = "discrepancia"  # cualquier otra diferencia
FINALIZADA = "finalizada"  # despacho parcial que se dio por terminado (acuerdo con el proveedor)


@dataclass
class Estado:
    estado: str
    detalle: str
    puede_finalizar: bool = False  # despacho parcial ya facturado: se puede dar por terminado


def formato(n: float) -> str:
    """Cantidad en formato chileno: 1.500 / 2,5."""
    texto = f"{n:,.3f}".rstrip("0").rstrip(".")
    return texto.replace(",", "_").replace(".", ",").replace("_", ".")


def comparar(pedido: float | None, despachos: list[float | None], facturas: list[float | None],
             finalizada: bool = False, motivo: str | None = None) -> Estado:
    """`pedido`: cantidad total de la OC. `despachos` y `facturas`: cantidad total de cada guía
    y de cada factura de la OC (None si el OCR no encontró la tabla de ítems).

    Una OC con despacho parcial y facturada por lo recibido se puede finalizar (`finalizada`): se
    da por terminada sin esperar el resto. Si después llega otra guía o factura que cambia las
    cantidades, vuelve a mostrar el estado que corresponda."""
    estado = comparar_cantidades(pedido, despachos, facturas)
    if estado.estado == PARCIAL and facturas:
        if finalizada:
            detalle = f"Finalizada con despacho parcial: {estado.detalle.removeprefix('Despachado ')}"
            return Estado(FINALIZADA, f"{detalle} · {motivo}" if motivo else detalle)
        estado.puede_finalizar = True
    return estado


def comparar_cantidades(pedido: float | None, despachos: list[float | None], facturas: list[float | None]) -> Estado:
    if pedido is None:
        return Estado(DISCREPANCIA, "No se pudo leer la cantidad de la orden de compra")
    if None in despachos:
        return Estado(DISCREPANCIA, "No se pudo leer la cantidad de una guía de despacho")
    if None in facturas:
        return Estado(DISCREPANCIA, "No se pudo leer la cantidad de una factura")

    diferencias = []
    parcial = False
    despachado = sum(despachos) if despachos else None
    if despachado is not None and despachado != pedido:
        if despachado < pedido:
            parcial = True
            diferencias.append(f"Despachado {formato(despachado)} de {formato(pedido)}")
        else:
            diferencias.append(f"Despachado {formato(despachado)}, más de lo pedido ({formato(pedido)})")

    if facturas:
        facturado = sum(facturas)
        # Se factura lo que se recibió; si aún no hay guía, lo pedido.
        esperado, contra = (despachado, "despachado") if despachado is not None else (pedido, "pedido")
        if facturado != esperado:
            diferencias.append(f"Facturado {formato(facturado)}, {contra} {formato(esperado)}")
            parcial = False

    if diferencias:
        return Estado(PARCIAL if parcial else DISCREPANCIA, " · ".join(diferencias))
    faltan = [nombre for nombre, docs in (("guía de despacho", despachos), ("factura", facturas)) if not docs]
    if faltan:
        return Estado(PENDIENTE, "Falta " + " y ".join(faltan))
    return Estado(OK, "Pedido, despacho y factura coinciden")
