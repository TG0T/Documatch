import io

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw, ImageFont

from app import config
from app.main import app

client = TestClient(app)


def imagen_guia() -> bytes:
    img = Image.new("RGB", (1600, 400), "white")
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype("arial.ttf", 40)
    for i, linea in enumerate(["GUIA DE DESPACHO N° 1203", "Transportista: Transportes Sur", "Patente: AB-CD-12"]):
        draw.text((50, 50 + i * 90), linea, fill="black", font=font)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_subir_listar_ver_y_eliminar():
    datos = imagen_guia()
    r = client.post("/api/documentos", files={"archivo": ("guia.png", datos, "image/png")})
    assert r.status_code == 200
    doc = r.json()
    assert doc["tipo"] == "guia_despacho"

    # Se guardó el archivo en disco
    guardados = list(config.ARCHIVOS_DIR.iterdir())
    assert len(guardados) == 1

    # Aparece en el listado (sin el texto completo)
    lista = client.get("/api/documentos").json()
    assert [d["id"] for d in lista] == [doc["id"]]
    assert "texto" not in lista[0]

    # Filtro por tipo
    assert client.get("/api/documentos", params={"tipo": "factura"}).json() == []

    # Se puede recuperar la imagen original
    r = client.get(doc["url_archivo"])
    assert r.status_code == 200
    assert r.content == datos

    # Eliminar borra el registro y el archivo
    assert client.delete(f"/api/documentos/{doc['id']}").status_code == 204
    assert client.get(f"/api/documentos/{doc['id']}").status_code == 404
    assert list(config.ARCHIVOS_DIR.iterdir()) == []


def imagen_factura() -> bytes:
    img = Image.new("RGB", (2000, 900), "white")
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype("arial.ttf", 30)
    columnas = [80, 300, 1000, 1200, 1450, 1720]
    filas = [
        ["FACTURA ELECTRÓNICA N° 4521"],
        ["Código", "Descripción", "Cantidad", "Unidad", "Precio Unit.", "Total"],
        ["A-100", "Tubo PVC 110 mm x 6 m", "12", "UN", "3.500", "42.000"],
        ["B-220", "Cemento especial 25 kg", "1.500", "KG", "120", "180.000"],
        ["", "", "", "", "Monto Neto", "222.000"],
        ["", "", "", "", "Total", "264.180"],
    ]
    for n, fila in enumerate(filas):
        for x, texto in zip(columnas, fila):
            draw.text((x, 60 + n * 70), texto, fill="black", font=font)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_extrae_cantidades_de_los_items():
    r = client.post("/api/documentos", files={"archivo": ("factura.png", imagen_factura(), "image/png")})
    assert r.status_code == 200
    doc = r.json()
    assert doc["tipo"] == "factura"
    assert [i["cantidad"] for i in doc["items"]] == [12, 1500]
    assert doc["items"][0]["descripcion"].startswith("Tubo PVC")
    assert doc["cantidad_total"] == 1512
    # Valor total de cada producto (columna "Total"), sin confundirlo con el precio unitario
    assert [i["total"] for i in doc["items"]] == [42000, 180000]
    assert doc["valor_total"] == 222000
    # La suma coincide con el "Monto Neto" impreso
    assert doc["neto_documento"] == 222000
    assert doc["valores_coinciden"] is True

    # El listado muestra los totales pero no el detalle
    fila = next(d for d in client.get("/api/documentos").json() if d["id"] == doc["id"])
    assert fila["cantidad_total"] == 1512
    assert fila["valor_total"] == 222000
    assert fila["valores_coinciden"] is True
    assert "items" not in fila
    client.delete(f"/api/documentos/{doc['id']}")


def imagen_guia_con_valores() -> bytes:
    img = Image.new("RGB", (2000, 700), "white")
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype("arial.ttf", 30)
    columnas = [80, 300, 1000, 1450]
    filas = [
        ["GUIA DE DESPACHO ELECTRONICA N° 1203"],
        ["Transportista: Transportes Sur   Patente: AB-CD-12"],
        ["Código", "Descripción", "Cantidad", "Valor"],
        ["A-100", "Pallet de madera", "10", "50.000"],
    ]
    for n, fila in enumerate(filas):
        for x, texto in zip(columnas, fila):
            draw.text((x, 60 + n * 70), texto, fill="black", font=font)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_guia_de_despacho_no_guarda_valores():
    r = client.post("/api/documentos", files={"archivo": ("guia.png", imagen_guia_con_valores(), "image/png")})
    doc = r.json()
    assert doc["tipo"] == "guia_despacho"
    # Las cantidades sí, los valores no (solo facturas y órdenes de compra)
    assert [i["cantidad"] for i in doc["items"]] == [10]
    assert [i["total"] for i in doc["items"]] == [None]
    assert doc["valor_total"] is None
    assert doc["valores_coinciden"] is None
    client.delete(f"/api/documentos/{doc['id']}")


