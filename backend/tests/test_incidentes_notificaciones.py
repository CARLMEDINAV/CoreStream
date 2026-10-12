import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models import Client, Notification, Role, User
from app.models.incident import Incident
from app.routers import incidents, notifications
from app.services import notification_service
from app.worker.tasks import deliver_notification


@pytest.fixture
async def entorno(db_session, sample_user, sample_client):
    rol = Role(name="DEVELOPER", description="desarrollador")
    lider = Role(name="TEAM_LEADER", description="lider")
    db_session.add_all([rol, lider])
    await db_session.flush()
    desarrollador = User(
        email="dev-web17@example.com", full_name="desarrollador",
        hashed_password="prueba", role=rol, client_id=sample_client.id,
    )
    otro = User(
        email="otro-web17@example.com", full_name="otro",
        hashed_password="prueba", role=rol, client_id=sample_client.id,
    )
    jefe = User(
        email="lider-web17@example.com", full_name="lider",
        hashed_password="prueba", role=lider, client_id=sample_client.id,
    )
    cliente_ajeno = Client(name="ajeno", slug="ajeno-web17", is_active=True)
    db_session.add_all([cliente_ajeno, desarrollador, otro, jefe])
    await db_session.flush()
    ajeno = User(
        email="ajeno-web17@example.com", full_name="ajeno",
        hashed_password="prueba", role=rol, client_id=cliente_ajeno.id,
    )
    db_session.add_all([desarrollador, otro, jefe, ajeno])
    await db_session.commit()
    await db_session.execute(text("PRAGMA foreign_keys=ON"))
    datos = SimpleNamespace(
        usuario=sample_user, admin=sample_user, dev=desarrollador,
        otro=otro, lider=jefe, ajeno=ajeno, db=db_session,
    )
    aplicacion = FastAPI()
    aplicacion.include_router(incidents.router, prefix="/api")
    aplicacion.include_router(notifications.router, prefix="/api/notifications")

    async def obtener_db():
        yield db_session

    aplicacion.dependency_overrides[get_db] = obtener_db
    aplicacion.dependency_overrides[get_current_user] = lambda: datos.usuario
    async with AsyncClient(transport=ASGITransport(app=aplicacion), base_url="http://prueba") as conexion:
        datos.api = conexion
        yield datos


async def crear(entorno, **datos):
    respuesta = await entorno.api.post("/api/incidents/", json={"title": "incidencia de prueba", **datos})
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


async def test_ciclo_completo_con_historial_y_comentarios(entorno):
    entorno.usuario = entorno.dev
    incidencia = await crear(entorno, severity="P1", categoria="red")
    identificador = incidencia["id"]
    ruta = f"/api/incidents/{identificador}"
    entorno.usuario = entorno.lider
    assert (await entorno.api.get("/api/incidents/?atencion=true")).json()[0]["id"] == identificador
    respuesta = await entorno.api.patch(ruta, json={"assigned_to_id": str(entorno.dev.id)})
    assert respuesta.status_code == 200
    assert respuesta.json()["status"] == "ASSIGNED"
    entorno.usuario = entorno.dev
    for estado in ("INVESTIGATING", "MITIGATED", "INVESTIGATING", "IN_REVIEW"):
        respuesta = await entorno.api.patch(ruta + "/status", json={"status": estado})
        assert respuesta.status_code == 200, respuesta.text
    assert (await entorno.api.post(ruta + "/comments", json={"comentario": "prueba lista"})).status_code == 201
    assert (await entorno.api.patch(ruta + "/status", json={"status": "RESOLVED"})).status_code == 403
    entorno.usuario = entorno.lider
    for estado in ("RESOLVED", "CLOSED"):
        assert (await entorno.api.patch(ruta + "/status", json={"status": estado})).status_code == 200
    assert (await entorno.api.get("/api/incidents/?atencion=true")).json() == []
    assert (await entorno.api.patch(ruta + "/status", json={"status": "REOPENED"})).status_code == 200
    assert (await entorno.api.get("/api/incidents/?atencion=true")).json()[0]["id"] == identificador
    historial = (await entorno.api.get(ruta + "/events")).json()
    assert {evento["tipo"] for evento in historial} >= {"reporte", "asignacion", "estado", "comentario"}
    assert all(evento["autor_id"] and evento["autor_nombre"] and evento["created_at"] for evento in historial)
    assert any(evento["estado_anterior"] == "CLOSED" and evento["estado_nuevo"] == "REOPENED" for evento in historial)


