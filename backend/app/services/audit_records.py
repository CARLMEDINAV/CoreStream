"""
Forma de una entrada de auditoría: clasificación del resultado y conversión de
valores a primitivos.

Separado de la escritura y de la consulta a propósito: es la única parte del
dominio de auditoría que no toca ni base de datos ni HTTP, así que puede
probarse y reutilizarse sin montar ninguna de las dos.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from app.models import AuditOutcome

# Orden de columnas de la exportación. Es también el orden de las claves en la
# línea JSON, para que las dos vistas del mismo registro se lean igual.
ENTRY_FIELDS: tuple[str, ...] = (
    "occurred_at",
    "request_id",
    "actor_user_id",
    "actor_email",
    "actor_role",
    "method",
    "path",
    "route_template",
    "resource_type",
    "resource_id",
    "status_code",
    "outcome",
    "ip",
    "user_agent",
    "duration_ms",
)

_DENIED_STATUS = frozenset({401, 403, 429})


def outcome_for(status_code: int) -> str:
    """
    Resultado del evento. Un 403 y un 422 son ambos 4xx pero significan cosas
    distintas para un auditor: el primero es un intento de acceso sin permiso,
    el segundo una petición mal formada. Colapsarlos haría inútil el filtro.
    """
    if status_code < 400:
        return AuditOutcome.SUCCESS
    if status_code in _DENIED_STATUS:
        return AuditOutcome.DENIED
    if status_code < 500:
        return AuditOutcome.FAILED
    return AuditOutcome.ERROR


def to_primitive(value: Any) -> Any:
    """
    Convierte un valor de la entrada a algo serializable.

    Punto único de esta conversión: la usan la línea JSON y las filas de la
    exportación. Cuando estaban duplicadas, cada una trataba los UUID y las
    fechas con reglas ligeramente distintas.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, (int, str, bool)):
        return value
    return str(value)


def as_log_payload(entry: Mapping[str, Any]) -> dict[str, Any]:
    """
    Convierte la entrada a JSON para enviarla al motor de registros, omitiendo
    los nulos.

    Recorre las claves de la propia entrada y no ENTRY_FIELDS, para que incluya
    `client_id` —que la exportación omite pero el motor necesita para distinguir
    tenants— y para que un campo nuevo aparezca sin tocar ninguna lista.
    """
    return {
        key: converted
        for key, value in entry.items()
        if (converted := to_primitive(value)) is not None
    }


def as_row(entry: Any) -> list[str]:
    """
    Entrada como fila de exportación. A diferencia del log, los nulos sí ocupan
    su celda: si no, las columnas se desalinearían.

    Acepta tanto un modelo AuditLog como un mapping, para que exportar no
    dependa de haber pasado por el ORM.
    """
    getter = entry.get if isinstance(entry, Mapping) else lambda f: getattr(entry, f, None)
    return [
        "" if (converted := to_primitive(getter(field))) is None else str(converted)
        for field in ENTRY_FIELDS
    ]
