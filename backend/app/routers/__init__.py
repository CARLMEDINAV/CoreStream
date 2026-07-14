"""
Routers del módulo de CoreStream.

Este paquete contiene todos los routers para los endpoints REST de CoreStream.
"""

from . import (
    auth,
    auth_simple,
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
)

__all__ = [
    "auth",
    "auth_simple",
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
]
