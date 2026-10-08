"""
Catálogo de planes comerciales y políticas derivadas (TRV-02 / TRV-08).

Módulo deliberadamente puro: ni FastAPI, ni SQLAlchemy, ni base de datos. Es
solo la política, y por eso puede ser la dependencia común del middleware que
la aplica por petición y de los servicios de auditoría que la aplican sobre los
datos.

Antes la retención vivía en middleware/commercial.py y services/audit_service.py
importaba de allí: un servicio dependiendo de un middleware, dirección
equivocada. Al extraer la política, las dos capas dependen de esto y ninguna de
la otra.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Sequence
from uuid import UUID

# audit_log es CORE a propósito: TRV-08 hace que el plan gobierne la
# PROFUNDIDAD del historial, no el acceso a él. Un cliente Basico consulta su
# propia auditoría, acotada a su retención; lo que se reserva a Enterprise es
# la exportación para auditorías externas.
CORE_FEATURES = frozenset({
    "projects", "tickets", "documents", "team", "incidents", "meetings",
    "support", "notifications", "audit_log",
})
PREMIUM_FEATURES = frozenset({"analytics", "document_translation"})
ENTERPRISE_FEATURES = frozenset({"audit_export"})

# Acumulativos: cada plan incluye todo lo del anterior.
PLAN_FEATURES: dict[str, frozenset[str]] = {
    "Basico": CORE_FEATURES,
    "Pro": CORE_FEATURES | PREMIUM_FEATURES,
    "Enterprise": CORE_FEATURES | PREMIUM_FEATURES | ENTERPRISE_FEATURES,
}
ALL_FEATURES = CORE_FEATURES | PREMIUM_FEATURES | ENTERPRISE_FEATURES

# Retención del registro de auditoría en días, por plan (TRV-08).
AUDIT_RETENTION_DAYS: dict[str, int] = {
    "Basico": 30,
    "Pro": 180,
    "Enterprise": 730,
}

# Ante un plan desconocido o ausente se conserva lo mínimo, no lo máximo: un
# valor que no está en el catálogo no puede acogerse a una retención ampliada
# que nadie ha contratado.
DEFAULT_RETENTION_DAYS = min(AUDIT_RETENTION_DAYS.values())


def features_for(plan: str | None, *, is_active: bool = True) -> frozenset[str]:
    """Banderas habilitadas. Un cliente inactivo no tiene ninguna."""
    if not is_active:
        return frozenset()
    return PLAN_FEATURES.get(plan or "", frozenset())


def is_known_feature(feature_flag: str) -> bool:
    return feature_flag in ALL_FEATURES


def audit_retention_days(plan: str | None) -> int:
    return AUDIT_RETENTION_DAYS.get(plan or "", DEFAULT_RETENTION_DAYS)


def cutoff_for_days(days: int, *, now: datetime | None = None) -> datetime:
    """Instante de corte para una retención dada en días."""
    return (now or datetime.now(timezone.utc)) - timedelta(days=days)


def retention_cutoff(plan: str | None, *, now: datetime | None = None) -> datetime:
    """
    Instante a partir del cual una entrada sigue viva para ese plan.

    Punto único de este cálculo: lo usan la purga (para borrar lo anterior) y
    la consulta (para no mostrar más historial del contratado, incluso en la
    ventana entre que una entrada caduca y pasa el cron). Tenerlo duplicado
    permitiría que las dos reglas divergieran sin que nada lo detecte.
    """
    reference = now or datetime.now(timezone.utc)
    return reference - timedelta(days=audit_retention_days(plan))


def group_by_retention(
    clients: Sequence[tuple[UUID, str | None]],
) -> dict[int, list[UUID]]:
    """
    Agrupa los clientes por días de retención: {días: [client_id, ...]}.

    Se agrupa en vez de recorrer cliente a cliente porque lo que decide el
    corte es el plan, no la identidad: así el número de sentencias depende de
    los planes en uso (tres o menos) y no del número de tenants. Dos planes
    con la misma retención comparten grupo, y un plan desconocido cae en el
    grupo por defecto de forma natural.

    Devuelve ids y no nombres de plan a propósito: es la única forma de
    expresar el mismo corte en los dos almacenes. La tabla podría filtrar por
    `commercial_plan` con una subconsulta, pero los documentos de
    Elasticsearch solo llevan `client_id` — con una función por almacén, las
    dos políticas podrían divergir sin que nada lo detecte.
    """
    groups: dict[int, list[UUID]] = {}
    for client_id, plan in clients:
        groups.setdefault(audit_retention_days(plan), []).append(client_id)
    return groups