def test_formato_no_soportado_no_guarda_nada():
    r = client.post("/api/documentos", files={"archivo": ("notas.txt", b"hola", "text/plain")})
    assert r.status_code == 400
    assert list(config.ARCHIVOS_DIR.iterdir()) == []


def test_no_acepta_el_mismo_archivo_dos_veces():
    datos = imagen_guia()
    doc = client.post("/api/documentos", files={"archivo": ("guia.png", datos, "image/png")}).json()
    r = client.post("/api/documentos", files={"archivo": ("copia.png", datos, "image/png")})
    assert r.status_code == 409
    assert f"documento #{doc['id']}" in r.json()["detail"]
    assert len(list(config.ARCHIVOS_DIR.iterdir())) == 1
    client.delete(f"/api/documentos/{doc['id']}")


def test_no_acepta_otro_archivo_del_mismo_documento():
    # La misma guía N° 1203 guardada con otra compresión: otro archivo, mismo documento
    datos = imagen_guia_con_valores()
    otro = io.BytesIO()
    Image.open(io.BytesIO(datos)).save(otro, format="PNG", compress_level=1)
    assert otro.getvalue() != datos
    doc = client.post("/api/documentos", files={"archivo": ("guia.png", datos, "image/png")}).json()
    r = client.post("/api/documentos", files={"archivo": ("foto.png", otro.getvalue(), "image/png")})
    assert r.status_code == 409
    assert "G-1203" in r.json()["detail"]
    assert len(list(config.ARCHIVOS_DIR.iterdir())) == 1
    client.delete(f"/api/documentos/{doc['id']}")


def guia_suelta(confianza: float, items: list[dict] | None) -> int:
    from app.db import SessionLocal
    from app.models import Documento

    with SessionLocal() as db:
        doc = Documento(nombre_original="guia.pdf", nombre_guardado=f"guia-{confianza}-{items is None}",
                        tipo_contenido="application/pdf", tamano=0, tipo="guia_despacho", numero=None,
                        confianza=confianza, puntajes={}, coincidencias={}, texto="", items=items,
                        cantidad_total=sum(i["cantidad"] for i in items) if items else None)
        db.add(doc)
        db.commit()
        return doc.id


def test_editar_cantidades_de_una_guia_con_poca_confianza():
    id_ = guia_suelta(0.5, [{"descripcion": "Taladro", "cantidad": 1, "total": None},
                            {"descripcion": "Esmeril", "cantidad": 7, "total": None}])
    assert client.get(f"/api/documentos/{id_}").json()["cantidades_editables"] is True

    r = client.put(f"/api/documentos/{id_}/cantidades", json={"cantidades": [14, 10]})
    assert r.status_code == 200
    doc = r.json()
    assert [i["cantidad"] for i in doc["items"]] == [14, 10]
    assert doc["items"][0]["descripcion"] == "Taladro"
    assert doc["cantidad_total"] == 24 and doc["cantidades_editadas"] is True

    # Tantas cantidades como ítems, y ninguna negativa
    assert client.put(f"/api/documentos/{id_}/cantidades", json={"cantidades": [1]}).status_code == 422
    assert client.put(f"/api/documentos/{id_}/cantidades", json={"cantidades": [1, -2]}).status_code == 422
    client.delete(f"/api/documentos/{id_}")


def test_guia_sin_tabla_de_items_recibe_el_total():
    id_ = guia_suelta(0.4, None)
    doc = client.put(f"/api/documentos/{id_}/cantidades", json={"cantidades": [129]}).json()
    assert doc["cantidad_total"] == 129 and len(doc["items"]) == 1
    client.delete(f"/api/documentos/{id_}")


def test_no_se_editan_guias_con_confianza_suficiente_ni_otros_documentos():
    id_ = guia_suelta(0.65, [{"descripcion": "Taladro", "cantidad": 1, "total": None}])
    assert client.get(f"/api/documentos/{id_}").json()["cantidades_editables"] is False
    assert client.put(f"/api/documentos/{id_}/cantidades", json={"cantidades": [2]}).status_code == 409
    client.delete(f"/api/documentos/{id_}")

    client.post("/api/dummies", params={"escenario": "ok"})
    factura = client.get("/api/dashboard").json()[0]["facturas"][0]
    assert factura["cantidades_editables"] is False
    assert client.put(f"/api/documentos/{factura['id']}/cantidades", json={"cantidades": [1]}).status_code == 409
    client.delete("/api/dummies")
