from __future__ import annotations

from uuid import UUID as PyUUID

from sqlalchemy import Boolean, ForeignKey, String, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.application import Application
    from app.models.document import Document
    from app.models.notification import Notification
    from app.models.role import Role
    from app.models.ticket import Ticket
    from app.models.ticket_event import TicketEvent
    from app.models.role import Role    

from .base import Base, BaseEntity


class User(Base, BaseEntity):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    specialty: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    preferences: Mapped[dict | None] = mapped_column(JSON, nullable=True, default=dict)

    role_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("roles.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    role: Mapped["Role"] = relationship(back_populates="users")

    assigned_tickets: Mapped[list["Ticket"]] = relationship(
        foreign_keys="Ticket.assignee_id",
        back_populates="assignee",
    )
    created_tickets: Mapped[list["Ticket"]] = relationship(
        foreign_keys="Ticket.created_by_id",
        back_populates="created_by",
    )
    owned_applications: Mapped[list["Application"]] = relationship(
        back_populates="owner"
    )
    events: Mapped[list["TicketEvent"]] = relationship(
        foreign_keys="TicketEvent.user_id",
        back_populates="user",
    )
    notifications: Mapped[list["Notification"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    uploaded_documents: Mapped[list["Document"]] = relationship(
        back_populates="uploaded_by"
    )
