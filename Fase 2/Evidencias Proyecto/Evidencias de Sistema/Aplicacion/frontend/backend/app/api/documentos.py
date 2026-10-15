import re
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app import config
from app.classifier.clasificador import clasificar, codigo, normalizar
from app.classifier.palabras_clave import TIPOS_DOCUMENTO
from app.db import get_db
from app.extraccion.mercancias import extraer_items, montos_netos, verificar_valores
from app.models import Documento
from app.services.ocr import EXTENSIONES_SOPORTADAS, extraer

router = APIRouter(prefix="/api/documentos", tags=["documentos"])

# Solo en estos documentos se guarda el valor de cada producto (la guía de despacho no vende).
TIPOS_CON_VALORES = {"factura", "orden_compra"}


def a_dict(doc: Documento, incluir_texto: bool = True) -> dict:
    datos = {
        "id": doc.id,
        "archivo": doc.nombre_original,
        "tipo": doc.tipo,
        "nombre": TIPOS_DOCUMENTO.get(doc.tipo, {}).get("nombre", "Desconocido"),
        "numero": doc.numero,
        "codigo": codigo(doc.tipo, doc.numero),  # "OC-123", "G-123", "F-123"
        "confianza": doc.confianza,
        "puntajes": doc.puntajes,
        "coincidencias": doc.coincidencias,
        "tamano": doc.tamano,
        "fecha_creacion": doc.fecha_creacion.isoformat() if doc.fecha_creacion else None,
        "cantidad_total": doc.cantidad_total,
        "valor_total": doc.valor_total,
        "neto_documento": doc.neto_documento,
        "valores_coinciden": doc.valores_coinciden,
        "orden_id": doc.orden_id,
        "dummy": bool(doc.dummy),
        "url_archivo": f"/api/documentos/{doc.id}/archivo",
    }
    if incluir_texto:
        datos["texto"] = doc.texto
        datos["items"] = doc.items or []
    return datos


def obtener_o_404(db: Session, documento_id: int) -> Documento:
    doc = db.get(Documento, documento_id)
    if doc is None:
        raise HTTPException(404, "Documento no encontrado")
    return doc


# Tipos que se vinculan a una orden de compra (su fila en el dashboard).
TIPOS_VINCULABLES = {"guia_despacho", "factura"}

# Números de OC más cortos que esto no se buscan en el texto: "46" aparece en cualquier parte.
LARGO_MINIMO_NUMERO_OC = 4


def buscar_orden(db: Session, texto: str) -> Documento | None:
    """La orden de compra que el documento menciona por su número (en las referencias de una
    guía o factura: "Orden Compra N° 4511048747")."""
    texto = normalizar(texto)
    ordenes = db.scalars(select(Documento).where(Documento.tipo == "orden_compra", Documento.numero.is_not(None))
                         .order_by(Documento.id.desc()))
    for orden in ordenes:
        numero = orden.numero.lower()
        if len(numero) >= LARGO_MINIMO_NUMERO_OC and re.search(rf"(?<![\w-]){re.escape(numero)}(?![\w-])", texto):
            return orden
    return None


