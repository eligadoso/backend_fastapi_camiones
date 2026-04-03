from __future__ import annotations

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .enums import EstadoGeneral


class Conductor(Base):
    __tablename__ = "conductor"

    id_conductor: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rut: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    apellido: Mapped[str] = mapped_column(String(100), nullable=False)
    telefono: Mapped[str | None] = mapped_column(String(30), nullable=True)
    licencia: Mapped[str | None] = mapped_column(String(50), nullable=True)
    estado: Mapped[EstadoGeneral] = mapped_column(String(20), default=EstadoGeneral.activo.value, nullable=False)

    visitas: Mapped[list["Visita"]] = relationship(back_populates="conductor")
