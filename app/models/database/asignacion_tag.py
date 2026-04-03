from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class AsignacionTag(Base):
    __tablename__ = "asignacion_tag"

    id_asignacion: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_tag: Mapped[int] = mapped_column(ForeignKey("tag_rfid.id_tag"), nullable=False)
    id_camion: Mapped[int] = mapped_column(ForeignKey("camion.id_camion"), nullable=False)
    fecha_inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    fecha_fin: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    activa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    tag: Mapped["TagRFID"] = relationship(back_populates="asignaciones")
    camion: Mapped["Camion"] = relationship(back_populates="asignaciones_tag")
