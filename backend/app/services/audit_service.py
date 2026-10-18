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
from typing import Any, AsyncIterator, Mapping, cast
from uuid import UUID

from sqlalchemy import CursorResult, delete, func, select, text, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, Client
from app.models.audit_log import PURGE_GUC
from app.plans import (
    DEFAULT_RETENTION_DAYS,
    cutoff_for_days,
    group_by_retention,
    retention_cutoff,
)
from app.schemas.audit import AuditFilters
from app.services.audit_sinks import get_audit_sink

logger = logging.getLogger("corestream.audit")

# Filas que se piden a la base por viaje al exportar. Ni tan pocas que el
# número de viajes domine el tiempo, ni tantas que el lote vuelva a ser
# el problema de memoria que se quería evitar.
EXPORT_BATCH_SIZE = 1000

# Tope de la lista de actores del visor. Los usuarios de una empresa son
# decenas, pero los intentos de acceso con correos inventados no tienen
# límite: sin tope, un barrido de mil emails llenaría el desplegable.
ACTOR_LIMIT = 200

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


def _filters(*, client_id: UUID, plan: str, filters: AuditFilters) -> list[Any]:
    """
    Traduce los criterios del visor a condiciones SQL.

    Único punto donde un filtro se vuelve SQL, y lo comparten la consulta
    paginada y la exportación: no pueden acotar de forma distinta.

    El cliente y el corte de retención se añaden siempre y no llegan en los
    filtros, porque no son criterios elegibles sino el límite de lo que ese
    plan concede ver.
    """
    conditions: list[Any] = [
        AuditLog.client_id == client_id,
        AuditLog.occurred_at >= retention_cutoff(plan),
    ]

    if filters.actor_email:
        conditions.append(AuditLog.actor_email.ilike(f"%{filters.actor_email}%"))
    if filters.actor_user_id:
        conditions.append(AuditLog.actor_user_id == filters.actor_user_id)
    if filters.resource_type:
        conditions.append(AuditLog.resource_type == filters.resource_type)
    if filters.resource_id:
        conditions.append(AuditLog.resource_id == filters.resource_id)
    if filters.outcome:
        conditions.append(AuditLog.outcome == filters.outcome)
    if filters.method:
        conditions.append(AuditLog.method == filters.method.upper())
    if filters.date_from:
        conditions.append(AuditLog.occurred_at >= filters.date_from)
    if filters.date_to:
        conditions.append(AuditLog.occurred_at <= filters.date_to)

    return conditions


async def iter_entries(
    db: AsyncSession,
    *,
    client_id: UUID,
    plan: str,
    filters: AuditFilters,
    batch_size: int = EXPORT_BATCH_SIZE,
) -> AsyncIterator[AuditLog]:
    """
    Recorre el historial exportable en lotes, sin cargarlo entero en memoria.

    Antes la exportación pedía las filas de una vez con un tope de 50.000.
    Un cliente Enterprise retiene 730 días y, auditando también las
    lecturas, los supera de sobra: el CSV salía truncado sin avisar de que
    faltaba el resto, que es lo peor que puede hacer un fichero destinado a
    una auditoría externa. Recorriendo por lotes, el coste en memoria deja de
    depender del tamaño del historial.

    Los lotes avanzan por clave —(occurred_at, id) menor que el último
    entregado— y no con OFFSET, por dos razones. El coste de OFFSET crece con
    la profundidad, porque Postgres descarta todas las filas anteriores en
    cada lote. Y la auditoría sigue escribiendo durante la exportación —la
    propia exportación se registra—, así que con OFFSET las filas nuevas
    desplazarían las páginas y el fichero podría repetir o perder entradas.

    El orden incluye el id porque dos entradas escritas en la misma
    transacción comparten `occurred_at`: sin un segundo criterio único, el
    avance por clave podría saltarse una.

    Tampoco se usa un cursor del servidor (`stream_scalars`): asyncpg lo
    implementa sobre sentencias preparadas y chocaba con las que la propia
    aplicación deja en la conexión del pool, lo que rompía la exportación
    justo en el caso normal de consultar el visor y exportar después.
    """
    conditions = _filters(client_id=client_id, plan=plan, filters=filters)
    cursor: tuple[datetime, UUID] | None = None

    while True:
        statement = select(AuditLog).where(*conditions)
        if cursor is not None:
            statement = statement.where(
                tuple_(AuditLog.occurred_at, AuditLog.id) < tuple_(*cursor)
            )

        rows = (
            await db.execute(
                statement
                .order_by(AuditLog.occurred_at.desc(), AuditLog.id.desc())
                .limit(batch_size)
            )
        ).scalars().all()

        for entry in rows:
            yield entry

        if len(rows) < batch_size:
            return

        cursor = (rows[-1].occurred_at, rows[-1].id)


async def query_entries(
    db: AsyncSession,
    *,
    client_id: UUID,
    plan: str,
    filters: AuditFilters,
    skip: int = 0,
    limit: int = 50,
) -> tuple[list[AuditLog], int]:
    """
    Consulta paginada acotada al cliente y a la profundidad de su plan.

    El límite de retención se aplica también en la lectura: entre la
    caducidad de una entrada y el paso del cron de purga hay una ventana en la
    que la fila existe todavía, y un cliente no debe ver más historial del
    que su plan le concede.
    """
    conditions = _filters(client_id=client_id, plan=plan, filters=filters)

    total = await db.scalar(
        select(func.count()).select_from(AuditLog).where(*conditions)
    ) or 0

    rows = (
        await db.execute(
            select(AuditLog)
            .where(*conditions)
            .order_by(AuditLog.occurred_at.desc(), AuditLog.id.desc())
            .offset(skip)
            .limit(limit)
        )
    ).scalars().all()

    return list(rows), total


async def filter_options(
    db: AsyncSession,
    *,
    client_id: UUID,
    plan: str,
    filters: AuditFilters,
    actor_limit: int = ACTOR_LIMIT,
) -> tuple[list[str], list[tuple[UUID | None, str]], bool]:
    """
    Valores presentes en el historial consultable: tipos de recurso y actores.

    Comparte las condiciones con la consulta y la exportación, así que las
    opciones que ofrece el visor son exactamente las que darían resultados:
    nunca aparece un valor fuera de la retención del plan ni de otro cliente.

    Devuelve también si la lista de actores se quedó corta. Se pide un
    elemento más que el tope para saberlo sin una segunda consulta de conteo.
    """
    conditions = _filters(client_id=client_id, plan=plan, filters=filters)

    resource_types = (
        await db.execute(
            select(AuditLog.resource_type)
            .where(*conditions, AuditLog.resource_type.is_not(None))
            .distinct()
            .order_by(AuditLog.resource_type)
        )
    ).scalars().all()

    rows = (
        await db.execute(
            select(AuditLog.actor_user_id, AuditLog.actor_email)
            .where(*conditions, AuditLog.actor_email.is_not(None))
            .distinct()
            .order_by(AuditLog.actor_email)
            .limit(actor_limit + 1)
        )
    ).all()

    truncated = len(rows) > actor_limit
    actors = [(row.actor_user_id, row.actor_email) for row in rows[:actor_limit]]

    return list(resource_types), actors, truncated
