from __future__ import annotations

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .enums import EstadoGeneral


class Planta(Base):
    __tablename__ = "planta"

    id_planta: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    direccion: Mapped[str | None] = mapped_column(String(250), nullable=True)
    estado: Mapped[EstadoGeneral] = mapped_column(String(20), default=EstadoGeneral.activo.value, nullable=False)

    zonas: Mapped[list["Zona"]] = relationship(back_populates="planta")
    visitas: Mapped[list["Visita"]] = relationship(back_populates="planta")
