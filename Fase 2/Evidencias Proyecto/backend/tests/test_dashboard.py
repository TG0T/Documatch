from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def estados():
    return sorted(fila["estado"] for fila in client.get("/api/dashboard").json())


def test_dummies_llenan_el_dashboard_y_se_borran():
    for escenario in ("ok", "parcial", "discrepancia", "pendiente"):
        assert client.post("/api/dummies", params={"escenario": escenario}).status_code == 201
    assert estados() == ["discrepancia", "ok", "parcial", "pendiente"]

    fila = next(f for f in client.get("/api/dashboard").json() if f["estado"] == "ok")
    assert fila["orden"]["codigo"].startswith("OC-")
    assert [g["codigo"][:2] for g in fila["guias"]] == ["G-"]
    assert [f["codigo"][:2] for f in fila["facturas"]] == ["F-"]
    # Los dummies no tienen archivo
    assert fila["orden"]["url_archivo"] is None

    assert client.delete("/api/dummies").status_code == 204
    assert client.get("/api/dashboard").json() == []
    assert client.get("/api/documentos").json() == []


def test_escenario_invalido():
    assert client.post("/api/dummies", params={"escenario": "otro"}).status_code == 400


def test_subir_a_una_fila_que_no_es_orden_de_compra():
    client.post("/api/dummies", params={"escenario": "ok"})
    guia = client.get("/api/dashboard").json()[0]["guias"][0]
    r = client.post("/api/documentos", data={"orden_id": guia["id"]},
                    files={"archivo": ("guia.png", b"x", "image/png")})
    assert r.status_code == 400
    client.delete("/api/dummies")


def test_guia_que_menciona_la_oc_se_vincula_sola():
    from app.api.documentos import buscar_orden
    from app.db import SessionLocal

    orden = client.post("/api/dummies", params={"escenario": "pendiente"}).json()
    numero = orden["codigo"].removeprefix("OC-")
    with SessionLocal() as db:
        assert buscar_orden(db, f"Referencias:\n+ Orden Compra N° {numero} del 2026-09-26").id == orden["id"]
        # Que el número aparezca dentro de otro más largo no cuenta
        assert buscar_orden(db, f"Folio 9{numero}") is None
    client.delete("/api/dummies")


def test_cantidades_y_avance_de_cada_fila():
    for escenario in ("ok", "parcial", "pendiente"):
        client.post("/api/dummies", params={"escenario": escenario})
    filas = {f["estado"]: f for f in client.get("/api/dashboard").json()}

    ok = filas["ok"]
    assert ok["pedido"] == ok["despachado"] == ok["facturado"]
    assert ok["avance"] == 100
    assert ok["orden"]["items"] and ok["guias"][0]["items"]

    parcial = filas["parcial"]
    assert parcial["despachado"] < parcial["pedido"]
    assert parcial["avance"] == round(100 * parcial["despachado"] / parcial["pedido"])

    pendiente = filas["pendiente"]
    assert pendiente["despachado"] is None and pendiente["facturado"] is None
    assert pendiente["avance"] is None
    client.delete("/api/dummies")


def test_finalizar_y_reabrir_un_despacho_parcial():
    client.post("/api/dummies", params={"escenario": "parcial"})
    client.post("/api/dummies", params={"escenario": "ok"})
    filas = {f["estado"]: f for f in client.get("/api/dashboard").json()}
    parcial, ok = filas["parcial"], filas["ok"]
    assert parcial["puede_finalizar"] and not ok["puede_finalizar"]

    # Una OC que no es parcial no se puede finalizar
    assert client.post(f"/api/ordenes/{ok['orden']['id']}/finalizar").status_code == 409

    id_ = parcial["orden"]["id"]
    r = client.post(f"/api/ordenes/{id_}/finalizar", json={"motivo": "Acuerdo con proveedor"})
    assert r.status_code == 204
    fila = next(f for f in client.get("/api/dashboard").json() if f["orden"]["id"] == id_)
    assert fila["estado"] == "finalizada" and fila["finalizada"]
    assert fila["detalle"].endswith("Acuerdo con proveedor")

    assert client.delete(f"/api/ordenes/{id_}/finalizar").status_code == 204
    fila = next(f for f in client.get("/api/dashboard").json() if f["orden"]["id"] == id_)
    assert fila["estado"] == "parcial" and not fila["finalizada"]

    # Sin motivo también se puede
    assert client.post(f"/api/ordenes/{id_}/finalizar").status_code == 204
    client.delete("/api/dummies")
