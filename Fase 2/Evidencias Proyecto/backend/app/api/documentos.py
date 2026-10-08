import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import config
from app.classifier.clasificador import clasificar
from app.classifier.palabras_clave import TIPOS_DOCUMENTO
from app.db import get_db
from app.models import Documento
from app.services.ocr import EXTENSIONES_SOPORTADAS, extraer_texto

router = APIRouter(prefix="/api/documentos", tags=["documentos"])


def a_dict(doc: Documento, incluir_texto: bool = True) -> dict:
    datos = {
        "id": doc.id,
        "archivo": doc.nombre_original,
        "tipo": doc.tipo,
        "nombre": TIPOS_DOCUMENTO.get(doc.tipo, {}).get("nombre", "Desconocido"),
        "confianza": doc.confianza,
        "puntajes": doc.puntajes,
        "coincidencias": doc.coincidencias,
        "tamano": doc.tamano,
        "fecha_creacion": doc.fecha_creacion.isoformat() if doc.fecha_creacion else None,
        "url_archivo": f"/api/documentos/{doc.id}/archivo",
    }
    if incluir_texto:
        datos["texto"] = doc.texto
    return datos


def obtener_o_404(db: Session, documento_id: int) -> Documento:
    doc = db.get(Documento, documento_id)
    if doc is None:
        raise HTTPException(404, "Documento no encontrado")
    return doc


@router.post("")
async def analizar_documento(archivo: UploadFile, db: Session = Depends(get_db)):
    extension = Path(archivo.filename or "").suffix.lower()
    if extension not in EXTENSIONES_SOPORTADAS:
        raise HTTPException(400, f"Formato no soportado. Usa: {', '.join(sorted(EXTENSIONES_SOPORTADAS))}")

    datos = await archivo.read()
    if len(datos) > config.MAX_FILE_SIZE:
        raise HTTPException(413, "El archivo supera el tamaño máximo permitido (20 MB)")

    try:
        # El OCR es lento y bloqueante: lo corremos fuera del event loop.
        texto = await run_in_threadpool(extraer_texto, datos, extension)
    except Exception as e:
        raise HTTPException(422, f"No se pudo leer el documento: {e}")

    resultado = clasificar(texto)

    nombre_guardado = f"{uuid.uuid4().hex}{extension}"
    ruta = config.ARCHIVOS_DIR / nombre_guardado
    ruta.write_bytes(datos)

    doc = Documento(
        nombre_original=archivo.filename,
        nombre_guardado=nombre_guardado,
        tipo_contenido=archivo.content_type or "application/octet-stream",
        tamano=len(datos),
        tipo=resultado.tipo,
        confianza=resultado.confianza,
        puntajes=resultado.puntajes,
        coincidencias=resultado.coincidencias,
        texto=texto,
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
    db.delete(doc)
    db.commit()
