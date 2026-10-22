from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient

from app.database import get_db
from app.middleware.auth import get_current_user
from app.middleware.commercial import require_feature
from app.models import Client, Role, Ticket, TicketStatus, User
from app.models.incident import EventoIncidencia, Incident, IncidentStatus
from app.routers import analytics, tickets, users


@pytest.fixture
async def entorno(db_session, sample_user, sample_client):
    sample_client.commercial_plan = "Pro"
    rol = Role(name="DEVELOPER")
    lider = Role(name="TEAM_LEADER")
    ajeno = Client(name="ajeno", slug="ajeno-web18")
    db_session.add_all([rol, lider, ajeno])
    await db_session.flush()
    datos = SimpleNamespace(db=db_session, cliente=sample_client, admin=sample_user, usuario=sample_user)
    for nombre, cargo, cliente in (("dev", rol, sample_client), ("otro", rol, sample_client),
                                   ("lider", lider, sample_client), ("ajeno", rol, ajeno)):
        usuario = User(email=f"{nombre}@example.com", full_name=nombre,
                       hashed_password="prueba", role=cargo, client_id=cliente.id)
        db_session.add(usuario)
        setattr(datos, nombre, usuario)
    await db_session.flush()
    aplicacion = FastAPI()
    aplicacion.include_router(users.router, prefix="/api/users")
    aplicacion.include_router(tickets.router, prefix="/api/tickets")
    aplicacion.include_router(analytics.router, prefix="/api/analytics",
                             dependencies=[Depends(require_feature("analytics"))])

    async def obtener_db():
        yield db_session

    aplicacion.dependency_overrides[get_db] = obtener_db
    aplicacion.dependency_overrides[get_current_user] = lambda: datos.usuario
    async with AsyncClient(transport=ASGITransport(app=aplicacion), base_url="http://prueba") as conexion:
        datos.api = conexion
        yield datos


async def agregar(entorno, modelo, **campos):
    elemento = modelo(client_id=entorno.cliente.id, title="trabajo", **campos)
    entorno.db.add(elemento)
    await entorno.db.flush()
    return elemento


async def test_banco_mezcla_ordena_y_excluye_trabajo_ajeno_o_finalizado(entorno):
    ahora = datetime.now(timezone.utc)
    primero = await agregar(entorno, Ticket, assignee_id=entorno.dev.id, due_date=ahora - timedelta(days=1))
    segundo = await agregar(entorno, Incident, assigned_to_id=entorno.dev.id,
                            created_at=ahora, estimated_resolution_time_seconds=3600)
    tercero = await agregar(entorno, Ticket, assignee_id=entorno.dev.id, due_date=ahora + timedelta(days=1))
    sin_fecha = await agregar(entorno, Incident, assigned_to_id=entorno.dev.id)
    await agregar(entorno, Ticket, assignee_id=entorno.otro.id)
    await agregar(entorno, Incident, assigned_to_id=entorno.otro.id)
    await agregar(entorno, Ticket, assignee_id=entorno.dev.id, status=TicketStatus.COMPLETED)
    await agregar(entorno, Ticket, assignee_id=entorno.dev.id, status=TicketStatus.RESOLVED)
    for estado in (IncidentStatus.RESOLVED, IncidentStatus.CLOSED):
        await agregar(entorno, Incident, assigned_to_id=entorno.dev.id, status=estado)
    entorno.usuario = entorno.dev
    respuesta = await entorno.api.get("/api/users/me/workbench")
    assert respuesta.status_code == 200, respuesta.text
    datos = respuesta.json()
    assert [fila["id"] for fila in datos] == [str(x.id) for x in (primero, segundo, tercero, sin_fecha)]
    assert [fila["type"] for fila in datos] == ["ticket", "incident", "ticket", "incident"]
    assert datos[-1]["due_date"] is None
    entorno.usuario = entorno.ajeno
    assert (await entorno.api.get("/api/users/me/workbench")).json() == []


