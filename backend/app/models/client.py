from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.user import User

from .base import Base, BaseEntity


class Client(Base, BaseEntity):
    """
    Representa a una empresa cliente (tenant) dentro de CoreStream.

    Es la raíz de la jerarquía multi-tenant: todo dato de negocio
    (usuarios, aplicaciones, tickets, etc.) pertenece a un único Client.
    """

    __tablename__ = "clients"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    users: Mapped[list["User"]] = relationship(lazy="raise_on_sql", back_populates="client")