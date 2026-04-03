from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .enums import EstadoGeneral


class Camion(Base):
    __tablename__ = "camion"

    id_camion: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    patente: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    id_empresa: Mapped[int] = mapped_column(ForeignKey("empresa_transporte.id_empresa"), nullable=False)
    marca: Mapped[str | None] = mapped_column(String(80), nullable=True)
    modelo: Mapped[str | None] = mapped_column(String(80), nullable=True)
    color: Mapped[str | None] = mapped_column(String(50), nullable=True)
    estado: Mapped[EstadoGeneral] = mapped_column(String(20), default=EstadoGeneral.activo.value, nullable=False)

    empresa: Mapped["EmpresaTransporte"] = relationship(back_populates="camiones")
    asignaciones_tag: Mapped[list["AsignacionTag"]] = relationship(back_populates="camion")
    visitas: Mapped[list["Visita"]] = relationship(back_populates="camion")
