"""Servicio de webhooks salientes (NEW-12).

Responsabilidades:
  1. Registrar eventos de dominio y decidir qué webhooks del cliente aplican.
  2. Persistir un `WebhookDelivery` por webhook aplicable (mismo commit que el
     evento de negocio → nunca hay evento sin entrega registrada).
  3. Encolar la entrega en ARQ DESPUÉS del commit (`flush_pending_webhook_deliveries`).
  4. Firmar el payload con HMAC-SHA256 (`compute_signature`).

Aislamiento multi-tenant: además del filtro automático de TRV-01, la selección
de webhooks filtra `client_id` de forma explícita contra el cliente del ticket,
así que sólo se disparan webhooks del propio tenant aunque el ContextVar no
esté inicializado. El payload se construye a partir del ticket del propio
cliente; nunca se incluyen datos de otros tenants.
"""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import logging
import secrets
from datetime import datetime, timezone
from typing import Any, Iterable
from urllib.parse import urlparse
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import (
    Application,
    Epic,
    Ticket,
    TicketEventType,
    User,
    Webhook,
    WebhookDelivery,
    WebhookDeliveryStatus,
    WebhookEventType,
)
from app.services.notification_service import get_arq_pool

logger = logging.getLogger("corestream.webhooks")

# Clave dentro de db.info donde se acumulan las entregas pendientes hasta el
# commit (mismo patrón que _pending_notifications de notification_service).
PENDING_KEY = "_pending_webhook_deliveries"

# Traducción de los eventos de auditoría de tickets a los eventos públicos de
# webhook. Los que no aparecen aquí (TIMER_*, MOVED, UPDATED...) no disparan
# webhooks: no son "eventos clave" para integraciones externas.
_TICKET_EVENT_MAP: dict[str, str] = {
    TicketEventType.CREATED.value: WebhookEventType.TICKET_CREATED.value,
    TicketEventType.ASSIGNED.value: WebhookEventType.TICKET_ASSIGNED.value,
    TicketEventType.TICKET_ASSIGNED.value: WebhookEventType.TICKET_ASSIGNED.value,
    TicketEventType.STATUS_CHANGED.value: WebhookEventType.STATUS_CHANGED.value,
    TicketEventType.REDIRECTED.value: WebhookEventType.TICKET_REDIRECTED.value,
    TicketEventType.COMPLETED.value: WebhookEventType.TICKET_COMPLETED.value,
    TicketEventType.QUESTION_RAISED.value: WebhookEventType.QUESTION_RAISED.value,
    TicketEventType.QUESTION_RESOLVED.value: WebhookEventType.QUESTION_RESOLVED.value,
    TicketEventType.COMMENT.value: WebhookEventType.COMMENT.value,
    TicketEventType.SUBTASK_COMPLETED.value: WebhookEventType.SUBTASK_COMPLETED.value,
}

_EVENT_LABELS: dict[str, str] = {
    WebhookEventType.TICKET_CREATED.value: "Ticket creado",
    WebhookEventType.TICKET_ASSIGNED.value: "Ticket asignado",
    WebhookEventType.STATUS_CHANGED.value: "Cambio de estado",
    WebhookEventType.TICKET_REDIRECTED.value: "Ticket redirigido",
    WebhookEventType.TICKET_COMPLETED.value: "Ticket completado",
    WebhookEventType.QUESTION_RAISED.value: "Pregunta bloqueante",
    WebhookEventType.QUESTION_RESOLVED.value: "Pregunta resuelta",
    WebhookEventType.COMMENT.value: "Comentario",
    WebhookEventType.SUBTASK_COMPLETED.value: "Subtarea completada",
}


def available_event_types() -> list[dict[str, str]]:
    """Lista de eventos suscribibles para la UI (valor + etiqueta legible)."""
    return [
        {"value": event.value, "label": _EVENT_LABELS.get(event.value, event.value)}
        for event in WebhookEventType
    ]


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def generate_secret() -> str:
    """Genera un secreto de firma (256 bits) para un webhook."""
    return secrets.token_hex(32)


