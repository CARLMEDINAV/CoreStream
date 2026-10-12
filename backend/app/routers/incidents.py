from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.context import set_audit_resource
from app.database import get_db
from app.middleware.auth import get_current_user
from app.models import Application, Role, User
from app.models.incident import EventoIncidencia, Incident, IncidentStatus
from app.schemas.incident import (
    ComentarioIncidencia,
    EventoIncidenciaRespuesta,
    IncidentCreate,
    IncidentResponse,
    IncidentStatusUpdate,
    IncidentUpdate,
)
from app.services.notification_service import create_notification, flush_pending_notifications
from app.services.ticket_permissions import is_admin_or_leader, require_admin_or_leader

router = APIRouter(prefix="/incidents", tags=["incidents"])


async def buscar_incidencia(db, identificador, usuario, bloquear=False):
    consulta = select(Incident).where(
        Incident.id == identificador, Incident.client_id == usuario.client_id,
    )
    if bloquear:
        consulta = consulta.with_for_update()
    incidencia = (await db.execute(consulta)).scalar_one_or_none()
    if incidencia is None:
        raise HTTPException(404, "Incidente no encontrado")
    return incidencia


async def validar_referencias(db, datos, usuario):
    if datos.get("application_id"):
        aplicacion = await db.scalar(select(Application.id).where(
            Application.id == datos["application_id"], Application.client_id == usuario.client_id,
        ))
        if aplicacion is None:
            raise HTTPException(404, "Aplicación no encontrada")
    if datos.get("assigned_to_id"):
        responsable = await db.scalar(select(User.id).join(Role).where(
            User.id == datos["assigned_to_id"], User.client_id == usuario.client_id,
            User.is_active, Role.name.in_(["DEVELOPER", "TEAM_LEADER"]),
        ))
        if responsable is None:
            raise HTTPException(422, "El responsable debe ser un desarrollador o líder activo del cliente")


def registrar_evento(db, incidencia, usuario, tipo, anterior=None, comentario=None):
    evento = EventoIncidencia(
        incident_id=incidencia.id, client_id=incidencia.client_id,
        autor_id=usuario.id, autor_nombre=usuario.full_name, tipo=tipo,
        estado_anterior=anterior, estado_nuevo=incidencia.status.value,
        comentario=comentario,
        created_at=datetime.now(timezone.utc),
    )
    db.add(evento)
    return evento


async def avisar_incidencia(db, incidencia, destinatario, tipo):
    aviso = await create_notification(
        db, user_id=destinatario, title=incidencia.title,
        message=("Incidencia reportada" if tipo == "INCIDENT_REPORTED" else "Se te asignó una incidencia"),
        notification_type=tipo, incident_id=incidencia.id,
    )
    db.info.setdefault("_pending_notifications", []).append(aviso)


