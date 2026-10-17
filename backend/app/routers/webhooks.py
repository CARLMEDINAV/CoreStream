"""Router de Webhooks salientes (NEW-12).

Sólo ADMIN gestiona integraciones salientes del cliente. Todas las rutas se
registran en main.py bajo `/api/webhooks` con `require_feature("webhooks")`,
así que un plan comercial sin esa bandera responde 403 aunque sea ADMIN.

El aislamiento por tenant lo garantiza TRV-01: cualquier consulta a `Webhook`
o `WebhookDelivery` queda restringida al cliente del usuario autenticado, de
modo que un ADMIN no puede leer ni modificar webhooks de otro cliente.
"""

from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware import get_current_user
from app.models import (
    Application,
    User,
    Webhook,
    WebhookDelivery,
    WebhookDeliveryStatus,
    WebhookFormat,
)
from app.schemas import (
    WebhookCreate,
    WebhookCreatedResponse,
    WebhookDeliveryResponse,
    WebhookEventTypeOption,
    WebhookResponse,
    WebhookSecretResponse,
    WebhookUpdate,
)
from app.services import webhook_service

router = APIRouter(tags=["Webhooks"])


def _serialize(webhook: Webhook) -> dict:
    return {
        "id": webhook.id,
        "name": webhook.name,
        "url": webhook.url,
        "event_types": list(webhook.event_types or []),
        "project_id": webhook.project_id,
        "is_active": webhook.is_active,
        "format": webhook.format,
        "has_secret": bool(webhook.secret),
        "last_status": webhook.last_status,
        "last_triggered_at": webhook.last_triggered_at,
        "failure_count": webhook.failure_count,
        "created_at": webhook.created_at,
        "updated_at": webhook.updated_at,
    }


async def _get_owned_project_or_400(
    db: AsyncSession, project_id: UUID
) -> Application:
    application = (
        await db.execute(select(Application).where(Application.id == project_id))
    ).scalar_one_or_none()
    if application is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Proyecto {project_id} no encontrado",
        )
    return application


async def _get_webhook_or_404(db: AsyncSession, webhook_id: UUID) -> Webhook:
    webhook = (
        await db.execute(select(Webhook).where(Webhook.id == webhook_id))
    ).scalar_one_or_none()
    if webhook is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Webhook {webhook_id} no encontrado",
        )
    return webhook


@router.get(
    "/event-types",
    response_model=List[WebhookEventTypeOption],
    summary="Listar tipos de evento suscribibles",
)
async def list_event_types(
    current_user: User = Depends(get_current_user),
) -> List[WebhookEventTypeOption]:
    return [WebhookEventTypeOption(**option) for option in webhook_service.available_event_types()]