def compute_signature(secret: str, body: bytes) -> str:
    """Firma `body` con HMAC-SHA256 y lo devuelve como `sha256=<hex>`."""
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def validate_webhook_url(url: str) -> str:
    """Valida esquema y host de la URL destino.

    Rechaza esquemas distintos de http/https y, salvo que se habilite
    explícitamente con WEBHOOK_ALLOW_PRIVATE_URLS, hosts privados/loopback/
    link-local cuando son literales IP o nombres `localhost`. Es una defensa
    básica contra SSRF; la resolución DNS de nombres arbitrarios no se
    comprueba aquí (ver limitaciones en docs/NEW-12.md).
    """
    if not url or not url.strip():
        raise ValueError("La URL del webhook no puede estar vacía")

    value = url.strip()
    parsed = urlparse(value)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("La URL del webhook debe usar http o https")
    if not parsed.netloc or not parsed.hostname:
        raise ValueError("La URL del webhook debe incluir un host válido")

    settings = get_settings()
    if getattr(settings, "WEBHOOK_ALLOW_PRIVATE_URLS", False):
        return value

    host = parsed.hostname.lower()
    if host == "localhost" or host.endswith(".localhost"):
        raise ValueError("La URL del webhook no puede apuntar a localhost")

    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return value  # nombre de dominio: no se resuelve aquí

    if (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
        or address.is_multicast
        or address.is_unspecified
    ):
        raise ValueError("La URL del webhook no puede apuntar a una dirección privada o reservada")

    return value


def _as_value(event_type: TicketEventType | str) -> str:
    return event_type.value if hasattr(event_type, "value") else str(event_type)


def _safe_detail(detail: Any) -> dict[str, Any]:
    """Deja sólo primitivas del detalle del evento (nada de objetos ORM)."""
    if not isinstance(detail, dict):
        return {}
    safe: dict[str, Any] = {}
    for key, value in detail.items():
        if isinstance(value, (str, int, float, bool)) or value is None:
            safe[str(key)] = value
    return safe


# ---------------------------------------------------------------------------
# Registro de eventos
# ---------------------------------------------------------------------------

async def _matching_webhooks(
    db: AsyncSession, *, event_type: str, project_id: UUID | None, client_id: UUID
) -> list[Webhook]:
    """Webhooks activos del cliente indicado que aplican al evento dado.

    Se filtra `client_id` de forma explícita, además del filtro automático de
    TRV-01, para que el aislamiento multi-tenant no dependa de que el
    ContextVar esté inicializado (p. ej. en tests sin `register_tenant_scope`).
    El filtro por `event_types` se aplica en Python para no depender de
    operadores JSONB que difieren entre PostgreSQL y SQLite (tests unitarios).
    """
    stmt = select(Webhook).where(
        Webhook.is_active.is_(True),
        Webhook.client_id == client_id,
    )
    if project_id is not None:
        stmt = stmt.where(
            or_(Webhook.project_id.is_(None), Webhook.project_id == project_id)
        )
    else:
        stmt = stmt.where(Webhook.project_id.is_(None))

    rows = (await db.execute(stmt)).scalars().all()
    return [
        webhook
        for webhook in rows
        if not webhook.event_types or event_type in webhook.event_types
    ]


