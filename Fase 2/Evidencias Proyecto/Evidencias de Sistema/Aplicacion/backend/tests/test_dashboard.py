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


def test_guia_subida_antes_que_su_oc_se_vincula_al_subir_la_oc():
    from app.api.documentos import vincular_sueltos
    from app.db import SessionLocal
    from app.models import Documento

    orden = client.post("/api/dummies", params={"escenario": "pendiente"}).json()
    numero = orden["codigo"].removeprefix("OC-")
    with SessionLocal() as db:
        guia = Documento(nombre_original="guia.pdf", nombre_guardado="guia-suelta", tipo_contenido="application/pdf",
                         tamano=0, tipo="guia_despacho", numero="45892", confianza=1, puntajes={}, coincidencias={},
                         texto=f"Documento de referencia: Orden de Compra Folio: {numero}")
        db.add(guia)
        db.commit()
        vincular_sueltos(db, db.get(Documento, orden["id"]))
        assert db.get(Documento, guia.id).orden_id == orden["id"]
        db.delete(guia)
        db.commit()
    client.delete("/api/dummies")


def test_subir_de_nuevo_una_guia_sin_oc_desde_su_fila_la_vincula():
    from tests.test_api import imagen_guia_con_valores

    datos = imagen_guia_con_valores()
    guia = client.post("/api/documentos", files={"archivo": ("guia.png", datos, "image/png")}).json()
    assert guia["orden_id"] is None
    orden = client.post("/api/dummies", params={"escenario": "pendiente"}).json()

    r = client.post("/api/documentos", data={"orden_id": orden["id"]},
                    files={"archivo": ("guia.png", datos, "image/png")})
    assert r.status_code == 200
    assert r.json()["id"] == guia["id"] and r.json()["orden_id"] == orden["id"]
    # Ya vinculada, otra subida sí es un duplicado
    r = client.post("/api/documentos", files={"archivo": ("guia.png", datos, "image/png")})
    assert r.status_code == 409
    client.delete(f"/api/documentos/{guia['id']}")
    client.delete("/api/dummies")


def test_dummy_con_guia_de_baja_confianza_se_corrige_editando():
    client.post("/api/dummies", params={"escenario": "baja_confianza"})
    fila = client.get("/api/dashboard").json()[0]
    guia = fila["guias"][0]
    assert guia["confianza"] < 0.65 and guia["cantidades_editables"]
    assert fila["estado"] == "discrepancia"  # la guía trae una cantidad mal leída

    # Corregir la guía con las cantidades de la factura deja la OC conciliada
    cantidades = [i["cantidad"] for i in fila["facturas"][0]["items"]]
    assert client.put(f"/api/documentos/{guia['id']}/cantidades", json={"cantidades": cantidades}).status_code == 200
    assert client.get("/api/dashboard").json()[0]["estado"] == "ok"
    client.delete("/api/dummies")
