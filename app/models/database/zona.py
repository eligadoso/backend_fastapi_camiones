from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .enums import TipoZona


class Zona(Base):
    __tablename__ = "zona"

    id_zona: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_planta: Mapped[int] = mapped_column(ForeignKey("planta.id_planta"), nullable=False)
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    tipo_zona: Mapped[TipoZona] = mapped_column(String(30), nullable=False)

    planta: Mapped["Planta"] = relationship(back_populates="zonas")
    puntos_control: Mapped[list["PuntoControl"]] = relationship(back_populates="zona")
