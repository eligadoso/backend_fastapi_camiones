from __future__ import annotations

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class UsuarioRol(Base):
    __tablename__ = "usuario_rol"

    id_usuario: Mapped[int] = mapped_column(ForeignKey("usuario.id_usuario"), primary_key=True)
    id_rol: Mapped[int] = mapped_column(ForeignKey("rol.id_rol"), primary_key=True)

    usuario: Mapped["Usuario"] = relationship(back_populates="roles")
    rol: Mapped["Rol"] = relationship(back_populates="usuarios")
