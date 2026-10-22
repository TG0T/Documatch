"""Dashboard: una fila por orden de compra con sus guías de despacho, facturas y estado."""
import random
import uuid

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.api.documentos import cantidades_editables
from app.classifier.clasificador import codigo
from app.db import get_db
from app.models import Documento
from app.seguimiento import Estado, comparar

router = APIRouter(prefix="/api", tags=["dashboard"])


def resumen(doc: Documento) -> dict:
    return {
        "id": doc.id,
        "tipo": doc.tipo,
        "codigo": codigo(doc.tipo, doc.numero),
        "archivo": doc.nombre_original,
        "cantidad_total": doc.cantidad_total,
        "valor_total": doc.valor_total,
        "items": doc.items or [],  # tal como los leyó el OCR (sin emparejar entre documentos)
        "confianza": doc.confianza,
        "cantidades_editables": cantidades_editables(doc),
        "cantidades_editadas": bool(doc.cantidades_editadas),
        "dummy": bool(doc.dummy),
        "url_archivo": None if doc.dummy else f"/api/documentos/{doc.id}/archivo",
    }


def suma(cantidades: list[float | None]) -> float | None:
    """Total de varias guías o facturas; None si no hay ninguna o alguna no se pudo leer."""
    return sum(cantidades) if cantidades and None not in cantidades else None


def vinculados_a(db: Session, ordenes: list[Documento]) -> list[Documento]:
    return db.scalars(select(Documento).where(Documento.orden_id.in_([o.id for o in ordenes]))
                      .order_by(Documento.id)).all()


def estado_de(orden: Documento, guias: list[Documento], facturas: list[Documento]) -> Estado:
    return comparar(orden.cantidad_total, [g.cantidad_total for g in guias], [f.cantidad_total for f in facturas],
                    finalizada=bool(orden.finalizada), motivo=orden.motivo_cierre)


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db)):
    ordenes = db.scalars(select(Documento).where(Documento.tipo == "orden_compra")
                         .order_by(Documento.fecha_creacion.desc(), Documento.id.desc())).all()
    vinculados = vinculados_a(db, ordenes)
    filas = []
    for orden in ordenes:
        guias = [d for d in vinculados if d.orden_id == orden.id and d.tipo == "guia_despacho"]
        facturas = [d for d in vinculados if d.orden_id == orden.id and d.tipo == "factura"]
        estado = estado_de(orden, guias, facturas)
        pedido, despachado = orden.cantidad_total, suma([g.cantidad_total for g in guias])
        filas.append({
            "orden": resumen(orden),
            "guias": [resumen(g) for g in guias],
            "facturas": [resumen(f) for f in facturas],
            "estado": estado.estado,
            "detalle": estado.detalle,
            "puede_finalizar": estado.puede_finalizar,
            "finalizada": bool(orden.finalizada),
            "pedido": pedido,
            "despachado": despachado,
            "facturado": suma([f.cantidad_total for f in facturas]),
            # Porcentaje de lo pedido que ya se despachó (tope 100); None si no hay con qué calcularlo
            "avance": min(round(100 * despachado / pedido), 100) if pedido and despachado is not None else None,
        })
    return filas


def orden_o_404(db: Session, orden_id: int) -> Documento:
    orden = db.get(Documento, orden_id)
    if orden is None or orden.tipo != "orden_compra":
        raise HTTPException(404, "Orden de compra no encontrada")
    return orden


@router.post("/ordenes/{orden_id}/finalizar", status_code=204)
def finalizar_orden(orden_id: int, motivo: str | None = Body(None, embed=True, max_length=255),
                    db: Session = Depends(get_db)):
    """Da por terminada una OC con despacho parcial (por ejemplo, por acuerdo con el proveedor).
    Solo si lo despachado ya se facturó completo: no sirve para ocultar una diferencia de cobro."""
    orden = orden_o_404(db, orden_id)
    vinculados = vinculados_a(db, [orden])
    estado = comparar(orden.cantidad_total,
                      [d.cantidad_total for d in vinculados if d.tipo == "guia_despacho"],
                      [d.cantidad_total for d in vinculados if d.tipo == "factura"])
    if not estado.puede_finalizar:
        raise HTTPException(409, "Solo se puede finalizar una orden con despacho parcial y facturada por lo recibido")
    orden.finalizada = True
    orden.motivo_cierre = (motivo or "").strip() or None
    db.commit()


