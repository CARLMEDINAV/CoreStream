"""Esquemas de validación para webhooks salientes (NEW-12)."""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.webhook import WebhookFormat


def _clean_event_types(values: list[str] | None) -> list[str]:
    if not values:
        return []
    cleaned: list[str] = []
    for value in values:
        name = str(value).strip().upper()
        if name and name not in cleaned:
            cleaned.append(name)
    return cleaned


class WebhookCreate(BaseModel):
    """Datos para crear un webhook. `secret` es opcional (se genera si falta)."""

    name: str = Field(..., max_length=255)
    url: str = Field(..., max_length=1024)
    event_types: list[str] = Field(default_factory=list)
    project_id: Optional[UUID] = None
    is_active: bool = True
    format: WebhookFormat = WebhookFormat.JSON
    message_template: Optional[str] = Field(None, max_length=2000)
    secret: Optional[str] = Field(None, max_length=255)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("El nombre del webhook no puede estar vacío")
        return v.strip()

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        from app.services.webhook_service import validate_webhook_url

        return validate_webhook_url(v)

    @field_validator("event_types")
    @classmethod
    def validate_event_types(cls, v: list[str]) -> list[str]:
        return _clean_event_types(v)


class WebhookUpdate(BaseModel):
    """Actualización parcial. `event_types`/`project_id` se pueden limpiar."""

    name: Optional[str] = Field(None, max_length=255)
    url: Optional[str] = Field(None, max_length=1024)
    event_types: Optional[list[str]] = None
    project_id: Optional[UUID] = None
    is_active: Optional[bool] = None
    format: Optional[WebhookFormat] = None
    message_template: Optional[str] = Field(None, max_length=2000)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.strip():
            raise ValueError("El nombre del webhook no puede estar vacío")
        return v.strip() if v else v

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        from app.services.webhook_service import validate_webhook_url

        return validate_webhook_url(v)

    @field_validator("event_types")
    @classmethod
    def validate_event_types(cls, v: Optional[list[str]]) -> Optional[list[str]]:
        return None if v is None else _clean_event_types(v)


class WebhookResponse(BaseModel):
    """Vista de un webhook. Nunca incluye el `secret`."""

    id: UUID
    name: str
    url: str
    event_types: list[str]
    project_id: Optional[UUID] = None
    is_active: bool
    format: WebhookFormat = WebhookFormat.JSON
    message_template: Optional[str] = None
    has_secret: bool = False
    last_status: Optional[str] = None
    last_triggered_at: Optional[datetime] = None
    failure_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WebhookCreatedResponse(WebhookResponse):
    """Respuesta de creación/rotación: el `secret` se muestra UNA sola vez."""

    secret: Optional[str] = None


class WebhookDeliveryResponse(BaseModel):
    id: UUID
    webhook_id: UUID
    event_type: str
    status: str
    attempt_count: int
    response_status: Optional[int] = None
    error: Optional[str] = None
    delivered_at: Optional[datetime] = None
    created_at: datetime
    payload: dict[str, Any]

    model_config = {"from_attributes": True}


class WebhookSecretResponse(BaseModel):
    secret: str


class WebhookEventTypeOption(BaseModel):
    value: str
    label: str
