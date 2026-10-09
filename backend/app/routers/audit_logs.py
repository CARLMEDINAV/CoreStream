"""
Consulta y exportación del registro de auditoría (TRV-07 / TRV-08).

La consulta está acotada al cliente del usuario y a la profundidad que su plan
concede. La exportación exige el flag `audit_export` (solo Enterprise) y queda
registrada como evento de auditoría en sí misma — una extracción completa del
historial es precisamente el tipo de acto que el registro debe recoger.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.context import mark_auditable, set_audit_resource
from app.database import get_db
from app.middleware.auth import require_role
from app.middleware.commercial import get_commercial_profile, require_feature
from app.models import User
from app.models.role import UserRole
from app.plans import audit_retention_days
from app.schemas.audit import AuditLogPage, AuditLogResponse
from app.schemas.commercial import CommercialProfile
from app.services import audit_service
from app.services.audit_export import EXTENSION, MEDIA_TYPE, render_csv

router = APIRouter(prefix="/api/audit-logs", tags=["Auditoría"])

# "ADMIN / Auditor (consulta)" se interpreta como un único rol del sistema: el
# resto del documento de requerimientos enumera siempre tres roles
# (ADMIN, TEAM_LEADER, DEVELOPER) y "Auditor" aparece solo aquí, así que se lee
# como la función de auditar y no como un rol aparte.
#
# TEAM_LEADER queda fuera a propósito: gestiona el trabajo de su equipo, no
# audita a sus miembros.
AUDIT_READERS = [UserRole.ADMIN.value]

_EXPORT_LIMIT = 50_000


@router.get("/", response_model=AuditLogPage, summary="Consultar el registro de auditoría")
async def list_audit_logs(
    actor_email: Optional[str] = Query(None, max_length=255),
    actor_user_id: Optional[UUID] = None,
    resource_type: Optional[str] = Query(None, max_length=50),
    outcome: Optional[Literal["SUCCESS", "DENIED", "FAILED", "ERROR"]] = None,
    method: Optional[Literal["POST", "PUT", "PATCH", "DELETE", "GET"]] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    _: None = Depends(require_feature("audit_log")),
    current_user: User = Depends(require_role(AUDIT_READERS)),
    profile: CommercialProfile = Depends(get_commercial_profile),
    db: AsyncSession = Depends(get_db),
) -> AuditLogPage:
    entries, total = await audit_service.query_entries(
        db,
        client_id=current_user.client_id,
        plan=profile.plan,
        actor_email=actor_email,
        actor_user_id=actor_user_id,
        resource_type=resource_type,
        outcome=outcome,
        method=method,
        date_from=date_from,
        date_to=date_to,
        skip=skip,
        limit=limit,
    )

    return AuditLogPage(
        items=[AuditLogResponse.model_validate(entry) for entry in entries],
        total=total,
        skip=skip,
        limit=limit,
        retention_days=audit_retention_days(profile.plan),
    )


@router.get(
    "/export",
    response_class=PlainTextResponse,
    summary="Exportar el registro de auditoría",
    description="Exporta en CSV para auditorías externas. Requiere plan Enterprise.",
)
async def export_audit_logs(
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    _: None = Depends(require_feature("audit_export")),
    current_user: User = Depends(require_role(AUDIT_READERS)),
    profile: CommercialProfile = Depends(get_commercial_profile),
    db: AsyncSession = Depends(get_db),
) -> PlainTextResponse:
    # Es un GET con 200: sin esto las reglas por defecto no lo registrarían.
    mark_auditable()
    set_audit_resource("audit_export")

    entries, _total = await audit_service.query_entries(
        db,
        client_id=current_user.client_id,
        plan=profile.plan,
        date_from=date_from,
        date_to=date_to,
        skip=0,
        limit=_EXPORT_LIMIT,
    )

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    return PlainTextResponse(
        content=render_csv(entries),
        media_type=MEDIA_TYPE,
        headers={
            "Content-Disposition":
                f'attachment; filename="auditoria-{stamp}.{EXTENSION}"'
        },
    )
