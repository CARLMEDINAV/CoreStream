from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    occurred_at: datetime
    request_id: str | None = None
    actor_user_id: UUID | None = None
    actor_email: str | None = None
    actor_role: str | None = None
    method: str
    path: str
    route_template: str | None = None
    resource_type: str | None = None
    resource_id: UUID | None = None
    status_code: int
    outcome: str
    ip: str | None = None
    user_agent: str | None = None
    duration_ms: int | None = None


class AuditLogPage(BaseModel):
    items: list[AuditLogResponse]
    total: int
    skip: int
    limit: int
    retention_days: int