@router.get(
    "/deliveries/{delivery_id}",
    response_model=WebhookDeliveryResponse,
    summary="Obtener una entrega concreta",
)
async def get_delivery(
    delivery_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WebhookDeliveryResponse:
    delivery = (
        await db.execute(select(WebhookDelivery).where(WebhookDelivery.id == delivery_id))
    ).scalar_one_or_none()
    if delivery is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entrega no encontrada")
    return WebhookDeliveryResponse.model_validate(delivery)


@router.post(
    "/deliveries/{delivery_id}/retry",
    response_model=WebhookDeliveryResponse,
    summary="Reintentar una entrega fallida",
)
async def retry_delivery(
    delivery_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WebhookDeliveryResponse:
    delivery = (
        await db.execute(select(WebhookDelivery).where(WebhookDelivery.id == delivery_id))
    ).scalar_one_or_none()
    if delivery is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entrega no encontrada")

    delivery.status = WebhookDeliveryStatus.PENDING
    delivery.error = None
    await db.commit()
    await db.refresh(delivery)

    await webhook_service.dispatch_now(db, delivery)
    return WebhookDeliveryResponse.model_validate(delivery)


@router.get(
    "/",
    response_model=List[WebhookResponse],
    summary="Listar webhooks del cliente",
)
async def list_webhooks(
    project_id: Optional[UUID] = Query(None, description="Filtrar por proyecto"),
    is_active: Optional[bool] = Query(None, description="Filtrar por estado"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[WebhookResponse]:
    stmt = select(Webhook).order_by(Webhook.created_at.desc())
    if project_id is not None:
        stmt = stmt.where(Webhook.project_id == project_id)
    if is_active is not None:
        stmt = stmt.where(Webhook.is_active.is_(is_active))

    rows = (await db.execute(stmt)).scalars().all()
    return [WebhookResponse(**_serialize(webhook)) for webhook in rows]


@router.post(
    "/",
    response_model=WebhookCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear un webhook",
)
async def create_webhook(
    payload: WebhookCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WebhookCreatedResponse:
    if payload.project_id is not None:
        await _get_owned_project_or_400(db, payload.project_id)

    secret = payload.secret or webhook_service.generate_secret()
    webhook = Webhook(
        name=payload.name,
        url=payload.url,
        secret=secret,
        event_types=payload.event_types,
        project_id=payload.project_id,
        is_active=payload.is_active,
        format=payload.format.value,
        created_by_id=current_user.id,
        client_id=current_user.client_id,
    )
    db.add(webhook)
    await db.commit()
    await db.refresh(webhook)

    return WebhookCreatedResponse(**_serialize(webhook), secret=secret)


@router.get(
    "/{webhook_id}",
    response_model=WebhookResponse,
    summary="Obtener un webhook",
)
async def get_webhook(
    webhook_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WebhookResponse:
    webhook = await _get_webhook_or_404(db, webhook_id)
    return WebhookResponse(**_serialize(webhook))


@router.put(
    "/{webhook_id}",
    response_model=WebhookResponse,
    summary="Actualizar un webhook",
)
async def update_webhook(
    webhook_id: UUID,
    payload: WebhookUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WebhookResponse:
    webhook = await _get_webhook_or_404(db, webhook_id)

    data = payload.model_dump(exclude_unset=True)
    if isinstance(data.get("format"), WebhookFormat):
        data["format"] = data["format"].value
    if "project_id" in data and data["project_id"] is not None:
        await _get_owned_project_or_400(db, data["project_id"])

    for field, value in data.items():
        setattr(webhook, field, value)

    await db.commit()
    await db.refresh(webhook)
    return WebhookResponse(**_serialize(webhook))


@router.delete(
    "/{webhook_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar un webhook",
)
async def delete_webhook(
    webhook_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    webhook = await _get_webhook_or_404(db, webhook_id)
    await db.delete(webhook)
    await db.commit()


@router.post(
    "/{webhook_id}/rotate-secret",
    response_model=WebhookSecretResponse,
    summary="Rotar el secreto de firma",
)
async def rotate_secret(
    webhook_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WebhookSecretResponse:
    webhook = await _get_webhook_or_404(db, webhook_id)
    webhook.secret = webhook_service.generate_secret()
    await db.commit()
    return WebhookSecretResponse(secret=webhook.secret)


@router.get(
    "/{webhook_id}/deliveries",
    response_model=List[WebhookDeliveryResponse],
    summary="Listar las últimas entregas de un webhook",
)
async def list_deliveries(
    webhook_id: UUID,
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[WebhookDeliveryResponse]:
    await _get_webhook_or_404(db, webhook_id)
    rows = (
        await db.execute(
            select(WebhookDelivery)
            .where(WebhookDelivery.webhook_id == webhook_id)
            .order_by(WebhookDelivery.created_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    return [WebhookDeliveryResponse.model_validate(row) for row in rows]


@router.post(
    "/{webhook_id}/test",
    response_model=WebhookDeliveryResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Enviar un evento de prueba",
)
async def send_test_event(
    webhook_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WebhookDeliveryResponse:
    webhook = await _get_webhook_or_404(db, webhook_id)

    payload = {
        "event": "PING",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "project": None,
        "ticket": None,
        "actor": {"id": str(current_user.id), "name": current_user.full_name},
        "data": {"message": "Evento de prueba enviado desde CoreStream"},
    }
    delivery = WebhookDelivery(
        webhook_id=webhook.id,
        event_type="PING",
        payload=payload,
        status=WebhookDeliveryStatus.PENDING,
        client_id=current_user.client_id,
    )
    db.add(delivery)
    await db.commit()
    await db.refresh(delivery)

    await webhook_service.enqueue_delivery(delivery, webhook)
    return WebhookDeliveryResponse.model_validate(delivery)