@router.delete("/ordenes/{orden_id}/finalizar", status_code=204)
def reabrir_orden(orden_id: int, db: Session = Depends(get_db)):
    orden = orden_o_404(db, orden_id)
    orden.finalizada = False
    orden.motivo_cierre = None
    db.commit()


# --- Dummies: documentos de ejemplo para llenar el dashboard sin subir archivos ---

PRODUCTOS = [
    "Tubo PVC 110 mm x 6 m", "Cemento especial 25 kg", "Guantes de nitrilo (caja)", "Toner negro",
    "Pallet de madera", "Cable eléctrico 2,5 mm (rollo)", "Tornillo hexagonal 1/2\"", "Resma papel carta",
]

ESCENARIOS = {"ok", "parcial", "discrepancia", "pendiente", "baja_confianza"}


def numero_libre(db: Session, tipo: str, generar) -> str:
    """Un número al azar que no use otro documento del mismo tipo (la base no acepta duplicados)."""
    while True:
        numero = generar()
        if db.scalar(select(Documento.id).where(Documento.tipo == tipo, Documento.numero == numero)) is None:
            return numero


def crear_dummy(db: Session, tipo: str, generar_numero, items: list[dict], orden_id: int | None = None,
                confianza: float = 1.0) -> Documento:
    numero = numero_libre(db, tipo, generar_numero)
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
        confianza=confianza,
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


def numero_al_azar() -> str:
    return str(random.randint(1000, 99999))


def item(descripcion: str, cantidad: int, precio: int) -> dict:
    return {"descripcion": descripcion, "cantidad": cantidad, "total": cantidad * precio}


@router.post("/dummies", status_code=201)
def agregar_dummy(escenario: str, db: Session = Depends(get_db)):
    """Crea una OC de ejemplo con su guía y factura según el escenario: "ok" (todo coincide),
    "parcial" (se despachó menos), "discrepancia" (se facturó más), "pendiente" (solo la OC) o
    "baja_confianza" (guía leída con poca confianza y una cantidad mal leída, que se puede corregir)."""
    if escenario not in ESCENARIOS:
        raise HTTPException(400, f"Escenario no válido. Usa: {', '.join(sorted(ESCENARIOS))}")

    pedidos = [(p, random.randint(2, 50), random.randint(10, 500) * 100)
               for p in random.sample(PRODUCTOS, random.randint(1, 3))]
    orden = crear_dummy(db, "orden_compra", lambda: f"{random.randint(100, 999)}-{random.randint(10, 999)}-SE26",
                        [item(*p) for p in pedidos])

    if escenario != "pendiente":
        despachados = list(pedidos)
        if escenario == "parcial":  # el primer producto llega incompleto
            p, cantidad, precio = despachados[0]
            despachados[0] = (p, cantidad // 2, precio)
        leidos, confianza = list(despachados), 1.0
        if escenario == "baja_confianza":  # el OCR leyó un 0 de más en la primera cantidad
            p, cantidad, precio = leidos[0]
            leidos[0], confianza = (p, cantidad * 10, precio), round(random.uniform(0.40, 0.60), 2)
        crear_dummy(db, "guia_despacho", numero_al_azar, [item(*p) for p in leidos], orden.id, confianza)

        facturados = list(despachados)
        if escenario == "discrepancia":  # se factura una unidad más de lo recibido
            p, cantidad, precio = facturados[0]
            facturados[0] = (p, cantidad + 1, precio)
        crear_dummy(db, "factura", numero_al_azar, [item(*p) for p in facturados], orden.id)

    db.commit()
    return resumen(orden)


@router.delete("/dummies", status_code=204)
def eliminar_dummies(db: Session = Depends(get_db)):
    dummies = select(Documento.id).where(Documento.dummy.is_(True))
    # Las guías y facturas reales que estaban en una OC dummy quedan sin OC
    db.execute(update(Documento).where(Documento.orden_id.in_(dummies)).values(orden_id=None))
    db.execute(delete(Documento).where(Documento.dummy.is_(True)))
    db.commit()
