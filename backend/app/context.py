"""
ContextVar para exponer el tenant (client_id) del usuario autenticado
a lo largo de un mismo request, sin tener que pasarlo a mano por cada
función/servicio. Se setea en get_current_user (middleware/auth.py) y
lo va a consumir el filtro automático de tenancy .
"""

from contextvars import ContextVar
from uuid import UUID

current_client_id_ctx: ContextVar[UUID | None] = ContextVar(
    "current_client_id", default=None
)