async def record_ticket_event(
    db: AsyncSession,
    *,
    ticket_id: UUID | str,
    event_type: TicketEventType | str,
    actor_id: UUID | str | None = None,
    detail: Any = None,
) -> list[WebhookDelivery]:
    """Registra un evento de ticket y crea las entregas de webhook aplicables.

    Debe llamarse ANTES del commit de la transacción de negocio; las entregas
    se encolan después con `flush_pending_webhook_deliveries`. Nunca lanza:
    un fallo al preparar webhooks no debe tumbar el cambio de negocio.
    """
    try:
        public_event = _TICKET_EVENT_MAP.get(_as_value(event_type))
        if public_event is None:
            return []

        row = (
            await db.execute(
                select(
                    Ticket.client_id,
                    Ticket.title,
                    Ticket.status,
                    Ticket.priority,
                    Ticket.epic_id,
                    Ticket.assignee_id,
                ).where(Ticket.id == ticket_id)
            )
        ).first()
        if row is None:
            return []

        project_id: UUID | None = None
        project_name: str | None = None
        if row.epic_id is not None:
            project_row = (
                await db.execute(
                    select(Epic.application_id, Application.name)
                    .join(Application, Application.id == Epic.application_id)
                    .where(Epic.id == row.epic_id)
                )
            ).first()
            if project_row is not None:
                project_id = project_row[0]
                project_name = project_row[1]

        webhooks = await _matching_webhooks(
            db,
            event_type=public_event,
            project_id=project_id,
            client_id=row.client_id,
        )
        if not webhooks:
            return []

        actor_name: str | None = None
        if actor_id is not None:
            actor_name = (
                await db.execute(select(User.full_name).where(User.id == actor_id))
            ).scalar_one_or_none()

        now = datetime.now(timezone.utc)
        payload: dict[str, Any] = {
            "event": public_event,
            "occurred_at": now.isoformat(),
            "project": (
                {"id": str(project_id), "name": project_name}
                if project_id is not None
                else None
            ),
            "ticket": {
                "id": str(ticket_id),
                "title": row.title,
                "status": _as_value(row.status),
                "priority": _as_value(row.priority),
                "assignee_id": str(row.assignee_id) if row.assignee_id else None,
                "epic_id": str(row.epic_id) if row.epic_id else None,
            },
            "actor": (
                {"id": str(actor_id), "name": actor_name}
                if actor_id is not None
                else None
            ),
            "data": _safe_detail(detail),
        }

        deliveries: list[tuple[WebhookDelivery, Webhook]] = []
        for webhook in webhooks:
            delivery = WebhookDelivery(
                webhook_id=webhook.id,
                event_type=public_event,
                payload=payload,
                status=WebhookDeliveryStatus.PENDING,
                client_id=row.client_id,
            )
            db.add(delivery)
            deliveries.append((delivery, webhook))

        db.info.setdefault(PENDING_KEY, []).extend(deliveries)
        return [delivery for delivery, _ in deliveries]
    except Exception:  # pragma: no cover - defensivo
        logger.exception("No se pudieron preparar webhooks para el evento %s", event_type)
        return []


# ---------------------------------------------------------------------------
# Entrega (post-commit)
# ---------------------------------------------------------------------------

async def enqueue_delivery(delivery: WebhookDelivery, webhook: Webhook) -> bool:
    """Encola la entrega de un webhook ya persistido. Fallos silenciosos."""
    pool = get_arq_pool()
    if pool is None:
        logger.warning(
            "ARQ pool no inicializado; entrega de webhook %s omitida", delivery.id
        )
        return False
    try:
        await pool.enqueue_job(
            "deliver_webhook",
            delivery_id=str(delivery.id),
            url=webhook.url,
            secret=webhook.secret,
            payload=delivery.payload,
            event_type=delivery.event_type,
        )
        return True
    except Exception as exc:
        logger.error("Error al encolar entrega de webhook %s: %s", delivery.id, exc)
        return False


async def flush_pending_webhook_deliveries(db: AsyncSession) -> None:
    """Encola las entregas acumuladas. Llamar DESPUÉS de db.commit()."""
    pending: Iterable[tuple[WebhookDelivery, Webhook]] = db.info.pop(PENDING_KEY, [])
    for delivery, webhook in pending:
        await enqueue_delivery(delivery, webhook)


async def dispatch_now(db: AsyncSession, delivery: WebhookDelivery) -> bool:
    """Encola una entrega ya persistida localizando su webhook (tenant-scoped)."""
    webhook = await db.get(Webhook, delivery.webhook_id)
    if webhook is None:
        return False
    return await enqueue_delivery(delivery, webhook)
