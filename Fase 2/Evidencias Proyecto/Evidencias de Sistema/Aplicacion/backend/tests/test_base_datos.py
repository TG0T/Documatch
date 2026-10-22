"""Restricciones del esquema (Base de Datos/schema.sql): duplicados y enlace OC - guía - factura."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.db import SessionLocal
from app.main import app

client = TestClient(app)


@pytest.fixture
def fila_ok():
    client.post("/api/dummies", params={"escenario": "ok"})
    yield client.get("/api/dashboard").json()[0]
    client.delete("/api/dummies")


def ejecutar(sql: str, **parametros):
    with SessionLocal() as db:
        resultado = db.execute(text(sql), parametros)
        db.commit()
        return resultado


def test_no_acepta_dos_documentos_del_mismo_tipo_y_numero(fila_ok):
    guia = fila_ok["guias"][0]
    with pytest.raises(IntegrityError, match="UNIQUE"):
        ejecutar("""INSERT INTO documentos (nombre_original, nombre_guardado, tipo_contenido, tamano, tipo, numero,
                                            confianza, texto)
                    SELECT nombre_original, 'copia', tipo_contenido, tamano, tipo, numero, confianza, texto
                    FROM documentos WHERE id = :id""", id=guia["id"])


def test_solo_se_enlaza_a_una_orden_de_compra(fila_ok):
    guia, factura = fila_ok["guias"][0], fila_ok["facturas"][0]
    with pytest.raises(IntegrityError, match="orden de compra"):
        ejecutar("UPDATE documentos SET orden_id = :guia WHERE id = :factura", guia=guia["id"], factura=factura["id"])
    with pytest.raises(IntegrityError, match="FOREIGN KEY|orden de compra"):
        ejecutar("UPDATE documentos SET orden_id = 999999 WHERE id = :id", id=factura["id"])


def test_borrar_la_orden_deja_sus_documentos_sin_orden(fila_ok):
    ids = [fila_ok["guias"][0]["id"], fila_ok["facturas"][0]["id"]]
    ejecutar("DELETE FROM documentos WHERE id = :id", id=fila_ok["orden"]["id"])
    for id_ in ids:  # siguen en el historial, sin OC
        assert ejecutar("SELECT orden_id FROM documentos WHERE id = :id", id=id_).one() == (None,)


def test_vista_de_conciliacion(fila_ok):
    fila = ejecutar("SELECT * FROM v_conciliacion WHERE orden_id = :id", id=fila_ok["orden"]["id"]).mappings().one()
    assert fila["orden"] == fila_ok["orden"]["codigo"]
    assert fila["guias"] == fila_ok["guias"][0]["codigo"]
    assert fila["facturas"] == fila_ok["facturas"][0]["codigo"]
    assert fila["pedido"] == fila["despachado"] == fila["facturado"] == fila_ok["pedido"]
