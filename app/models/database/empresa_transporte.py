from __future__ import annotations

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .enums import EstadoGeneral


class EmpresaTransporte(Base):
    __tablename__ = "empresa_transporte"

    id_empresa: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    razon_social: Mapped[str] = mapped_column(String(150), nullable=False)
    rut: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    telefono: Mapped[str | None] = mapped_column(String(30), nullable=True)
    correo: Mapped[str | None] = mapped_column(String(150), nullable=True)
    estado: Mapped[EstadoGeneral] = mapped_column(String(20), default=EstadoGeneral.activo.value, nullable=False)

    camiones: Mapped[list["Camion"]] = relationship(back_populates="empresa")
