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
from datetime import datetime, timezone
from uuid import UUID

import httpx
import redis.asyncio as aioredis

from app.config import get_settings
from app.database import get_session_maker
from app.redis_client import user_notifications_channel
from app.services import audit_records, audit_service

logger = logging.getLogger(__name__)

# Actor de los eventos que origina el propio sistema, no una persona.
SYSTEM_ACTOR = "system:worker"
SYSTEM_ROLE = "SYSTEM"
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
    incident_id: str | None = None,
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
        "incident_id": incident_id,
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
    await audit_service.record(audit_records.build_entry(
        actor_email=SYSTEM_ACTOR,
        actor_role=SYSTEM_ROLE,
        method="DELETE",
        path=f"/worker/purge_audit_logs?filas={total}",
        route_template="/worker/purge_audit_logs",
        resource_type="audit_retention",
        status_code=200,
    ))

    return deleted


# ---------------------------------------------------------------------------
# Webhooks salientes (NEW-12)
# ---------------------------------------------------------------------------

async def _update_delivery(
    delivery_id: str,
    *,
    status: str,
    attempt: int,
    response_status: int | None = None,
    error: str | None = None,
) -> None:
    """Persiste el resultado de un intento de entrega (sesión propia).

    Se ejecuta en el worker, donde no hay ContextVar de tenant: el filtro de
    TRV-01 queda inactivo y la consulta por id es global, que es lo correcto
    para actualizar una entrega concreta ya identificada por su id.
    """
    from app.database import get_session_maker
    from app.models import Webhook, WebhookDelivery, WebhookDeliveryStatus

    now = datetime.now(timezone.utc)
    resolved = WebhookDeliveryStatus(status)

    async with get_session_maker()() as db:
        delivery = await db.get(WebhookDelivery, UUID(delivery_id))
        if delivery is None:
            logger.warning("Entrega de webhook %s no encontrada al actualizar", delivery_id)
            return

        delivery.status = resolved
        delivery.attempt_count = attempt
        delivery.response_status = response_status
        delivery.error = error
        if resolved is WebhookDeliveryStatus.SUCCESS:
            delivery.delivered_at = now

        webhook = await db.get(Webhook, delivery.webhook_id)
        if webhook is not None:
            webhook.last_status = resolved.value
            if resolved is WebhookDeliveryStatus.SUCCESS:
                webhook.last_triggered_at = now
                webhook.failure_count = 0
            else:
                webhook.failure_count = (webhook.failure_count or 0) + 1

        await db.commit()

        client_id = delivery.client_id
        event_type = delivery.event_type

    # Enviar datos de una empresa a un tercero es un evento de la plataforma
    # (TRV-07). Se registra aqui porque es el unico punto por el que pasan
    # todos los resultados de una entrega, con exito o sin el.
    #
    # La URL de destino no se guarda a proposito: la de un webhook entrante de
    # Slack lleva su propio secreto en la ruta, y la auditoria no es sitio para
    # un secreto. Queda el webhook afectado por su id.
    await audit_service.record(audit_records.build_entry(
        client_id=client_id,
        actor_email=SYSTEM_ACTOR,
        actor_role=SYSTEM_ROLE,
        method="POST",
        path=f"/worker/deliver_webhook?evento={event_type}&intento={attempt}",
        route_template="/worker/deliver_webhook",
        resource_type="webhook_delivery",
        resource_id=UUID(delivery_id),
        # Sin respuesta del destino (timeout o error de red) el resultado se
        # registra como 504: el acto fallo por el otro extremo, no aqui.
        status_code=response_status or 504,
    ))


async def deliver_webhook(
    ctx: dict,
    *,
    delivery_id: str,
    url: str,
    secret: str | None,
    payload: dict,
    event_type: str,
    payload_format: str = "JSON",
    message_template: str | None = None,
) -> None:
    """ARQ task: entrega un webhook por HTTP POST y persiste el resultado.

    `payload_format` decide el cuerpo enviado: `JSON` (esquema propio de
    CoreStream) o `SLACK` (mensaje `{"text": ...}` compatible con Incoming
    Webhooks). La firma HMAC se calcula sobre el cuerpo REAL enviado.

    Ante cualquier fallo (timeout, error de red, respuesta no-2xx) se relanza
    la excepción para que ARQ reintente según `max_tries`/`retry_delay` de
    WorkerSettings. El número de intento lo aporta ARQ en `ctx['job_try']`.
    """
    from app.services.webhook_service import build_slack_payload, compute_signature

    attempt = int(ctx.get("job_try") or 1)
    outgoing = (
        build_slack_payload(payload, message_template)
        if payload_format == "SLACK"
        else payload
    )
    body = json.dumps(outgoing, separators=(",", ":"), default=str).encode("utf-8")

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "CoreStream-Webhooks/1.0",
        "X-CoreStream-Event": event_type,
        "X-CoreStream-Delivery": str(delivery_id),
    }
    if secret:
        headers["X-CoreStream-Signature"] = compute_signature(secret, body)

    status_code: int | None = None
    error: str | None = None
    try:
        async with httpx.AsyncClient(timeout=settings.WEBHOOK_TIMEOUT_SECONDS) as client:
            response = await client.post(url, content=body, headers=headers)
        status_code = response.status_code
        if 200 <= status_code < 300:
            await _update_delivery(
                delivery_id, status="SUCCESS", attempt=attempt, response_status=status_code
            )
            logger.info(
                "Webhook entregado | delivery=%s | evento=%s | status=%d",
                delivery_id, event_type, status_code,
            )
            return
        error = f"HTTP {status_code}"
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"[:500]

    await _update_delivery(
        delivery_id,
        status="FAILED",
        attempt=attempt,
        response_status=status_code,
        error=error,
    )
    raise RuntimeError(f"Entrega de webhook {delivery_id} falló: {error}")
