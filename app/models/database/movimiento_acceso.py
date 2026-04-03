from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .enums import TipoMovimiento


class MovimientoAcceso(Base):
    __tablename__ = "movimiento_acceso"
    __table_args__ = (UniqueConstraint("id_lectura", name="uq_movimiento_lectura"),)

    id_movimiento: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_visita: Mapped[int] = mapped_column(ForeignKey("visita.id_visita"), nullable=False)
    id_lectura: Mapped[int] = mapped_column(ForeignKey("lectura_rfid.id_lectura"), nullable=False)
    tipo_movimiento: Mapped[TipoMovimiento] = mapped_column(String(20), nullable=False)
    fecha_hora_movimiento: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    id_punto_control: Mapped[int] = mapped_column(ForeignKey("punto_control.id_punto_control"), nullable=False)
    validado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    observacion: Mapped[str | None] = mapped_column(Text, nullable=True)

    visita: Mapped["Visita"] = relationship(back_populates="movimientos")
    lectura: Mapped["LecturaRFID"] = relationship(back_populates="movimiento")
    punto_control: Mapped["PuntoControl"] = relationship(back_populates="movimientos")
