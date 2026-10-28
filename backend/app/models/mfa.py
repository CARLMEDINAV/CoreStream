"""
Modelos de apoyo a NEW-08: códigos de recuperación de 2FA e identidades SSO.

Ambas tablas llevan client_id (TenantMixin) por el mismo criterio de TRV-01:
toda tabla de negocio pertenece a un cliente.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID as PyUUID

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, BaseEntity, TenantMixin


class UserRecoveryCode(Base, BaseEntity, TenantMixin):
    """
    Código de recuperación de un solo uso para entrar si se pierde el
    dispositivo del TOTP. Solo se guarda un HMAC del código (con una clave que
    no está en la base de datos): un volcado de la tabla no permite reconstruirlos.
    """

    __tablename__ = "user_recovery_codes"

    user_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("user_id", "code_hash", name="uq_recovery_user_hash"),
    )


class UserIdentity(Base, BaseEntity, TenantMixin):
    """
    Vínculo entre un usuario de CoreStream y su cuenta en un proveedor SSO.

    Tras el primer login, el usuario se reconoce por (provider, subject), que es
    estable, y no por el correo, que el proveedor permite cambiar.
    """

    __tablename__ = "user_identities"

    user_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        UniqueConstraint("provider", "subject", name="uq_identity_provider_subject"),
        UniqueConstraint("user_id", "provider", name="uq_identity_user_provider"),
    )
