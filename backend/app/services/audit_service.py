"""
Ciclo de vida del registro de auditoría: escritura, purga de retención y
consulta (TRV-07 / TRV-08).

La forma de la entrada vive en audit_records.py, los destinos en
audit_sinks.py y los formatos de exportación en audit_export.py. Aquí solo
queda lo que habla con la base de datos.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Mapping, cast
from uuid import UUID

from sqlalchemy import CursorResult, delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, Client
from app.models.audit_log import PURGE_GUC
from app.plans import (
    DEFAULT_RETENTION_DAYS,
    cutoff_for_days,
    group_by_retention,
    retention_cutoff,
)
from app.services.audit_sinks import get_audit_sink

logger = logging.getLogger("corestream.audit")

# Etiqueta del grupo de entradas sin tenant resuelto (un login fallido contra
# un email inexistente no pertenece a ningún cliente).
ORPHAN_GROUP = "sin_cliente"


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def record(entry: Mapping[str, Any]) -> None:
    """
    Deriva la entrada a todos los destinos configurados.

    Punto de entrada único del middleware: no sabe cuántos destinos hay ni
    cuáles son, solo que esto no propaga excepciones (ver CompositeSink).
    """
    await get_audit_sink().emit(entry)


async def _authorize_purge(db: AsyncSession) -> None:
    """
    Declara en la sesión la marca que el trigger de borrado exige.

    SET LOCAL vive solo hasta el final de la transacción actual, así que la
    autorización no se le queda pegada a la conexión cuando vuelve al pool —
    cualquier otra petición que la reutilice sigue sin poder borrar.

    En SQLite (tests unitarios) no hay GUC ni triggers: no hay nada que
    autorizar y el borrado funciona igual.
    """
    if db.bind is None or db.bind.dialect.name != "postgresql":
        return
    await db.execute(text(f"SET LOCAL {PURGE_GUC} = 'on'"))


async def _delete_where(db: AsyncSession, *conditions: Any) -> int:
    """Borra y devuelve el número de filas afectadas."""
    result = cast(CursorResult, await db.execute(delete(AuditLog).where(*conditions)))
    return result.rowcount or 0


async def retention_plan(db: AsyncSession) -> tuple[dict[int, list[UUID]], datetime]:
    """
    La política de retención vigente: {días: [client_id, ...]} y el instante
    de referencia.

    Se resuelve una sola vez y la comparten los dos almacenes. Si cada uno
    calculara la suya, podrían aplicar cortes distintos sobre el mismo evento
    —o quedarse uno sin actualizar— y la retención de TRV-08 dejaría de ser
    una política única.
    """
    clients = (await db.execute(select(Client.id, Client.commercial_plan))).all()
    return group_by_retention([(c.id, c.commercial_plan) for c in clients]), _now()


async def purge_expired(
    db: AsyncSession,
    groups: dict[int, list[UUID]] | None = None,
    now: datetime | None = None,
) -> dict[str, int]:
    """
    Borra de la tabla las entradas que superan la retención de cada grupo.

    Devuelve {etiqueta_de_grupo: filas_borradas}, donde la etiqueta es la
    retención en días ("30d", "180d"…) más `sin_cliente`.

    `groups` y `now` llegan de retention_plan() para compartirlos con los
    demás destinos; si no se pasan, se resuelven aquí (útil en tests).

    El borrado se agrupa por retención, no por cliente: una sentencia por
    grupo basta y el coste deja de crecer con el número de tenants. Lo que no
    se puede es agrupar por rango de fechas global ni particionar por fecha —
    solo se podría soltar una partición cuando hubiera caducado el cliente de
    mayor retención, y eso incumpliría la retención escalonada de TRV-08.
    """
    if groups is None:
        groups, now = await retention_plan(db)
    referencia = now or _now()

    await _authorize_purge(db)

    deleted: dict[str, int] = {}

    for dias, client_ids in groups.items():
        if not client_ids:
            continue
        removed = await _delete_where(
            db,
            AuditLog.client_id.in_(client_ids),
            AuditLog.occurred_at < cutoff_for_days(dias, now=referencia),
        )
        if removed:
            deleted[f"{dias}d"] = removed

    # Las entradas sin cliente caducan con la retención más corta: no
    # pertenecen a ningún tenant que pueda haber contratado conservarlas más.
    orphans = await _delete_where(
        db,
        AuditLog.client_id.is_(None),
        AuditLog.occurred_at < cutoff_for_days(DEFAULT_RETENTION_DAYS, now=referencia),
    )
    if orphans:
        deleted[ORPHAN_GROUP] = orphans

    await db.commit()
    return deleted


async def purge_sinks(groups: dict[int, list[UUID]], now: datetime) -> dict[str, int]:
    """
    Pide a cada destino que sepa caducar que aplique la misma política.

    Open/Closed: un destino nuevo que necesite retención propia solo tiene que
    implementar `purge`; este bucle no cambia. Los que no la implementan —la
    salida de logs, cuya rotación la gobierna Docker— se ignoran.

    Los fallos se registran y no propagan, igual que en la escritura: que el
    motor de búsqueda no esté disponible no debe dejar sin purgar la tabla.
    """
    purged: dict[str, int] = {}

    for sink in getattr(get_audit_sink(), "sinks", ()):
        purge = getattr(sink, "purge", None)
        if purge is None:
            continue
        try:
            purged[sink.name] = await purge(groups, now)
        except Exception:
            logger.exception("El destino '%s' no pudo aplicar la retención", sink.name)

    return purged


async def query_entries(
    db: AsyncSession,
    *,
    client_id: UUID,
    plan: str,
    actor_email: str | None = None,
    actor_user_id: UUID | None = None,
    resource_type: str | None = None,
    outcome: str | None = None,
    method: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    skip: int = 0,
    limit: int = 50,
) -> tuple[list[AuditLog], int]:
    """
    Consulta paginada acotada al cliente y a la profundidad de su plan.

    El límite de retención se aplica también en la lectura: entre la caducidad
    de una entrada y el paso del cron de purga hay una ventana en la que la
    fila existe todavía, y un cliente no debe ver más historial del que su
    plan le concede.
    """
    filters = [
        AuditLog.client_id == client_id,
        AuditLog.occurred_at >= retention_cutoff(plan),
    ]

    if actor_email:
        filters.append(AuditLog.actor_email.ilike(f"%{actor_email}%"))
    if actor_user_id:
        filters.append(AuditLog.actor_user_id == actor_user_id)
    if resource_type:
        filters.append(AuditLog.resource_type == resource_type)
    if outcome:
        filters.append(AuditLog.outcome == outcome)
    if method:
        filters.append(AuditLog.method == method.upper())
    if date_from:
        filters.append(AuditLog.occurred_at >= date_from)
    if date_to:
        filters.append(AuditLog.occurred_at <= date_to)

    total = await db.scalar(select(func.count()).select_from(AuditLog).where(*filters)) or 0

    rows = (
        await db.execute(
            select(AuditLog)
            .where(*filters)
            .order_by(AuditLog.occurred_at.desc())
            .offset(skip)
            .limit(limit)
        )
    ).scalars().all()

    return list(rows), total