@router.post("/", response_model=IncidentResponse, status_code=status.HTTP_201_CREATED)
async def create_incident(
    incident_in: IncidentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if incident_in.assigned_to_id:
        require_admin_or_leader(current_user)
    await validar_referencias(db, incident_in.model_dump(), current_user)
    incident = Incident(
        **incident_in.model_dump(), created_by_id=current_user.id,
        client_id=current_user.client_id, status=IncidentStatus.REPORTED,
    )
    db.add(incident)
    await db.flush()
    registrar_evento(db, incident, current_user, "reporte")
    destinatarios = (await db.scalars(select(User.id).join(Role).where(
        User.client_id == current_user.client_id, User.is_active,
        Role.name.in_(["ADMIN", "TEAM_LEADER"]),
    ))).all()
    for destinatario in destinatarios:
        await avisar_incidencia(db, incident, destinatario, "INCIDENT_REPORTED")
    if incident.assigned_to_id:
        incident.status = IncidentStatus.ASSIGNED
        registrar_evento(db, incident, current_user, "asignacion", "REPORTED", str(incident.assigned_to_id))
        await avisar_incidencia(db, incident, incident.assigned_to_id, "INCIDENT_ASSIGNED")
    await db.commit()
    await db.refresh(incident)
    await flush_pending_notifications(db)
    set_audit_resource("incident", incident.id)
    return incident


@router.get("/", response_model=list[IncidentResponse])
async def get_incidents(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    atencion: bool = False,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Incident).where(Incident.client_id == current_user.client_id)
    if atencion:
        require_admin_or_leader(current_user)
        query = query.where(
            Incident.severity.in_(["P1", "P2"]),
            Incident.status.not_in([IncidentStatus.RESOLVED, IncidentStatus.CLOSED]),
        )
    result = await db.execute(query.order_by(Incident.created_at.desc(), Incident.id).offset(skip).limit(limit))
    return result.scalars().all()


@router.get("/{incident_id}", response_model=IncidentResponse)
async def get_incident(
    incident_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await buscar_incidencia(db, incident_id, current_user)


@router.patch("/{incident_id}", response_model=IncidentResponse)
async def update_incident(
    incident_id: UUID,
    incident_in: IncidentUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    incident = await buscar_incidencia(db, incident_id, current_user, bloquear=True)
    update_data = incident_in.model_dump(exclude_unset=True)
    if not is_admin_or_leader(current_user):
        if incident.assigned_to_id != current_user.id or set(update_data) - {"mitigation_state"}:
            raise HTTPException(403, "Solo puedes actualizar las notas de tus incidencias")
    await validar_referencias(db, update_data, current_user)
    anterior = incident.status.value
    reasignado = "assigned_to_id" in update_data and update_data["assigned_to_id"] != incident.assigned_to_id
    if reasignado and incident.status in (IncidentStatus.RESOLVED, IncidentStatus.CLOSED):
        raise HTTPException(409, "Reabre la incidencia antes de cambiar el responsable")
    for field, value in update_data.items():
        setattr(incident, field, value)
    if reasignado:
        incident.status = IncidentStatus.ASSIGNED if incident.assigned_to_id else IncidentStatus.REPORTED
        registrar_evento(db, incident, current_user, "asignacion", anterior, str(incident.assigned_to_id or ""))
        if incident.assigned_to_id:
            await avisar_incidencia(db, incident, incident.assigned_to_id, "INCIDENT_ASSIGNED")
    elif update_data:
        registrar_evento(db, incident, current_user, "actualizacion", comentario=", ".join(update_data))
    await db.commit()
    await db.refresh(incident)
    await flush_pending_notifications(db)
    return incident


@router.patch("/{incident_id}/status", response_model=IncidentResponse)
async def update_incident_status(
    incident_id: UUID,
    status_in: IncidentStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    incident = await buscar_incidencia(db, incident_id, current_user, bloquear=True)
    if not is_admin_or_leader(current_user) and incident.assigned_to_id != current_user.id:
        raise HTTPException(403, "Solo puedes gestionar tus incidencias")
    if status_in.status in (IncidentStatus.RESOLVED, IncidentStatus.CLOSED, IncidentStatus.REOPENED):
        require_admin_or_leader(current_user)
    cambios = {
        "REPORTED": {"INVESTIGATING"},
        "ASSIGNED": {"INVESTIGATING"},
        "INVESTIGATING": {"IN_REVIEW", "MITIGATED"},
        "MITIGATED": {"INVESTIGATING", "IN_REVIEW"},
        "IN_REVIEW": {"INVESTIGATING", "RESOLVED"},
        "RESOLVED": {"CLOSED", "REOPENED"},
        "CLOSED": {"REOPENED"},
        "REOPENED": {"INVESTIGATING"},
    }
    if status_in.status == incident.status:
        return incident
    if status_in.status.value not in cambios[incident.status.value]:
        raise HTTPException(409, "Ese cambio de estado no está permitido")
    if status_in.status == IncidentStatus.INVESTIGATING and not incident.assigned_to_id:
        raise HTTPException(409, "Asigna un responsable antes de tomar la incidencia")
    anterior = incident.status.value
    incident.status = status_in.status
    registrar_evento(db, incident, current_user, "estado", anterior)
    await db.commit()
    await db.refresh(incident)
    return incident


@router.get("/{incident_id}/events", response_model=list[EventoIncidenciaRespuesta])
async def listar_eventos(
    incident_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await buscar_incidencia(db, incident_id, current_user)
    return (await db.scalars(select(EventoIncidencia).where(
        EventoIncidencia.incident_id == incident_id, EventoIncidencia.client_id == current_user.client_id,
    ).order_by(EventoIncidencia.created_at, EventoIncidencia.id))).all()


@router.post("/{incident_id}/comments", response_model=EventoIncidenciaRespuesta, status_code=201)
async def comentar_incidencia(
    incident_id: UUID,
    datos: ComentarioIncidencia,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    incidencia = await buscar_incidencia(db, incident_id, current_user)
    evento = registrar_evento(db, incidencia, current_user, "comentario", comentario=datos.comentario)
    await db.commit()
    await db.refresh(evento)
    return evento
