from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .enums import EstadoVisita


class Visita(Base):
    __tablename__ = "visita"

    id_visita: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_camion: Mapped[int] = mapped_column(ForeignKey("camion.id_camion"), nullable=False)
    id_conductor: Mapped[int] = mapped_column(ForeignKey("conductor.id_conductor"), nullable=False)
    id_planta: Mapped[int] = mapped_column(ForeignKey("planta.id_planta"), nullable=False)
    fecha_hora_ingreso: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fecha_hora_salida: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    estado_visita: Mapped[EstadoVisita] = mapped_column(String(20), default=EstadoVisita.en_planta.value, nullable=False)
    motivo: Mapped[str | None] = mapped_column(String(200), nullable=True)
    observacion: Mapped[str | None] = mapped_column(Text, nullable=True)

    camion: Mapped["Camion"] = relationship(back_populates="visitas")
    conductor: Mapped["Conductor"] = relationship(back_populates="visitas")
    planta: Mapped["Planta"] = relationship(back_populates="visitas")
    movimientos: Mapped[list["MovimientoAcceso"]] = relationship(back_populates="visita")
    alertas: Mapped[list["Alerta"]] = relationship(back_populates="visita")
