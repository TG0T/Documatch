from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, Integer, String, Text, func
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

    fecha_creacion: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
