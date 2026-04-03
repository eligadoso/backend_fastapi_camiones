from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .enums import EstadoAlerta, SeveridadAlerta


class Alerta(Base):
    __tablename__ = "alerta"

    id_alerta: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_visita: Mapped[int | None] = mapped_column(ForeignKey("visita.id_visita"), nullable=True)
    id_lectura: Mapped[int | None] = mapped_column(ForeignKey("lectura_rfid.id_lectura"), nullable=True)
    tipo_alerta: Mapped[str] = mapped_column(String(80), nullable=False)
    severidad: Mapped[SeveridadAlerta] = mapped_column(String(20), nullable=False)
    mensaje: Mapped[str] = mapped_column(Text, nullable=False)
    fecha_hora: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    estado_alerta: Mapped[EstadoAlerta] = mapped_column(String(20), default=EstadoAlerta.pendiente.value, nullable=False)
    id_usuario_atiende: Mapped[int | None] = mapped_column(ForeignKey("usuario.id_usuario"), nullable=True)
    fecha_atencion: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    visita: Mapped["Visita | None"] = relationship(back_populates="alertas")
    lectura: Mapped["LecturaRFID | None"] = relationship(back_populates="alertas")
    usuario_atiende: Mapped["Usuario | None"] = relationship(back_populates="alertas_atendidas")
