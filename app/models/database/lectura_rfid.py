from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .enums import ResultadoLectura


class LecturaRFID(Base):
    __tablename__ = "lectura_rfid"

    id_lectura: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_tag: Mapped[int] = mapped_column(ForeignKey("tag_rfid.id_tag"), nullable=False)
    id_punto_control: Mapped[int] = mapped_column(ForeignKey("punto_control.id_punto_control"), nullable=False)
    fecha_hora_lectura: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resultado: Mapped[ResultadoLectura] = mapped_column(String(20), nullable=False)
    detalle: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    tag: Mapped["TagRFID"] = relationship(back_populates="lecturas")
    punto_control: Mapped["PuntoControl"] = relationship(back_populates="lecturas")
    movimiento: Mapped["MovimientoAcceso | None"] = relationship(back_populates="lectura", uselist=False)
    alertas: Mapped[list["Alerta"]] = relationship(back_populates="lectura")
