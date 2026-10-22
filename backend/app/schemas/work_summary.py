from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class ConteosTrabajo(BaseModel):
    active: int
    in_progress: int
    blocked: int
    completed_last_7_days: int


class ResumenTrabajo(BaseModel):
    tickets: ConteosTrabajo
    incidents: ConteosTrabajo
    total: ConteosTrabajo


class TrabajoPersonal(BaseModel):
    id: UUID
    type: Literal["ticket", "incident"]
    title: str
    status: str
    due_date: datetime | None
