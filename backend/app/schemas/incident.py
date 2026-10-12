from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.incident import AffectedEnvironment, IncidentSeverity, IncidentStatus


class IncidentBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    categoria: str = Field(default="general", min_length=1, max_length=50)
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=10_000)
    severity: IncidentSeverity = Field(default=IncidentSeverity.P3)
    affected_environment: AffectedEnvironment = Field(default=AffectedEnvironment.PRODUCTION)
    estimated_resolution_time_seconds: int = Field(default=0, ge=0)
    mitigation_state: Optional[str] = Field(None, max_length=10_000)
    application_id: Optional[UUID] = None
    assigned_to_id: Optional[UUID] = None

class IncidentCreate(IncidentBase):
    pass

class IncidentUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    categoria: Optional[str] = Field(None, min_length=1, max_length=50)
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=10_000)
    severity: Optional[IncidentSeverity] = None
    affected_environment: Optional[AffectedEnvironment] = None
    estimated_resolution_time_seconds: Optional[int] = Field(None, ge=0)
    mitigation_state: Optional[str] = Field(None, max_length=10_000)
    application_id: Optional[UUID] = None
    assigned_to_id: Optional[UUID] = None

    @field_validator("title", "categoria", "severity", "affected_environment", "estimated_resolution_time_seconds")
    @classmethod
    def rechazar_nulos(cls, valor):
        if valor is None:
            raise ValueError("El campo no puede ser nulo")
        return valor

class IncidentStatusUpdate(BaseModel):
    status: IncidentStatus

class IncidentResponse(IncidentBase):
    id: UUID
    status: IncidentStatus
    created_by_id: Optional[UUID]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ComentarioIncidencia(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    comentario: str = Field(min_length=1, max_length=10000)


class EventoIncidenciaRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    incident_id: UUID
    autor_id: Optional[UUID]
    autor_nombre: str
    tipo: str
    estado_anterior: Optional[str]
    estado_nuevo: Optional[str]
    comentario: Optional[str]
    created_at: datetime
