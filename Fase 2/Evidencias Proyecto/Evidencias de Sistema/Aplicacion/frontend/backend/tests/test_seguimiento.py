from app.seguimiento import DISCREPANCIA, FINALIZADA, OK, PARCIAL, PENDIENTE, comparar


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


def test_parcial_facturado_se_puede_finalizar():
    assert comparar(200, [116], [116]).puede_finalizar
    # Sin factura, o con una diferencia de cobro, no
    assert not comparar(200, [116], []).puede_finalizar
    assert not comparar(200, [116], [120]).puede_finalizar
    assert not comparar(200, [200], [200]).puede_finalizar


def test_orden_finalizada():
    estado = comparar(200, [116], [116], finalizada=True, motivo="Acuerdo con proveedor")
    assert estado.estado == FINALIZADA
    assert estado.detalle == "Finalizada con despacho parcial: 116 de 200 · Acuerdo con proveedor"


def test_finalizada_vuelve_a_su_estado_si_cambian_las_cantidades():
    # Llegó otra factura después de finalizar: la diferencia de cobro se muestra igual.
    assert comparar(200, [116], [116, 10], finalizada=True).estado == DISCREPANCIA
