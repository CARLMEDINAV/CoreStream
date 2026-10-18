"""
Consulta y exportación del registro de auditoría (TRV-07 / TRV-08).

La consulta está acotada al cliente del usuario y a la profundidad que su plan
concede. La exportación exige el flag `audit_export` (solo Enterprise) y queda
registrada como evento de auditoría en sí misma — una extracción completa del
historial es precisamente el tipo de acto que el registro debe recoger.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import AsyncIterator

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.context import defer_audit
from app.database import get_db
from app.middleware.auth import require_role
from app.middleware.commercial import get_commercial_profile, require_feature
from app.middleware.request_id import get_request_id
from app.models import AuditLog, User
from app.models.role import UserRole
from app.plans import audit_retention_days
from app.schemas.audit import (
    METHOD_VALUES,
    OUTCOME_VALUES,
    AuditActor,
    AuditFilterOptions,
    AuditFilters,
    AuditLogPage,
    AuditLogResponse,
)
from app.schemas.commercial import CommercialProfile
from app.services import audit_records, audit_service
from app.services.audit_export import EXTENSION, MEDIA_TYPE, iter_csv

router = APIRouter(prefix="/api/audit-logs", tags=["Auditoría"])

# "ADMIN / Auditor (consulta)" se interpreta como un único rol del sistema: el
# resto del documento de requerimientos enumera siempre tres roles
# (ADMIN, TEAM_LEADER, DEVELOPER) y "Auditor" aparece solo aquí, así que se lee
# como la función de auditar y no como un rol aparte.
#
# TEAM_LEADER queda fuera a propósito: gestiona el trabajo de su equipo, no
# audita a sus miembros.
AUDIT_READERS = [UserRole.ADMIN.value]


async def _record_export(
    request: Request,
    current_user: User,
    request_id: str | None,
    *,
    rows: int,
    status_code: int,
    duration_ms: int,
) -> None:
    """
    Escribe el evento de la extracción con su resultado.

    La ruta lleva los filtros con que se pidió y las filas entregadas: sin
    eso constaría que alguien exportó, pero no si se llevó el historial
    completo, el de un solo usuario, o un fichero cortado a medias.
    """
    detail = f"filas_entregadas={rows}"
    query = request.url.query

    await audit_service.record(audit_records.build_entry(
        client_id=current_user.client_id,
        request_id=request_id,
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        actor_role=current_user.role.name if current_user.role else None,
        method=request.method,
        path=(
            f"{request.url.path}?{query}&{detail}"
            if query
            else f"{request.url.path}?{detail}"
        ),
        route_template="/api/audit-logs/export",
        resource_type="audit_export",
        status_code=status_code,
        ip=request.client.host if request.client else None,
        user_agent=(request.headers.get("user-agent") or "")[:512] or None,
        duration_ms=duration_ms,
    ))


async def _audited_csv(
    entries: AsyncIterator[AuditLog],
    *,
    request: Request,
    current_user: User,
    request_id: str | None,
) -> AsyncIterator[str]:
    """
    Entrega el CSV y registra el acto cuando el fichero ha salido entero.

    El middleware no registra esta petición (ver context.defer_audit): escribe
    su entrada en cuanto el handler devuelve la respuesta, y en una respuesta
    por trozos eso ocurre antes de que el cuerpo haya salido. Habría quedado
    un 200 aunque el volcado se cortara a mitad, y una auditoría no puede
    afirmar que una extracción terminó bien sin saberlo.

    Registrando al final, el resultado es el real: SUCCESS con el fichero
    completo, ERROR si se corta, y en los dos casos con las filas que
    alcanzaron a salir.

    Lo que no se cubre: si el cliente aborta la descarga, el generador se
    cierra sin pasar por aquí y el acto no se registra.
    """
    started = time.perf_counter()
    delivered = 0

    def _elapsed() -> int:
        return int((time.perf_counter() - started) * 1000)

    try:
        async for block in iter_csv(entries):
            delivered += block.count("\n")
            yield block
    except Exception:
        # La cabecera ocupa la primera línea y no es una entrada.
        await _record_export(
            request, current_user, request_id,
            rows=max(delivered - 1, 0), status_code=500, duration_ms=_elapsed(),
        )
        raise
    else:
        await _record_export(
            request, current_user, request_id,
            rows=max(delivered - 1, 0), status_code=200, duration_ms=_elapsed(),
        )


@router.get("/", response_model=AuditLogPage, summary="Consultar el registro de auditoría")
async def list_audit_logs(
    filters: AuditFilters = Depends(),
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
        filters=filters,
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
    response_class=StreamingResponse,
    summary="Exportar el registro de auditoría",
    description="Exporta en CSV lo mismo que muestra el visor, con los filtros "
                "aplicados. Requiere plan Enterprise.",
)
async def export_audit_logs(
    request: Request,
    filters: AuditFilters = Depends(),
    _: None = Depends(require_feature("audit_export")),
    current_user: User = Depends(require_role(AUDIT_READERS)),
    profile: CommercialProfile = Depends(get_commercial_profile),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    # El resultado de este acto no se conoce hasta que el fichero ha salido
    # entero, así que lo registra el volcado y no el middleware.
    defer_audit()
    request_id = get_request_id()

    entries = audit_service.iter_entries(
        db,
        client_id=current_user.client_id,
        plan=profile.plan,
        filters=filters,
    )

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    return StreamingResponse(
        _audited_csv(
            entries,
            request=request,
            current_user=current_user,
            request_id=request_id,
        ),
        media_type=MEDIA_TYPE,
        headers={
            "Content-Disposition":
                f'attachment; filename="auditoria-{stamp}.{EXTENSION}"'
        },
    )


@router.get(
    "/filters",
    response_model=AuditFilterOptions,
    summary="Valores disponibles para los filtros del visor",
)
async def list_filter_options(
    filters: AuditFilters = Depends(),
    _: None = Depends(require_feature("audit_log")),
    current_user: User = Depends(require_role(AUDIT_READERS)),
    profile: CommercialProfile = Depends(get_commercial_profile),
    db: AsyncSession = Depends(get_db),
) -> AuditFilterOptions:
    resource_types, actors, truncated = await audit_service.filter_options(
        db,
        client_id=current_user.client_id,
        plan=profile.plan,
        filters=filters,
    )

    return AuditFilterOptions(
        resource_types=resource_types,
        actors=[AuditActor(id=actor_id, email=email) for actor_id, email in actors],
        actors_truncated=truncated,
        outcomes=list(OUTCOME_VALUES),
        methods=list(METHOD_VALUES),
        retention_days=audit_retention_days(profile.plan),
    )