async def test_notificaciones_reales_filtradas_y_enlazadas(entorno, sample_ticket):
    await crear(entorno, assigned_to_id=str(entorno.dev.id))
    await notification_service.create_notification(
        entorno.db, user_id=entorno.dev.id, title="ticket", message="asignado",
        notification_type="TICKET_ASSIGNED", ticket_id=sample_ticket.id,
    )
    await entorno.db.commit()
    entorno.usuario = entorno.dev
    for tipo, campo in (("INCIDENT_ASSIGNED", "incident_id"), ("TICKET_ASSIGNED", "ticket_id")):
        respuesta = await entorno.api.get("/api/notifications/", params={"type": tipo, "unread_only": True})
        assert respuesta.status_code == 200, respuesta.text
        avisos = respuesta.json()
        assert len(avisos) == 1 and avisos[0]["type"] == tipo
        assert avisos[0][campo] is not None
        assert (avisos[0]["ticket_id"] is None) != (avisos[0]["incident_id"] is None)
        recurso = "incidents" if campo == "incident_id" else "tickets"
        if recurso == "incidents":
            assert (await entorno.api.get("/api/incidents/" + avisos[0][campo])).status_code == 200
        assert (await entorno.api.get("/api/notifications/", params={"type": tipo, "skip": 1, "limit": 1})).json() == []
    assert len((await entorno.api.get("/api/notifications/")).json()) == 2
    assert (await entorno.api.get("/api/notifications/?type=DESCONOCIDO")).status_code == 422
    entorno.usuario = entorno.admin
    reporte = (await entorno.api.get("/api/notifications/?type=INCIDENT_REPORTED")).json()
    assert len(reporte) == 1 and reporte[0]["incident_id"]
    assert (await entorno.api.get("/api/notifications/?type=INCIDENT_ASSIGNED")).json() == []


async def test_no_repite_asignacion_ni_permite_atajos(entorno):
    incidencia = await crear(entorno, assigned_to_id=str(entorno.dev.id))
    ruta = "/api/incidents/" + incidencia["id"]
    assert (await entorno.api.patch(ruta, json={"assigned_to_id": str(entorno.dev.id)})).status_code == 200
    assert (await entorno.api.patch(ruta + "/status", json={"status": "CLOSED"})).status_code == 409
    entorno.usuario = entorno.dev
    assert len((await entorno.api.get("/api/notifications/")).json()) == 1
    assert (await entorno.api.patch(ruta, json={"assigned_to_id": str(entorno.otro.id)})).status_code == 403
    entorno.usuario = entorno.otro
    assert (await entorno.api.patch(ruta + "/status", json={"status": "INVESTIGATING"})).status_code == 403
    assert (await entorno.api.patch(ruta, json={"mitigation_state": "ajena"})).status_code == 403
    assert (await entorno.api.post("/api/incidents/", json={
        "title": "sin permiso", "assigned_to_id": str(entorno.otro.id),
    })).status_code == 403


