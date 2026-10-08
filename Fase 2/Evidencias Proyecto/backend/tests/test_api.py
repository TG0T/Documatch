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


def test_formato_no_soportado_no_guarda_nada():
    r = client.post("/api/documentos", files={"archivo": ("notas.txt", b"hola", "text/plain")})
    assert r.status_code == 400
    assert list(config.ARCHIVOS_DIR.iterdir()) == []
