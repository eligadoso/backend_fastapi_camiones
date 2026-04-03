from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .enums import TipoPunto


class PuntoControl(Base):
    __tablename__ = "punto_control"

    id_punto_control: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_zona: Mapped[int] = mapped_column(ForeignKey("zona.id_zona"), nullable=False)
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    tipo_punto: Mapped[TipoPunto] = mapped_column(String(30), nullable=False)
    id_esp32: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    zona: Mapped["Zona"] = relationship(back_populates="puntos_control")
    lecturas: Mapped[list["LecturaRFID"]] = relationship(back_populates="punto_control")
    movimientos: Mapped[list["MovimientoAcceso"]] = relationship(back_populates="punto_control")
