from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Documento(Base):
    __tablename__ = "documentos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre_original: Mapped[str] = mapped_column(String(255))
    # Nombre con el que se guardó en data/archivos (único, para no pisar archivos con el mismo nombre)
    nombre_guardado: Mapped[str] = mapped_column(String(255), unique=True)
    tipo_contenido: Mapped[str] = mapped_column(String(100))
    tamano: Mapped[int] = mapped_column(Integer)

    tipo: Mapped[str] = mapped_column(String(50), index=True)
    confianza: Mapped[float] = mapped_column(Float)
    puntajes: Mapped[dict] = mapped_column(JSON)
    coincidencias: Mapped[dict] = mapped_column(JSON)
    texto: Mapped[str] = mapped_column(Text)
    # Mercancías encontradas: [{"descripcion": ..., "cantidad": ..., "total": ...}]
    items: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # Suma de las cantidades de los ítems (None si no se encontró la tabla)
    cantidad_total: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Suma de los valores totales de los ítems (solo facturas y órdenes de compra)
    valor_total: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Neto (o subtotal) impreso en el documento y si coincide con valor_total. Si no coincide
    # (o es None: no se encontró el neto) hay que revisar los valores a mano.
    neto_documento: Mapped[float | None] = mapped_column(Float, nullable=True)
    valores_coinciden: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    fecha_creacion: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
