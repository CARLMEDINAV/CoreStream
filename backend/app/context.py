"""
ContextVar para exponer el tenant (client_id) del usuario autenticado
a lo largo de un mismo request, sin tener que pasarlo a mano por cada
función/servicio. Se setea en get_current_user (middleware/auth.py) y
lo va a consumir el filtro automático de tenancy .
"""

from contextvars import ContextVar
from typing import Any
from uuid import UUID

current_client_id_ctx: ContextVar[UUID | None] = ContextVar(
    "current_client_id", default=None
)

# El valor es un dict MUTABLE, no los datos directamente: AuditMiddleware lo
# siembra antes de call_next y get_current_user lo rellena ya dentro del
# handler. Starlette ejecuta el app interno en otra task, así que una
# reasignación de ContextVar hecha abajo no sube al middleware — mutar el
# mismo objeto sí se ve desde ambos lados.
audit_ctx: ContextVar[dict[str, Any] | None] = ContextVar("audit", default=None)


def set_audit_actor(
    *, user_id: UUID, email: str, role: str, client_id: UUID | None = None
) -> None:
    bucket = audit_ctx.get()
    if bucket is not None:
        bucket["actor_user_id"] = user_id
        bucket["actor_email"] = email
        bucket["actor_role"] = role
        if client_id is not None:
            bucket["client_id"] = client_id


def set_audit_subject(email: str) -> None:
    """Identidad intentada en una acción sin actor autenticado (login fallido)."""
    bucket = audit_ctx.get()
    if bucket is not None and not bucket.get("actor_email"):
        bucket["actor_email"] = email


def defer_audit() -> None:
    """
    Declara que el acto lo registra el propio handler, no el middleware.

    Lo necesita una respuesta que se envía por trozos: el middleware escribe
    la entrada en cuanto el handler devuelve la respuesta, cuando el cuerpo
    todavía no ha salido, así que registraría un 200 aunque el volcado se
    corte a mitad. En una auditoría eso es afirmar que una extracción
    terminó bien sin saberlo.

    Quien difiere el registro se obliga a hacerlo: si el handler no lo
    escribe, el acto no queda en ninguna parte.
    """
    bucket = audit_ctx.get()
    if bucket is not None:
        bucket["deferred"] = True


def set_audit_resource(resource_type: str, resource_id: UUID | str | None = None) -> None:
    """
    El id se descarta si no es un UUID: la columna lo es, y un valor inválido
    haría fallar la escritura de la entrada entera. Mejor perder el id del
    recurso que perder el registro del acto.
    """
    bucket = audit_ctx.get()
    if bucket is None:
        return

    bucket["resource_type"] = resource_type
    if resource_id is None:
        return
    try:
        bucket["resource_id"] = (
            resource_id if isinstance(resource_id, UUID) else UUID(str(resource_id))
        )
    except (ValueError, TypeError):
        pass


def get_audit_bucket() -> dict[str, Any] | None:
    return audit_ctx.get()