async def test_aislamiento_y_referencias_ajenas(entorno):
    incidencia = await crear(entorno)
    ruta = "/api/incidents/" + incidencia["id"]
    assert (await entorno.api.patch(ruta, json={"assigned_to_id": str(entorno.ajeno.id)})).status_code == 422
    assert (await entorno.api.patch(ruta, json={"assigned_to_id": str(entorno.admin.id)})).status_code == 422
    assert (await entorno.api.patch(ruta, json={"application_id": str(uuid4())})).status_code == 404
    entorno.usuario = entorno.ajeno
    for sufijo in ("", "/events"):
        assert (await entorno.api.get(ruta + sufijo)).status_code == 404
    assert (await entorno.api.patch(ruta + "/status", json={"status": "INVESTIGATING"})).status_code == 404
    assert (await entorno.api.post(ruta + "/comments", json={"comentario": "ajeno"})).status_code == 404
    assert (await entorno.api.get("/api/incidents/")).json() == []
    assert (await entorno.api.get("/api/notifications/?type=INCIDENT_REPORTED")).json() == []


@pytest.mark.parametrize("datos", [
    {"title": "   "}, {"categoria": "   "}, {"severity": None},
    {"title": None}, {"categoria": None}, {"estimated_resolution_time_seconds": None},
])
async def test_campos_invalidos(entorno, datos):
    incidencia = await crear(entorno)
    assert (await entorno.api.patch("/api/incidents/" + incidencia["id"], json=datos)).status_code == 422


@pytest.mark.parametrize("tipo,ticket,incidente", [
    ("TICKET_ASSIGNED", False, False), ("INCIDENT_REPORTED", False, False),
    ("INCIDENT_ASSIGNED", True, False), ("STATUS_CHANGED", False, True),
    ("INCIDENT_REPORTED", True, True), ("SYSTEM", True, True),
    ("NO_EXISTE", False, False),
])
async def test_rechaza_enlaces_invalidos(entorno, tipo, ticket, incidente):
    with pytest.raises(ValueError):
        await notification_service.create_notification(
            entorno.db, user_id=entorno.dev.id, title="prueba", message="prueba",
            notification_type=tipo, ticket_id=uuid4() if ticket else None,
            incident_id=uuid4() if incidente else None,
        )


async def test_servicio_rechaza_recurso_de_otro_cliente(entorno):
    incidencia = await crear(entorno)
    with pytest.raises(ValueError, match="cliente"):
        await notification_service.create_notification(
            entorno.db, user_id=entorno.ajeno.id, title="prueba", message="prueba",
            notification_type="INCIDENT_ASSIGNED", incident_id=incidencia["id"],
        )


async def test_base_rechaza_aviso_sin_recurso(entorno):
    entorno.db.add(Notification(
        user_id=entorno.dev.id, client_id=entorno.dev.client_id,
        type="INCIDENT_REPORTED", title="prueba", message="prueba",
    ))
    with pytest.raises(IntegrityError):
        await entorno.db.flush()
    await entorno.db.rollback()


async def test_cola_y_worker_conservan_incident_id(entorno, monkeypatch):
    cola = AsyncMock()
    monkeypatch.setattr(notification_service, "_arq_pool", cola)
    incidencia = await crear(entorno, assigned_to_id=str(entorno.dev.id))
    llamadas = cola.enqueue_job.call_args_list
    assert {llamada.kwargs["notification_type"] for llamada in llamadas} == {"INCIDENT_REPORTED", "INCIDENT_ASSIGNED"}
    for llamada in llamadas:
        assert llamada.kwargs["incident_id"] == incidencia["id"]
        assert llamada.kwargs["ticket_id"] is None
        redis = AsyncMock()
        await deliver_notification({"redis": redis}, **llamada.kwargs)
        aviso = json.loads(redis.publish.call_args.args[1])
        assert aviso["incident_id"] == incidencia["id"]
        assert aviso["type"] == llamada.kwargs["notification_type"]
        assert aviso["ticket_id"] is None


async def test_borrar_recurso_borra_sus_avisos(entorno):
    incidencia = await crear(entorno)
    registro = await entorno.db.get(Incident, UUID(incidencia["id"]))
    await entorno.db.delete(registro)
    await entorno.db.commit()
    assert (await entorno.db.scalars(select(Notification))).all() == []

