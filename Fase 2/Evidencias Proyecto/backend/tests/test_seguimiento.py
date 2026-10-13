from app.seguimiento import DISCREPANCIA, OK, PARCIAL, PENDIENTE, comparar


def test_todo_coincide():
    assert comparar(10, [10], [10]).estado == OK


def test_varias_guias_suman_lo_pedido():
    assert comparar(10, [6, 4], [10]).estado == OK


def test_solo_la_orden_esta_pendiente():
    estado = comparar(10, [], [])
    assert estado.estado == PENDIENTE
    assert estado.detalle == "Falta guía de despacho y factura"


def test_falta_la_factura():
    assert comparar(10, [10], []).detalle == "Falta factura"


def test_despacho_parcial():
    # Se despachó menos de lo pedido y se facturó lo despachado.
    estado = comparar(10, [6], [6])
    assert estado.estado == PARCIAL
    assert estado.detalle == "Despachado 6 de 10"


def test_despacho_parcial_sin_factura():
    assert comparar(10, [6], []).estado == PARCIAL


def test_se_facturo_mas_de_lo_despachado():
    estado = comparar(10, [10], [11])
    assert estado.estado == DISCREPANCIA
    assert estado.detalle == "Facturado 11, despachado 10"


def test_se_despacho_mas_de_lo_pedido():
    assert comparar(10, [12], [12]).estado == DISCREPANCIA


def test_factura_sin_guia_se_compara_con_lo_pedido():
    assert comparar(10, [], [8]).detalle == "Facturado 8, pedido 10"


def test_cantidad_ilegible():
    assert comparar(None, [], []).estado == DISCREPANCIA
    assert comparar(10, [None], []).estado == DISCREPANCIA


def test_formato_chileno():
    assert comparar(1500, [2.5], []).detalle == "Despachado 2,5 de 1.500"
