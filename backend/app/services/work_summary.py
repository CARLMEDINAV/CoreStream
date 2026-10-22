"""consultas de trabajo personal y de equipo para web-18."""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Ticket, TicketStatus
from app.models.incident import EventoIncidencia, Incident, IncidentStatus


async def resumen_trabajo(db: AsyncSession, cliente_id: UUID, usuario_id: UUID | None = None) -> dict:
    ahora = datetime.now(timezone.utc)
    desde = ahora - timedelta(days=7)
    resolucion = select(func.max(EventoIncidencia.created_at)).where(
        EventoIncidencia.incident_id == Incident.id,
        EventoIncidencia.client_id == cliente_id,
        EventoIncidencia.tipo == "estado",
        EventoIncidencia.estado_nuevo == "RESOLVED",
    ).correlate(Incident).scalar_subquery()
    resultado = {}
    for nombre, modelo, responsable, finales, progreso, bloqueados, fecha in (
        ("tickets", Ticket, Ticket.assignee_id,
         (TicketStatus.COMPLETED, TicketStatus.RESOLVED),
         (TicketStatus.IN_PROGRESS, TicketStatus.INVESTIGATING),
         (TicketStatus.BLOCKED, TicketStatus.BLOCKED_QUESTION), Ticket.completed_at),
        ("incidents", Incident, Incident.assigned_to_id,
         (IncidentStatus.RESOLVED, IncidentStatus.CLOSED),
         (IncidentStatus.INVESTIGATING, IncidentStatus.MITIGATED, IncidentStatus.IN_REVIEW),
         (), resolucion),
    ):
        consulta = select(
            func.count().filter(modelo.status.not_in(finales)),
            func.count().filter(modelo.status.in_(progreso)),
            func.count().filter(modelo.status.in_(bloqueados)),
            func.count().filter(modelo.status.in_(finales), fecha >= desde, fecha <= ahora),
        ).where(modelo.client_id == cliente_id)
        if usuario_id is not None:
            consulta = consulta.where(responsable == usuario_id)
        fila = (await db.execute(consulta)).one()
        resultado[nombre] = dict(zip(
            ("active", "in_progress", "blocked", "completed_last_7_days"), fila, strict=True,
        ))
    resultado["total"] = {
        clave: resultado["tickets"][clave] + resultado["incidents"][clave]
        for clave in resultado["tickets"]
    }
    return resultado


async def banco_trabajo(db: AsyncSession, cliente_id: UUID, usuario_id: UUID) -> list[dict]:
    tickets = (await db.scalars(select(Ticket).where(
        Ticket.client_id == cliente_id, Ticket.assignee_id == usuario_id,
        Ticket.status.not_in((TicketStatus.COMPLETED, TicketStatus.RESOLVED)),
    ))).all()
    incidencias = (await db.scalars(select(Incident).where(
        Incident.client_id == cliente_id, Incident.assigned_to_id == usuario_id,
        Incident.status.not_in((IncidentStatus.RESOLVED, IncidentStatus.CLOSED)),
    ))).all()
    resultado = []
    for tipo, elementos in (("ticket", tickets), ("incident", incidencias)):
        for elemento in elementos:
            fecha = elemento.due_date if tipo == "ticket" else (
                elemento.created_at + timedelta(seconds=elemento.estimated_resolution_time_seconds)
                if elemento.estimated_resolution_time_seconds else None
            )
            if fecha is not None and fecha.tzinfo is None:
                fecha = fecha.replace(tzinfo=timezone.utc)
            resultado.append({
                "id": elemento.id, "type": tipo, "title": elemento.title,
                "status": elemento.status.value, "due_date": fecha,
            })
    resultado.sort(key=lambda elemento: (
        elemento["due_date"] is None,
        elemento["due_date"] or datetime.max.replace(tzinfo=timezone.utc),
        elemento["type"], str(elemento["id"]),
    ))
    return resultado
