from __future__ import annotations

from enum import Enum

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, BaseEntity
from .user import User


class UserRole(str, Enum):
    ADMIN = "ADMIN"
    TEAM_LEADER = "TEAM_LEADER"
    DEVELOPER = "DEVELOPER"
    # Solo lectura del registro de auditoría (TRV-07/TRV-08, "ADMIN / Auditor").
    # Existe para no tener que dar ADMIN a quien solo debe leer: un ADMIN puede
    # invitar usuarios, cambiar roles y resetear contraseñas, así que usarlo
    # para dar acceso de lectura daría al auditor poder sobre el sistema que
    # audita. AUDITOR no aparece en ningún otro require_role, así que todo lo
    # demás le queda denegado por omisión.
    AUDITOR = "AUDITOR"


class Role(Base, BaseEntity):
    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)

    users: Mapped[list["User"]] = relationship(lazy="raise_on_sql", back_populates="role")
 