@router.post("")
async def analizar_documento(archivo: UploadFile, orden_id: int | None = Form(None), db: Session = Depends(get_db)):
    """Analiza y guarda un documento. Con `orden_id` (subido desde una fila del dashboard) debe ser
    una guía de despacho o una factura, y queda vinculado a esa orden de compra."""
    orden = obtener_o_404(db, orden_id) if orden_id is not None else None
    if orden is not None and orden.tipo != "orden_compra":
        raise HTTPException(400, "El documento indicado no es una orden de compra")

    extension = Path(archivo.filename or "").suffix.lower()
    if extension not in EXTENSIONES_SOPORTADAS:
        raise HTTPException(400, f"Formato no soportado. Usa: {', '.join(sorted(EXTENSIONES_SOPORTADAS))}")

    datos = await archivo.read()
    if len(datos) > config.MAX_FILE_SIZE:
        raise HTTPException(413, "El archivo supera el tamaño máximo permitido (20 MB)")

    try:
        # El OCR es lento y bloqueante: lo corremos fuera del event loop.
        extraccion = await run_in_threadpool(extraer, datos, extension)
    except Exception as e:
        raise HTTPException(422, f"No se pudo leer el documento: {e}")

    resultado = clasificar(extraccion.texto)
    if orden is not None and resultado.tipo not in TIPOS_VINCULABLES:
        nombre = TIPOS_DOCUMENTO.get(resultado.tipo, {}).get("nombre", "un documento desconocido")
        raise HTTPException(422, f"Se esperaba una guía de despacho o una factura, pero el documento es: {nombre}")
    if orden is None and resultado.tipo in TIPOS_VINCULABLES:
        orden = buscar_orden(db, extraccion.texto)
    items = extraer_items(extraccion.paginas)
    con_valores = resultado.tipo in TIPOS_CON_VALORES
    totales = [i.total for i in items if i.total is not None] if con_valores else []
    coinciden, neto = verificar_valores(items, montos_netos(extraccion.paginas)) if con_valores else (None, None)

    nombre_guardado = f"{uuid.uuid4().hex}{extension}"
    ruta = config.ARCHIVOS_DIR / nombre_guardado
    ruta.write_bytes(datos)

    doc = Documento(
        nombre_original=archivo.filename,
        nombre_guardado=nombre_guardado,
        tipo_contenido=archivo.content_type or "application/octet-stream",
        tamano=len(datos),
        tipo=resultado.tipo,
        numero=resultado.numero,
        confianza=resultado.confianza,
        puntajes=resultado.puntajes,
        coincidencias=resultado.coincidencias,
        texto=extraccion.texto,
        items=[
            {"descripcion": i.descripcion, "cantidad": i.cantidad, "total": i.total if con_valores else None}
            for i in items
        ],
        cantidad_total=sum(i.cantidad for i in items) if items else None,
        valor_total=sum(totales) if totales else None,
        neto_documento=neto,
        valores_coinciden=coinciden,
        orden_id=orden.id if orden else None,
    )
    try:
        db.add(doc)
        db.commit()
    except Exception:
        ruta.unlink(missing_ok=True)  # no dejar archivos huérfanos si falla la base
        raise
    db.refresh(doc)
    return a_dict(doc)


@router.get("")
def listar_documentos(tipo: str | None = None, db: Session = Depends(get_db)):
    consulta = select(Documento).order_by(Documento.fecha_creacion.desc(), Documento.id.desc())
    if tipo:
        consulta = consulta.where(Documento.tipo == tipo)
    return [a_dict(doc, incluir_texto=False) for doc in db.scalars(consulta)]


@router.get("/{documento_id}")
def obtener_documento(documento_id: int, db: Session = Depends(get_db)):
    return a_dict(obtener_o_404(db, documento_id))


@router.get("/{documento_id}/archivo")
def descargar_archivo(documento_id: int, db: Session = Depends(get_db)):
    doc = obtener_o_404(db, documento_id)
    ruta = config.ARCHIVOS_DIR / doc.nombre_guardado
    if not ruta.exists():
        raise HTTPException(404, "El archivo ya no existe en el servidor")
    # inline: el navegador muestra la imagen/PDF en vez de descargarlo
    return FileResponse(ruta, media_type=doc.tipo_contenido, filename=doc.nombre_original,
                        content_disposition_type="inline")


@router.delete("/{documento_id}", status_code=204)
def eliminar_documento(documento_id: int, db: Session = Depends(get_db)):
    doc = obtener_o_404(db, documento_id)
    (config.ARCHIVOS_DIR / doc.nombre_guardado).unlink(missing_ok=True)
    # Las guías y facturas de una OC eliminada quedan sin OC (siguen en el historial)
    db.execute(update(Documento).where(Documento.orden_id == doc.id).values(orden_id=None))
    db.delete(doc)
    db.commit()