async def test_conteos_personales_equipo_y_resolucion_sin_duplicados(entorno):
    ahora = datetime.now(timezone.utc)
    for estado in (TicketStatus.TODO, TicketStatus.IN_PROGRESS, TicketStatus.BLOCKED,
                   TicketStatus.BLOCKED_QUESTION, TicketStatus.REDIRECTED):
        await agregar(entorno, Ticket, assignee_id=entorno.dev.id, status=estado)
    for dias in (1, 8, -1):
        await agregar(entorno, Ticket, assignee_id=entorno.dev.id, status=TicketStatus.COMPLETED,
                      completed_at=ahora - timedelta(days=dias))
    for estado in (IncidentStatus.REOPENED, IncidentStatus.INVESTIGATING,
                   IncidentStatus.MITIGATED, IncidentStatus.IN_REVIEW):
        await agregar(entorno, Incident, assigned_to_id=entorno.dev.id, status=estado)
    for estado, dias in ((IncidentStatus.CLOSED, 1), (IncidentStatus.RESOLVED, 8),
                         (IncidentStatus.REOPENED, 1)):
        incidencia = await agregar(entorno, Incident, assigned_to_id=entorno.dev.id, status=estado)
        for tipo in ("estado", "comentario"):
            entorno.db.add(EventoIncidencia(
                client_id=entorno.cliente.id, incident_id=incidencia.id, autor_nombre="lider",
                tipo=tipo, estado_nuevo="RESOLVED", created_at=ahora - timedelta(days=dias),
            ))
    await agregar(entorno, Ticket)
    await entorno.db.flush()
    entorno.usuario = entorno.dev
    respuesta = await entorno.api.get(f"/api/users/{entorno.dev.id}/stats")
    assert respuesta.status_code == 200, respuesta.text
    datos = respuesta.json()
    assert datos["blocked_tickets"] == 2
    assert datos["work_summary"]["total"] == {
        "active": 10, "in_progress": 4, "blocked": 2, "completed_last_7_days": 2,
    }
    entorno.usuario = entorno.lider
    equipo = (await entorno.api.get("/api/analytics/work-summary")).json()
    assert equipo["total"] == {**datos["work_summary"]["total"], "active": 11}
    entorno.usuario = entorno.ajeno
    personal = (await entorno.api.get(f"/api/users/{entorno.ajeno.id}/stats")).json()
    assert all(valor == 0 for valor in personal["work_summary"]["total"].values())


@pytest.mark.parametrize("rol", ["admin", "lider", "dev"])
async def test_permisos_y_plan(entorno, rol):
    entorno.usuario = getattr(entorno, rol)
    esperado = 403 if rol == "dev" else 200
    assert (await entorno.api.get(f"/api/users/{entorno.otro.id}/stats")).status_code == esperado
    assert (await entorno.api.get("/api/analytics/work-summary")).status_code == esperado
    assert (await entorno.api.get(f"/api/users/{entorno.usuario.id}/stats")).status_code == 200
    if rol != "dev":
        assert (await entorno.api.get(f"/api/users/{entorno.ajeno.id}/stats")).status_code == 404
        assert (await entorno.api.get(f"/api/users/{uuid4()}/stats")).status_code == 404
    entorno.cliente.commercial_plan = "Basico"
    await entorno.db.flush()
    respuesta = await entorno.api.get("/api/analytics/work-summary")
    assert respuesta.status_code == 403
    assert respuesta.json()["detail"]["code"] == "FEATURE_NOT_INCLUDED"
    assert (await entorno.api.get("/api/users/me/workbench")).status_code == 200
    assert (await entorno.api.get(f"/api/users/{entorno.usuario.id}/stats")).status_code == 200
    assert (await entorno.api.get("/api/users/invalido/stats")).status_code == 422


async def test_workbench_tickets_conserva_contrato_y_ordena(entorno):
    ahora = datetime.now(timezone.utc)
    ultimo = await agregar(entorno, Ticket, assignee_id=entorno.dev.id)
    primero = await agregar(entorno, Ticket, assignee_id=entorno.dev.id, due_date=ahora)
    entorno.usuario = entorno.dev
    respuesta = await entorno.api.get("/api/tickets/my-workbench")
    assert respuesta.status_code == 200, respuesta.text
    assert [fila["id"] for fila in respuesta.json()] == [str(primero.id), str(ultimo.id)]
    assert "subtasks" in respuesta.json()[0]


async def test_limite_siete_dias_historial_y_aislamiento_del_equipo(entorno, monkeypatch):
    ahora = datetime(2026, 10, 22, 12, tzinfo=timezone.utc)

    class Reloj(datetime):
        @classmethod
        def now(cls, tz=None):
            return ahora

    monkeypatch.setattr("app.services.work_summary.datetime", Reloj)
    for fecha in (ahora - timedelta(days=7), ahora - timedelta(days=7, seconds=1), ahora):
        await agregar(entorno, Ticket, status=TicketStatus.COMPLETED, completed_at=fecha)
    incidencia = await agregar(entorno, Incident, status=IncidentStatus.CLOSED)
    for dias in (8, 2, 1):
        entorno.db.add(EventoIncidencia(
            client_id=entorno.cliente.id, incident_id=incidencia.id, autor_nombre="lider",
            tipo="estado", estado_nuevo="RESOLVED", created_at=ahora - timedelta(days=dias),
        ))
    antigua = await agregar(entorno, Incident, status=IncidentStatus.RESOLVED)
    for tipo, dias in (("estado", 8), ("comentario", 1)):
        entorno.db.add(EventoIncidencia(
            client_id=entorno.cliente.id, incident_id=antigua.id, autor_nombre="lider",
            tipo=tipo, estado_nuevo="RESOLVED", created_at=ahora - timedelta(days=dias),
        ))
    await agregar(entorno, Incident, status=IncidentStatus.RESOLVED)
    entorno.db.add_all([
        Ticket(client_id=entorno.ajeno.client_id, title="ajeno"),
        Incident(client_id=entorno.ajeno.client_id, title="ajeno"),
    ])
    await entorno.db.flush()
    respuesta = await entorno.api.get("/api/analytics/work-summary")
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["total"] == {
        "active": 0, "in_progress": 0, "blocked": 0, "completed_last_7_days": 3,
    }
