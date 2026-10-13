"""Dashboard: una fila por orden de compra con sus guías de despacho, facturas y estado."""
import random
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.classifier.clasificador import codigo
from app.db import get_db
from app.models import Documento
from app.seguimiento import comparar

router = APIRouter(prefix="/api", tags=["dashboard"])


def resumen(doc: Documento) -> dict:
    return {
        "id": doc.id,
        "tipo": doc.tipo,
        "codigo": codigo(doc.tipo, doc.numero),
        "archivo": doc.nombre_original,
        "cantidad_total": doc.cantidad_total,
        "valor_total": doc.valor_total,
        "dummy": bool(doc.dummy),
        "url_archivo": None if doc.dummy else f"/api/documentos/{doc.id}/archivo",
    }


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db)):
    ordenes = db.scalars(select(Documento).where(Documento.tipo == "orden_compra")
                         .order_by(Documento.fecha_creacion.desc(), Documento.id.desc())).all()
    vinculados = db.scalars(select(Documento).where(Documento.orden_id.in_([o.id for o in ordenes]))
                            .order_by(Documento.id)).all()
    filas = []
    for orden in ordenes:
        guias = [d for d in vinculados if d.orden_id == orden.id and d.tipo == "guia_despacho"]
        facturas = [d for d in vinculados if d.orden_id == orden.id and d.tipo == "factura"]
        estado = comparar(orden.cantidad_total,
                          [g.cantidad_total for g in guias], [f.cantidad_total for f in facturas])
        filas.append({
            "orden": resumen(orden),
            "guias": [resumen(g) for g in guias],
            "facturas": [resumen(f) for f in facturas],
            "estado": estado.estado,
            "detalle": estado.detalle,
        })
    return filas


# --- Dummies: documentos de ejemplo para llenar el dashboard sin subir archivos ---

PRODUCTOS = [
    "Tubo PVC 110 mm x 6 m", "Cemento especial 25 kg", "Guantes de nitrilo (caja)", "Toner negro",
    "Pallet de madera", "Cable eléctrico 2,5 mm (rollo)", "Tornillo hexagonal 1/2\"", "Resma papel carta",
]

ESCENARIOS = {"ok", "parcial", "discrepancia", "pendiente"}


def crear_dummy(db: Session, tipo: str, numero: str, items: list[dict], orden_id: int | None = None) -> Documento:
    con_valores = tipo != "guia_despacho"
    items = [{**i, "total": i["total"] if con_valores else None} for i in items]
    valor = sum(i["total"] for i in items) if con_valores else None
    doc = Documento(
        nombre_original=f"dummy-{codigo(tipo, numero)}",
        nombre_guardado=f"dummy-{uuid.uuid4().hex}",
        tipo_contenido="text/plain",
        tamano=0,
        tipo=tipo,
        numero=numero,
        confianza=1.0,
        puntajes={},
        coincidencias={},
        texto="Documento de ejemplo creado desde el dashboard.",
        items=items,
        cantidad_total=sum(i["cantidad"] for i in items),
        valor_total=valor,
        neto_documento=valor,
        valores_coinciden=True if con_valores else None,
        orden_id=orden_id,
        dummy=True,
    )
    db.add(doc)
    db.flush()  # para tener el id de la OC antes de crear sus guías y facturas
    return doc


def item(descripcion: str, cantidad: int, precio: int) -> dict:
    return {"descripcion": descripcion, "cantidad": cantidad, "total": cantidad * precio}


@router.post("/dummies", status_code=201)
def agregar_dummy(escenario: str, db: Session = Depends(get_db)):
    """Crea una OC de ejemplo con su guía y factura según el escenario: "ok" (todo coincide),
    "parcial" (se despachó menos), "discrepancia" (se facturó más) o "pendiente" (solo la OC)."""
    if escenario not in ESCENARIOS:
        raise HTTPException(400, f"Escenario no válido. Usa: {', '.join(sorted(ESCENARIOS))}")

    pedidos = [(p, random.randint(2, 50), random.randint(10, 500) * 100)
               for p in random.sample(PRODUCTOS, random.randint(1, 3))]
    orden = crear_dummy(db, "orden_compra", f"{random.randint(100, 999)}-{random.randint(10, 999)}-SE26",
                        [item(*p) for p in pedidos])

    if escenario != "pendiente":
        despachados = list(pedidos)
        if escenario == "parcial":  # el primer producto llega incompleto
            p, cantidad, precio = despachados[0]
            despachados[0] = (p, cantidad // 2, precio)
        crear_dummy(db, "guia_despacho", str(random.randint(1000, 99999)), [item(*p) for p in despachados], orden.id)

        facturados = list(despachados)
        if escenario == "discrepancia":  # se factura una unidad más de lo recibido
            p, cantidad, precio = facturados[0]
            facturados[0] = (p, cantidad + 1, precio)
        crear_dummy(db, "factura", str(random.randint(1000, 99999)), [item(*p) for p in facturados], orden.id)

    db.commit()
    return resumen(orden)


@router.delete("/dummies", status_code=204)
def eliminar_dummies(db: Session = Depends(get_db)):
    dummies = select(Documento.id).where(Documento.dummy.is_(True))
    # Las guías y facturas reales que estaban en una OC dummy quedan sin OC
    db.execute(update(Documento).where(Documento.orden_id.in_(dummies)).values(orden_id=None))
    db.execute(delete(Documento).where(Documento.dummy.is_(True)))
    db.commit()
