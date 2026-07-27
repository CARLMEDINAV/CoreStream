"""
Routers del módulo de CoreStream.

Este paquete contiene todos los routers para los endpoints REST de CoreStream.
"""

from . import (
    auth,
    users,
    applications,
    epics,
    tickets,
    subtasks,
    analytics,
    documents,
    notifications,
    websocket,
    ticket_redirection,
    uploads,
    support_tickets,
    incidents,
    meetings,
)

__all__ = [
    "auth",
    "users",
    "applications",
    "epics",
    "tickets",
    "subtasks",
    "analytics",
    "documents",
    "notifications",
    "websocket",
    "ticket_redirection",
    "uploads",
    "support_tickets",
    "incidents",
    "meetings",
]
