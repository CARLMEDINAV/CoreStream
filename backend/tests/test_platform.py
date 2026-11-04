"""permisos internos, cambios comerciales y uso premium."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.config import get_settings
from app.context import set_audit_actor
from app.database import get_db
from app.main import app
from app.middleware.auth import get_current_user
from app.models import AuditLog, Client
from app.plans import features_for


@pytest.fixture
async def consola(db_session, sample_user, sample_client, monkeypatch):
    ajustes = get_settings()
    monkeypatch.setattr(ajustes, "PLATFORM_ADMIN_IDS", [sample_user.id])
    monkeypatch.setattr(ajustes, "PLATFORM_CLIENT_ID", sample_client.id)
    monkeypatch.setattr(ajustes, "AUDIT_READS", False)

    async def base():
        yield db_session

    async def usuario():
        set_audit_actor(user_id=sample_user.id, email=sample_user.email,
                        role="ADMIN", client_id=sample_user.client_id)
        return sample_user

    async def registrar(entrada):
        db_session.add(AuditLog(**entrada))
        await db_session.commit()

    monkeypatch.setattr("app.middleware.audit.record", registrar)
    app.dependency_overrides[get_db] = base
    app.dependency_overrides[get_current_user] = usuario
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as api:
            yield api
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize("ruta,metodo", [
    ("/access", "get"), ("/clients", "get"),
    (f"/clients/{uuid4()}", "put"), (f"/clients/{uuid4()}/usage", "get"),
    (f"/clients/{uuid4()}/changes", "get"),
])
async def test_admin_cliente_no_accede(consola, monkeypatch, ruta, metodo):
    monkeypatch.setattr(get_settings(), "PLATFORM_ADMIN_IDS", [])
    respuesta = await consola.request(metodo, "/api/platform" + ruta)
    assert respuesta.status_code == 403


async def test_exige_cliente_interno_y_cuenta_activa(consola, sample_user, sample_client, monkeypatch):
    monkeypatch.setattr(get_settings(), "PLATFORM_CLIENT_ID", uuid4())
    assert (await consola.get("/api/platform/clients")).status_code == 403
    monkeypatch.setattr(get_settings(), "PLATFORM_CLIENT_ID", sample_client.id)
    sample_user.is_active = False
    assert (await consola.get("/api/platform/clients")).status_code == 403
    sample_user.is_active = True
    sample_client.is_active = False
    assert (await consola.get("/api/platform/clients")).status_code == 403


async def test_cambio_inmediato_con_auditoria_y_sin_afectar_otro_cliente(consola, db_session, sample_client):
    otro = Client(name="Otro", slug="otro")
    db_session.add(otro)
    await db_session.commit()
    assert len((await consola.get("/api/platform/clients")).json()) == 2
    ruta = f"/api/platform/clients/{sample_client.id}"
    datos = {"plan": "Pro", "feature_overrides": {"analytics": False, "audit_export": True}}
    respuesta = await consola.put(ruta, json=datos)
    assert respuesta.status_code == 200
    perfil = (await consola.get("/api/auth/commercial-profile")).json()
    assert perfil["feature_flags"]["analytics"] is False
    assert perfil["feature_flags"]["audit_export"] is True
    assert (await consola.get("/api/analytics/support-summary")).status_code == 403
    assert otro.commercial_plan == "Basico"
    cambios = (await consola.get(ruta + "/changes")).json()
    assert cambios[0]["detail"]["before"] == {"plan": "Basico", "feature_overrides": {}}
    assert cambios[0]["detail"]["after"] == datos
    registro = await db_session.scalar(select(AuditLog).where(AuditLog.resource_type == "commercial_profile"))
    assert registro.client_id == sample_client.id
    assert registro.actor_role == "PLATFORM_ADMIN"
    assert registro.ip and registro.user_agent and registro.actor_user_id
    assert (await consola.put(ruta, json={"plan": "Pro", "feature_overrides": {}})).status_code == 200
    assert (await consola.get("/api/analytics/support-summary")).status_code == 200


@pytest.mark.parametrize("datos", [
    {"plan": "Otro", "feature_overrides": {}},
    {"plan": "Pro", "feature_overrides": {"desconocida": True}},
    {"plan": "Pro", "feature_overrides": {"analytics": "false"}},
    {"plan": "Pro", "feature_overrides": {}, "PLATFORM_ADMIN_IDS": []},
])
async def test_rechaza_perfil_invalido(consola, sample_client, datos):
    assert (await consola.put(f"/api/platform/clients/{sample_client.id}", json=datos)).status_code == 422
    assert sample_client.commercial_plan == "Basico"


async def test_uso_cuenta_exitos_aislados_y_respeta_retencion(consola, db_session, sample_client):
    ruta = f"/api/platform/clients/{sample_client.id}"
    assert (await consola.get("/api/analytics/support-summary")).status_code == 403
    await consola.put(ruta, json={"plan": "Basico", "feature_overrides": {"analytics": True}})
    assert (await consola.get("/api/analytics/support-summary")).status_code == 200
    for cliente_id, fecha in [
        (uuid4(), datetime.now(timezone.utc)),
        (sample_client.id, datetime.now(timezone.utc) - timedelta(days=40)),
    ]:
        db_session.add(AuditLog(client_id=cliente_id, occurred_at=fecha, method="GET", path="/api/analytics",
                               status_code=200, outcome="SUCCESS", feature_flag="analytics"))
    await db_session.commit()
    uso = (await consola.get(ruta + "/usage?days=730")).json()
    assert uso["requests"] == {"analytics": 1, "audit_export": 0, "document_translation": 0}
    assert (await consola.get(ruta + "/usage?days=0")).status_code == 422


async def test_cliente_inexistente(consola):
    ruta = f"/api/platform/clients/{uuid4()}"
    assert (await consola.put(ruta, json={"plan": "Pro", "feature_overrides": {}})).status_code == 404
    assert (await consola.get(ruta + "/usage")).status_code == 404
    assert (await consola.get(ruta + "/changes")).status_code == 404


async def test_sin_sesion_no_accede():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as api:
        assert (await api.get("/api/platform/clients")).status_code == 401


def test_excepciones_no_habilitan_cliente_inactivo_o_plan_desconocido():
    assert not features_for("Pro", is_active=False, overrides={"analytics": True})
    assert not features_for("Otro", overrides={"analytics": True})


async def test_fallo_de_auditoria_revierte_el_plan(db_session, sample_client, sample_user, monkeypatch):
    from sqlalchemy import event
    from starlette.requests import Request

    from app.routers.platform import PerfilComercial, actualizar_perfil

    await db_session.commit()
    identificador = sample_client.id

    def rechazar(mapper, connection, target):
        raise RuntimeError("auditoria no disponible")

    event.listen(AuditLog, "before_insert", rechazar)
    try:
        with pytest.raises(RuntimeError, match="auditoria no disponible"):
            await actualizar_perfil(
                identificador, PerfilComercial(plan="Enterprise", feature_overrides={}),
                Request({"type": "http", "method": "PUT", "path": "/api/platform/clients/test", "headers": []}),
                sample_user, db_session,
            )
        await db_session.rollback()
        await db_session.refresh(sample_client)
        assert sample_client.commercial_plan == "Basico"
    finally:
        event.remove(AuditLog, "before_insert", rechazar)


def test_migracion_conserva_clientes_y_revierte():
    import importlib.util
    from pathlib import Path

    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import create_engine, text

    ruta = Path(__file__).parents[1] / "alembic/versions/e4a5b6c7d8e9_platform_plans.py"
    especificacion = importlib.util.spec_from_file_location("migracion", ruta)
    migracion = importlib.util.module_from_spec(especificacion)
    especificacion.loader.exec_module(migracion)
    motor = create_engine("sqlite:///:memory:")
    with motor.begin() as conexion:
        conexion.execute(text("ATTACH DATABASE ':memory:' AS audit"))
        conexion.execute(text("CREATE TABLE clients (id INTEGER PRIMARY KEY)"))
        conexion.execute(text("CREATE TABLE audit.audit_logs (id INTEGER PRIMARY KEY)"))
        conexion.execute(text("INSERT INTO clients (id) VALUES (1)"))
        with Operations.context(MigrationContext.configure(conexion)):
            migracion.upgrade()
            assert conexion.scalar(text("SELECT feature_overrides FROM clients")) == "{}"
            migracion.downgrade()
            assert conexion.scalar(text("SELECT id FROM clients")) == 1
    motor.dispose()
