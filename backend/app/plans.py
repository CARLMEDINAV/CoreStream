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

import os
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
#
# Los valores llegan del entorno, no están fijados aquí. Cuánto tiempo se
# conserva la auditoría de un cliente no es una decisión técnica: es parte de
# lo que se le vende, y puede estar condicionada por obligaciones legales de
# conservación. Con variables de entorno la fija quien define los planes y se
# cambia sin desplegar — que además es lo que hace "configurable por tier
# comercial" inobjetable frente al criterio de TRV-08.
#
# Los números de abajo son el valor por defecto si no se declara nada, no una
# decisión tomada: ver .env.example.
_FALLBACK_RETENTION = {"Basico": 30, "Pro": 180, "Enterprise": 730}


def _dias_desde_entorno(plan: str) -> int:
    crudo = os.environ.get(f"AUDIT_RETENTION_DAYS_{plan.upper()}", "").strip()
    if not crudo:
        return _FALLBACK_RETENTION[plan]
    try:
        dias = int(crudo)
    except ValueError:
        raise ValueError(
            f"AUDIT_RETENTION_DAYS_{plan.upper()} debe ser un número de días, "
            f"no {crudo!r}"
        ) from None
    if dias < 1:
        raise ValueError(
            f"AUDIT_RETENTION_DAYS_{plan.upper()} debe ser al menos 1 día, no {dias}"
        )
    return dias


AUDIT_RETENTION_DAYS: dict[str, int] = {
    plan: _dias_desde_entorno(plan) for plan in _FALLBACK_RETENTION
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
