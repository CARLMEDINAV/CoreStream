from uuid import UUID

from pydantic import BaseModel


class CommercialProfile(BaseModel):
    client_id: UUID
    plan: str
    is_active: bool
    feature_flags: dict[str, bool]
    audit_retention_days: int = 30
