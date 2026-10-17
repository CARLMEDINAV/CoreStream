"""Modelos de webhooks salientes (NEW-12).

Un Webhook representa una integración configurada por un ADMIN que recibe un
POST firmado cada vez que ocurre un evento clave del cliente (tenant) al que
pertenece. La entrega efectiva la realiza el worker de ARQ
(`app.worker.tasks.deliver_webhook`) con reintentos ante fallo.

Aislamiento multi-tenant (TRV-01): igual que el resto de tablas de negocio,
`Webhook` y `WebhookDelivery` heredan de TenantMixin, así que el filtro
automático de tenancy restringe cualquier consulta al cliente autenticado.
Un webhook de un cliente nunca puede ver ni disparar datos de otro.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any
from uuid import UUID as PyUUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.application import Application

from .base import Base, BaseEntity, TenantMixin


class WebhookEventType(str, Enum):
    """Eventos clave que un webhook puede suscribir.

    Los valores coinciden con los `TicketEventType` de negocio, normalizados
    a un conjunto estable y documentado (ver `webhook_service._TICKET_EVENT_MAP`).
    """

    TICKET_CREATED = "TICKET_CREATED"
    TICKET_ASSIGNED = "TICKET_ASSIGNED"
    STATUS_CHANGED = "STATUS_CHANGED"
    TICKET_REDIRECTED = "TICKET_REDIRECTED"
    TICKET_COMPLETED = "TICKET_COMPLETED"
    QUESTION_RAISED = "QUESTION_RAISED"
    QUESTION_RESOLVED = "QUESTION_RESOLVED"
    COMMENT = "COMMENT"
    SUBTASK_COMPLETED = "SUBTASK_COMPLETED"


class WebhookDeliveryStatus(str, Enum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class WebhookFormat(str, Enum):
    """Formato del cuerpo que recibe el destino.

    JSON  — payload propio de CoreStream (por defecto), pensado para
            integraciones que consumen su esquema completo.
    SLACK — cuerpo `{"text": ...}` compatible con los Incoming Webhooks de
            Slack, para apuntar la URL directamente a un canal sin intermediario.
    """

    JSON = "JSON"
    SLACK = "SLACK"


class Webhook(Base, BaseEntity, TenantMixin):
    """Integración saliente configurada por un ADMIN.

    `project_id` es opcional: cuando es NULL el webhook aplica a todos los
    proyectos del cliente. `event_types` es una lista de `WebhookEventType`;
    una lista vacía significa "todos los eventos".
    """

    __tablename__ = "webhooks"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str] = mapped_column(String(1024), nullable=False)
    # Se guarda sólo para firmar el payload (HMAC-SHA256). Nunca se devuelve
    # en las respuestas de lectura.
    secret: Mapped[str | None] = mapped_column(String(255), nullable=True)
    event_types: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    # Formato del cuerpo enviado al destino (ver WebhookFormat). Se guarda como
    # texto, igual que `last_status`, para no depender de un tipo ENUM de
    # PostgreSQL al añadir formatos nuevos.
    format: Mapped[str] = mapped_column(
        String(20), default=WebhookFormat.JSON.value, nullable=False
    )
    # Plantilla opcional del texto enviado cuando `format = SLACK`. Admite
    # variables entre llaves ({ticket}, {estado}, …); si está vacía se usa el
    # texto por defecto generado por `webhook_service.build_slack_payload`.
    message_template: Mapped[str | None] = mapped_column(String(2000), nullable=True)

    last_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    last_triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    project_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_by_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    project: Mapped["Application | None"] = relationship(lazy="raise_on_sql")
    deliveries: Mapped[list["WebhookDelivery"]] = relationship(
        lazy="raise_on_sql",
        back_populates="webhook",
        cascade="all, delete-orphan",
    )


class WebhookDelivery(Base, BaseEntity, TenantMixin):
    """Registro de cada intento de entrega (auditoría + reintentos)."""

    __tablename__ = "webhook_deliveries"

    webhook_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("webhooks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[WebhookDeliveryStatus] = mapped_column(
        SQLEnum(WebhookDeliveryStatus, name="webhook_delivery_status_enum"),
        default=WebhookDeliveryStatus.PENDING,
        nullable=False,
        index=True,
    )
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    response_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    webhook: Mapped["Webhook"] = relationship(lazy="raise_on_sql", back_populates="deliveries")
