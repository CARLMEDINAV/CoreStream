"""
Filtro automático de multi-tenancy (TRV-01).

Inyecta `WHERE client_id = <tenant actual>` en cada SELECT sobre cualquier
modelo que herede de TenantMixin, sin tener que agregar el filtro a mano en
cada router. Se apoya en with_loader_criteria (SQLAlchemy 2.0), que aplica
el criterio a toda la jerarquía de clases mapeadas que comparten ese mixin.

Se registra UNA vez, explícitamente, en el arranque de la app (main.py) —
no al importar este módulo ni al importar database.py, siguiendo el mismo
criterio de "sin efectos secundarios ocultos" que ya usan ahí.
"""

from sqlalchemy import event
from sqlalchemy.orm import Session, with_loader_criteria

from app.context import current_client_id_ctx
from app.models.base import TenantMixin

_registered = False


def register_tenant_scope() -> None:
    global _registered
    if _registered:
        return

    @event.listens_for(Session, "do_orm_execute")
    def _apply_tenant_filter(execute_state):
        if not (execute_state.is_select or execute_state.is_update or execute_state.is_delete):
            return

        if execute_state.execution_options.get("skip_tenant_scope"):
            # Bypass explícito, no un descuido: lo usan chequeos que deben
            # ser globales entre tenants (ej. unicidad de email en
            # invitations.py — TRV-01 exige email único, no único por
            # cliente).
            return

        client_id = current_client_id_ctx.get()
        if client_id is None:
            return

        execute_state.statement = execute_state.statement.options(
            with_loader_criteria(
                TenantMixin,
                lambda cls: cls.client_id == client_id,
                include_aliases=True,
            )
        )

    _registered = True