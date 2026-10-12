from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID as PyUUID

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, String
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, BaseEntity, TenantMixin

if TYPE_CHECKING:
    from .incident import Incident
    from .ticket import Ticket
    from .user import User


class NotificationType(str, Enum):
    TICKET_ASSIGNED   = "TICKET_ASSIGNED"
    STATUS_CHANGED    = "STATUS_CHANGED"
    TICKET_REDIRECTED = "TICKET_REDIRECTED"
    TICKET_COMPLETED  = "TICKET_COMPLETED"
    QUESTION_RAISED   = "QUESTION_RAISED"
    INCIDENT_REPORTED = "INCIDENT_REPORTED"
    INCIDENT_ASSIGNED = "INCIDENT_ASSIGNED"
    SYSTEM            = "SYSTEM"


def validar_enlace(tipo, ticket_id, incident_id):
    if ticket_id is not None and incident_id is not None:
        raise ValueError("La notificación no puede enlazar dos recursos")
    if tipo in (NotificationType.INCIDENT_REPORTED, NotificationType.INCIDENT_ASSIGNED):
        if incident_id is None or ticket_id is not None:
            raise ValueError("La notificación de incidencia necesita solo incident_id")
    elif tipo != NotificationType.SYSTEM and (ticket_id is None or incident_id is not None):
        raise ValueError("La notificación de ticket necesita solo ticket_id")


class Notification(Base, BaseEntity, TenantMixin):
    __tablename__ = "notifications"
    __table_args__ = (CheckConstraint(
        "(type IN ('INCIDENT_REPORTED', 'INCIDENT_ASSIGNED') AND incident_id IS NOT NULL AND ticket_id IS NULL) OR "
        "(type IN ('TICKET_ASSIGNED', 'STATUS_CHANGED', 'TICKET_REDIRECTED', 'TICKET_COMPLETED', 'QUESTION_RAISED') "
        "AND ticket_id IS NOT NULL AND incident_id IS NULL) OR "
        "(type = 'SYSTEM' AND (ticket_id IS NULL OR incident_id IS NULL))",
        name="ck_notificacion_recurso",
    ),)

    user_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ticket_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tickets.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    incident_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(String(1000), nullable=False)
    type: Mapped[NotificationType] = mapped_column(
        SQLEnum(NotificationType, name="notification_type_enum"),
        nullable=False,
    )
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    user: Mapped["User"] = relationship(lazy="raise_on_sql", back_populates="notifications")  # type: ignore[name-defined]
    ticket: Mapped["Ticket | None"] = relationship(lazy="raise_on_sql")  # type: ignore[name-defined]
    incident: Mapped["Incident | None"] = relationship(lazy="raise_on_sql")  # type: ignore[name-defined]
