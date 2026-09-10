# Esquemas de validación para operaciones relacionadas con notificaciones
# Las notificaciones informan a los usuarios sobre cambios relevantes en el sistema

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, field_validator


class NotificationResponse(BaseModel):
    id: UUID
    user_id: UUID
    title: str
    message: str
    type: str
    is_read: bool
    ticket_id: Optional[UUID] = None
    incident_id: Optional[UUID] = None
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("type")
    @classmethod
    def validate_notification_type(cls, v: str) -> str:
        valid_types = {
            "TICKET_ASSIGNED",
            "STATUS_CHANGED",
            "TICKET_REDIRECTED",
            "TICKET_COMPLETED",
            "QUESTION_RAISED",
            "INCIDENT_REPORTED",
            "INCIDENT_ASSIGNED",
            "SYSTEM",
        }
        if v.upper() not in valid_types:
            raise ValueError(f"El tipo de notificación debe ser uno de: {', '.join(valid_types)}")
        return v.upper()
class NotificationMarkRead(BaseModel):
    """
    Esquema para marcar múltiples notificaciones como leídas.
    Permite actualizaciones eficientes en lote.
    
    Atributos:
        notification_ids: Lista de UUIDs de notificaciones a marcar como leídas
    """
    notification_ids: list[UUID]

    @field_validator("notification_ids")
    @classmethod
    def validate_notification_ids_not_empty(cls, v: list[UUID]) -> list[UUID]:
        """
        Valida que la lista de IDs de notificaciones no esté vacía.
        
        Args:
            v: Lista de IDs a validar
            
        Returns:
            La lista validada
            
        Raises:
            ValueError: Si la lista está vacía
        """
        if not v or len(v) == 0:
            raise ValueError("Debe proporcionar al menos una notificación para marcar como leída")
        return v
