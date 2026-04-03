from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .enums import EstadoTag


class TagRFID(Base):
    __tablename__ = "tag_rfid"

    id_tag: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    uid_tag: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    codigo_interno: Mapped[str | None] = mapped_column(String(100), nullable=True)
    estado: Mapped[EstadoTag] = mapped_column(String(20), default=EstadoTag.activo.value, nullable=False)
    fecha_alta: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    fecha_baja: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    asignaciones: Mapped[list["AsignacionTag"]] = relationship(back_populates="tag")
    lecturas: Mapped[list["LecturaRFID"]] = relationship(back_populates="tag")
