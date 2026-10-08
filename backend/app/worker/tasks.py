"""
ARQ worker tasks para el sistema de notificaciones de CoreStream.

Flujo:
  HTTP handler
      └─► notification_service.enqueue_notification()   [fire-and-forget]
                  └─► ARQ Redis queue
                              └─► deliver_notification()  [este archivo]
                                      ├─► redis.publish("corestream:user:{id}:notifications", …)
                                      └─► retry automático (max_tries=3, backoff=5 s)

El DB save ocurre ANTES de encolar (en notification_service.create_notification,
dentro de la sesión del caller) para mantener atomicidad con el ticket.
Este task solo hace la entrega en tiempo real vía Redis pub/sub.
"""

from __future__ import annotations

import json
import logging

import redis.asyncio as aioredis

from app.config import get_settings
from app.database import get_session_maker
from app.models import AuditOutcome
from app.redis_client import user_notifications_channel
from app.services import audit_service

logger = logging.getLogger(__name__)
settings = get_settings()


async def deliver_notification(
    ctx: dict,
    *,
    user_id: str,
    notification_id: str,
    title: str,
    message: str,
    notification_type: str,
    ticket_id: str | None = None,
    created_at: str,
) -> None:
    """
    ARQ task: publica la notificación al canal Redis correcto para
    que el WebSocket la reenvíe al cliente en tiempo real.

    El canal `corestream:user:{user_id}:notifications` es el mismo al que
    `websocket.py` está suscrito, cerrando el circuito.

    Parámetros se pasan como keyword-only para claridad y para que ARQ
    los serialice correctamente en Redis.
    """
    redis: aioredis.Redis = ctx["redis"]

    # Publicar solo el contenido plano de la notificación.
    # websocket.py lo envolverá en {"type": "notification", "data": <este payload>}
    # antes de enviarlo al cliente WebSocket.
    payload = json.dumps({
        "id": notification_id,
        "type": notification_type,
        "title": title,
        "message": message,
        "ticket_id": ticket_id,
        "is_read": False,
        "created_at": created_at,
    })

    channel = user_notifications_channel(user_id)
    subscribers = await redis.publish(channel, payload)
    logger.info(
        "Notificación entregada | canal=%s | tipo=%s | suscriptores=%d",
        channel, notification_type, subscribers,
    )


async def purge_audit_logs(ctx: dict) -> dict[str, int]:
    """
    Cron de retención escalonada por plan comercial (TRV-08).

    La purga se audita a sí misma: sin este registro, la única operación que
    borra entradas del log de auditoría sería la única que no deja rastro.
    """
    async with get_session_maker()() as db:
        # La política se resuelve UNA vez y la comparten los dos almacenes: si
        # cada uno calculara la suya, el mismo evento podría caducar en la
        # tabla y sobrevivir en el motor de búsqueda (o al revés).
        groups, now = await audit_service.retention_plan(db)
        deleted = await audit_service.purge_expired(db, groups, now)

    # Los índices de Elasticsearch son por día y mezclan tenants, así que el
    # motor necesita su propio borrado por grupo para no conservar eventos de
    # un plan corto durante la retención de un plan largo.
    purged = await audit_service.purge_sinks(groups, now)

    total = sum(deleted.values())
    logger.info(
        "Purga de auditoría | tabla: %s (%d filas) | destinos: %s",
        ", ".join(f"{k}={v}" for k, v in sorted(deleted.items())) or "nada",
        total,
        ", ".join(f"{k}={v}" for k, v in sorted(purged.items())) or "nada",
    )

    # El desglose por grupo de retención va en la ruta del evento: es lo que
    # permite comprobar después qué política se aplicó y a cuántas filas.
    await audit_service.record({
        "client_id": None,
        "actor_email": "system:worker",
        "actor_role": "SYSTEM",
        "method": "DELETE",
        "path": f"/worker/purge_audit_logs?filas={total}",
        "route_template": "/worker/purge_audit_logs",
        "resource_type": "audit_retention",
        "status_code": 200,
        "outcome": AuditOutcome.SUCCESS,
        "duration_ms": None,
    })

    return deleted
