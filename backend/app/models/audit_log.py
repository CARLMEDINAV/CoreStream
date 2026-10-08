from __future__ import annotations

from datetime import datetime
from uuid import UUID as PyUUID
from uuid import uuid4

from sqlalchemy import DateTime, Integer, SmallInteger, String, func
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base

# Esquema propio, separado de `public` donde viven las tablas operativas. Es lo
# que hace literal el criterio 2 de TRV-07 ("no se almacenan en las tablas
# operativas") en vez de dejarlo en una interpretación: otro namespace, con
# permisos otorgables por separado, al que ningún servicio de dominio escribe.
AUDIT_SCHEMA = "audit"

# Marca de sesión que el trigger de borrado exige para dejar pasar un DELETE.
# La fija purge_expired() y nadie más.
PURGE_GUC = "corestream.audit_purge"


class AuditOutcome:
    SUCCESS = "SUCCESS"
    DENIED = "DENIED"
    FAILED = "FAILED"
    ERROR = "ERROR"


class AuditLog(Base):
    """
    Registro de auditoría de no repudio (TRV-07).

    No hereda TenantMixin a propósito: el filtro de tenant_scope.py se
    aplicaría a toda consulta, y tanto el escritor (que corre sin usuario
    resuelto en los login fallidos) como la purga de TRV-08 necesitan
    operar entre tenants. client_id va como columna plana y el filtrado
    por cliente es explícito en el router.

    Sin FK a clients: es un registro histórico, no datos relacionales — un
    ondelete RESTRICT impediría borrar un cliente por tener auditoría, y un
    CASCADE borraría justo lo que no debe desaparecer.

    actor_email y actor_role están desnormalizados: el registro debe seguir
    diciendo quién era y con qué rol actuaba aunque el usuario se borre o
    cambie de rol después.

    No hereda BaseEntity: aporta un updated_at con onupdate que nunca podría
    dispararse en una tabla append-only con UPDATE bloqueado por trigger.
    """

    __tablename__ = "audit_logs"
    __table_args__ = {"schema": AUDIT_SCHEMA}

    id: Mapped[PyUUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid4, nullable=False
    )

    client_id: Mapped[PyUUID | None] = mapped_column(
        PgUUID(as_uuid=True), nullable=True, index=True
    )

    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    actor_user_id: Mapped[PyUUID | None] = mapped_column(
        PgUUID(as_uuid=True), nullable=True, index=True
    )
    actor_email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    actor_role: Mapped[str | None] = mapped_column(String(50), nullable=True)

    method: Mapped[str] = mapped_column(String(10), nullable=False)
    path: Mapped[str] = mapped_column(String(512), nullable=False)
    route_template: Mapped[str | None] = mapped_column(String(512), nullable=True, index=True)

    resource_type: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    resource_id: Mapped[PyUUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)

    status_code: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    outcome: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

    ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
