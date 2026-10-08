"""
Circuito completo de auditoría contra PostgreSQL real (TRV-07 / TRV-08).

Lo que solo se puede comprobar aquí: que el middleware escribe de verdad al
atravesar la aplicación entera, que el trigger de inmutabilidad existe y
aborta, y que el gating comercial de la exportación responde por HTTP.
"""

import psycopg2
import pytest
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

from tests.integration.conftest import (
    DEFAULT_CLIENT_SLUG,
    DEV,
    TEST_DATABASE_URL,
    _sync_url,
)


def _consulta(sql: str, params: tuple = ()):
    conn = psycopg2.connect(_sync_url(TEST_DATABASE_URL))
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        return cur.fetchall()
    finally:
        conn.close()


def _ejecuta(sql: str, params: tuple = ()):
    conn = psycopg2.connect(_sync_url(TEST_DATABASE_URL))
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    try:
        conn.cursor().execute(sql, params)
    finally:
        conn.close()


def _set_plan(plan: str, slug: str = DEFAULT_CLIENT_SLUG) -> None:
    _ejecuta("UPDATE clients SET commercial_plan = %s WHERE slug = %s", (plan, slug))


# ---------------------------------------------------------------------------
# TRV-07 — el registro se escribe de verdad
# ---------------------------------------------------------------------------

async def test_una_mutacion_deja_entrada_con_todos_los_campos_del_criterio(
    client, leader_headers, epic, dev_id
):
    res = await client.post(
        "/api/tickets/",
        json={
            "epic_id": epic["id"],
            "title": "Ticket auditado",
            "priority": "LOW",
            "assignee_id": dev_id,
        },
        headers=leader_headers,
    )
    assert res.status_code == 201, res.text[:300]

    filas = _consulta(
        "SELECT actor_email, actor_role, method, path, route_template, status_code, "
        "outcome, occurred_at, request_id, client_id, duration_ms "
        "FROM audit.audit_logs WHERE path = '/api/tickets/' AND method = 'POST' "
        "ORDER BY occurred_at DESC LIMIT 1"
    )
    assert filas, "la creación de un ticket no dejó entrada de auditoría"
    (
        actor_email, actor_role, method, path, route_template,
        status_code, outcome, occurred_at, request_id, client_id, duration_ms,
    ) = filas[0]

    # Criterio 1 de TRV-07: usuario y rol, verbo y recurso, timestamp, resultado.
    assert actor_email and actor_role == "TEAM_LEADER"
    assert method == "POST"
    assert path == "/api/tickets/"
    assert route_template
    assert status_code == 201
    assert outcome == "SUCCESS"
    assert occurred_at is not None
    assert request_id, "el request_id debe correlacionar con los logs de aplicación"
    assert client_id is not None
    assert duration_ms is not None


async def test_el_evento_sale_tambien_por_stdout(client, leader_headers, epic, caplog):
    """
    Criterio 2 de TRV-07: el mismo evento tiene dos destinos. Sin esta línea,
    un colector externo no tendría nada que ingerir y la auditoría viviría solo
    en la base de datos.
    """
    import logging

    with caplog.at_level(logging.INFO, logger="corestream.audit.event"):
        res = await client.post(
            "/api/tickets/",
            json={"epic_id": epic["id"], "title": "Para stdout", "priority": "LOW"},
            headers=leader_headers,
        )
        assert res.status_code == 201

    eventos = [
        r for r in caplog.records
        if r.name == "corestream.audit.event" and getattr(r, "audit", None)
    ]
    assert eventos, "el evento de auditoría no se emitió al log"

    evento = eventos[-1].audit
    assert evento["method"] == "POST"
    assert evento["path"] == "/api/tickets/"
    assert evento["outcome"] == "SUCCESS"
    assert evento["actor_role"] == "TEAM_LEADER"
    assert evento["request_id"]


async def test_el_contexto_sigue_vivo_mientras_se_registra(client, leader_headers, epic):
    """
    El reset del contexto va DESPUÉS de registrar. Si se hiciera antes, el
    logger.exception de una escritura fallida saldría sin actor ni cliente —
    justo cuando hace falta saber de quién era el evento que se perdió.
    """
    from app.context import get_audit_bucket
    from app.services.audit_sinks import build_default_sink, set_audit_sink

    visto: dict = {}
    real = build_default_sink()

    class Espia:
        name = "espia"

        async def emit(self, entry):
            bucket = get_audit_bucket()
            visto["bucket_vivo"] = bucket is not None
            visto["actor"] = (bucket or {}).get("actor_email")
            await real.emit(entry)

    set_audit_sink(Espia())
    try:
        res = await client.post(
            "/api/tickets/",
            json={"epic_id": epic["id"], "title": "Espiando contexto", "priority": "LOW"},
            headers=leader_headers,
        )
        assert res.status_code == 201
    finally:
        set_audit_sink(None)

    assert visto["bucket_vivo"] is True
    assert visto["actor"], "el actor debe estar disponible al escribir la entrada"
    assert get_audit_bucket() is None, "y el contexto debe quedar limpio al terminar"


async def test_un_fallo_de_auditoria_no_tumba_la_peticion(client, leader_headers, epic):
    """
    El CompositeSink aísla y no propaga, y el middleware captura por si acaso:
    dos redes, porque un sink sustituido en el futuro podría no aislar.
    """
    from app.services.audit_sinks import set_audit_sink

    class Rota:
        name = "rota"

        async def emit(self, entry):
            raise RuntimeError("fallo simulado de escritura")

    set_audit_sink(Rota())
    try:
        res = await client.post(
            "/api/tickets/",
            json={"epic_id": epic["id"], "title": "Auditoría caída", "priority": "LOW"},
            headers=leader_headers,
        )
    finally:
        set_audit_sink(None)

    assert res.status_code == 201, (
        "dejar la API fuera de servicio porque la auditoría no está disponible "
        "no es un comportamiento exigido por TRV-07"
    )


async def test_el_recurso_creado_queda_identificado(client, leader_headers, epic, dev_id):
    """
    "Recurso afectado" del criterio 1. En una creación no hay parámetro de
    ruta del que extraer el id, así que sin que el handler lo declare el
    registro diría qué colección se tocó pero no cuál objeto nació.
    """
    res = await client.post(
        "/api/tickets/",
        json={
            "epic_id": epic["id"],
            "title": "Ticket identificado",
            "priority": "LOW",
            "assignee_id": dev_id,
        },
        headers=leader_headers,
    )
    assert res.status_code == 201
    creado = res.json()["id"]

    filas = _consulta(
        "SELECT resource_type, resource_id FROM audit.audit_logs "
        "WHERE method = 'POST' AND path = '/api/tickets/' "
        "ORDER BY occurred_at DESC LIMIT 1"
    )
    assert filas
    resource_type, resource_id = filas[0]
    assert resource_type == "ticket"
    assert str(resource_id) == creado


async def test_el_auditor_lee_pero_no_administra(client, admin_headers):
    """
    El rol existe para no tener que dar ADMIN a quien solo debe leer: un
    AUDITOR consulta la auditoría y no puede tocar usuarios ni tickets.
    """
    invitacion = await client.post(
        "/api/invitations/", json={"email": "auditor@x.com", "role": "AUDITOR"},
        headers=admin_headers,
    )
    assert invitacion.status_code == 201, invitacion.text[:300]

    aceptar = await client.post(
        f"/api/invitations/{invitacion.json()['token']}/accept",
        json={"full_name": "Auditora Externa", "password": "AuditPass123!@#"},
    )
    assert aceptar.status_code in (200, 201), aceptar.text[:300]

    login = await client.post(
        "/api/auth/login",
        json={"email": "auditor@x.com", "password": "AuditPass123!@#"},
    )
    assert login.status_code == 200, login.text[:300]
    auditor = {"Authorization": f"Bearer {login.json()['access_token']}"}

    _set_plan("Pro")
    assert (await client.get("/api/audit-logs/", headers=auditor)).status_code == 200

    # Y nada más: no administra usuarios ni construye estructura.
    assert (await client.get("/api/users/", headers=auditor)).status_code == 403
    assert (
        await client.post(
            "/api/applications/",
            json={"name": "No deberia", "color": "#000000", "icon": "x"},
            headers=auditor,
        )
    ).status_code == 403


async def test_no_se_asigna_un_ticket_a_un_auditor(client, admin_headers, leader_headers, epic):
    """Rol de solo lectura: no ejecuta trabajo, así que no recibe tickets."""
    invitacion = await client.post(
        "/api/invitations/", json={"email": "auditor2@x.com", "role": "AUDITOR"},
        headers=admin_headers,
    )
    await client.post(
        f"/api/invitations/{invitacion.json()['token']}/accept",
        json={"full_name": "Auditor Dos", "password": "AuditPass123!@#"},
    )
    login = await client.post(
        "/api/auth/login",
        json={"email": "auditor2@x.com", "password": "AuditPass123!@#"},
    )
    auditor_id = (await client.get("/api/auth/me", headers={
        "Authorization": f"Bearer {login.json()['access_token']}"
    })).json()["id"]

    res = await client.post(
        "/api/tickets/",
        json={
            "epic_id": epic["id"], "title": "Para un auditor",
            "priority": "LOW", "assignee_id": auditor_id,
        },
        headers=leader_headers,
    )
    assert res.status_code == 400
    assert "AUDITOR" in res.text


async def test_el_login_fallido_registra_el_email_intentado(client):
    res = await client.post(
        "/api/auth/login",
        json={"email": "intruso@ninguna-parte.com", "password": "loquesea"},
    )
    assert res.status_code == 401

    filas = _consulta(
        "SELECT actor_email, outcome, actor_user_id FROM audit.audit_logs "
        "WHERE path = '/api/auth/login' ORDER BY occurred_at DESC LIMIT 1"
    )
    assert filas
    actor_email, outcome, actor_user_id = filas[0]
    assert actor_email == "intruso@ninguna-parte.com"
    assert outcome == "DENIED"
    assert actor_user_id is None


async def test_el_login_correcto_registra_al_usuario_resuelto(client):
    res = await client.post(
        "/api/auth/login", json={"email": DEV["email"], "password": DEV["password"]}
    )
    assert res.status_code == 200

    filas = _consulta(
        "SELECT actor_email, actor_role, outcome, actor_user_id, client_id "
        "FROM audit.audit_logs WHERE path = '/api/auth/login' "
        "ORDER BY occurred_at DESC LIMIT 1"
    )
    actor_email, actor_role, outcome, actor_user_id, client_id = filas[0]
    assert actor_email == DEV["email"]
    assert actor_role == "DEVELOPER"
    assert outcome == "SUCCESS"
    assert actor_user_id is not None
    assert client_id is not None


async def test_un_acceso_denegado_en_lectura_queda_registrado(client, dev_headers):
    """Un DEVELOPER no entra a la gestión de usuarios: ese 403 es auditable."""
    res = await client.get("/api/users/", headers=dev_headers)
    assert res.status_code == 403

    filas = _consulta(
        "SELECT method, outcome, status_code FROM audit.audit_logs "
        "WHERE path = '/api/users/' ORDER BY occurred_at DESC LIMIT 1"
    )
    assert filas
    method, outcome, status_code = filas[0]
    assert method == "GET"
    assert outcome == "DENIED"
    assert status_code == 403


async def test_una_lectura_con_exito_tambien_se_registra(client, leader_headers, epic):
    """
    "Todo evento de la plataforma" (descripción de TRV-07): con AUDIT_READS
    activado —el valor por defecto— quién consultó qué también queda, no solo
    quién modificó. Es lo que pide una auditoría de acceso a datos.
    """
    res = await client.get(f"/api/epics/{epic['id']}", headers=leader_headers)
    assert res.status_code == 200

    filas = _consulta(
        "SELECT method, outcome, resource_id, actor_role FROM audit.audit_logs "
        "WHERE path = %s ORDER BY occurred_at DESC LIMIT 1",
        (f"/api/epics/{epic['id']}",),
    )
    assert filas, "una lectura con éxito debe dejar entrada"
    method, outcome, resource_id, actor_role = filas[0]
    assert method == "GET"
    assert outcome == "SUCCESS"
    assert str(resource_id) == epic["id"]
    assert actor_role == "TEAM_LEADER"


async def test_las_sondas_de_salud_no_se_auditan(client):
    antes = _consulta("SELECT count(*) FROM audit.audit_logs")[0][0]
    assert (await client.get("/api/health")).status_code in (200, 503)
    assert (await client.get("/health")).status_code == 200
    assert _consulta("SELECT count(*) FROM audit.audit_logs")[0][0] == antes


async def test_el_recurso_afectado_se_extrae_de_la_ruta(client, leader_headers, ticket):
    res = await client.put(
        f"/api/tickets/{ticket['id']}",
        json={"title": "Título auditado"},
        headers=leader_headers,
    )
    assert res.status_code == 200, res.text[:300]

    filas = _consulta(
        "SELECT resource_id FROM audit.audit_logs WHERE method = 'PUT' "
        "AND path LIKE '/api/tickets/%%' ORDER BY occurred_at DESC LIMIT 1"
    )
    assert filas and str(filas[0][0]) == ticket["id"]


# ---------------------------------------------------------------------------
# TRV-07 — inmutabilidad impuesta por la base de datos
# ---------------------------------------------------------------------------

async def test_el_registro_es_inmutable_a_nivel_de_postgres(client, leader_headers, epic):
    res = await client.post(
        "/api/tickets/",
        json={"epic_id": epic["id"], "title": "Para inmutabilidad", "priority": "LOW"},
        headers=leader_headers,
    )
    assert res.status_code == 201

    with pytest.raises(psycopg2.errors.RaiseException):
        _ejecuta("UPDATE audit.audit_logs SET actor_email = 'falsificado@x.com'")


async def test_un_borrado_suelto_queda_bloqueado(client, leader_headers, epic):
    """
    La app y cualquier sesión de psql comparten credenciales, así que la
    inmutabilidad no puede depender de que nadie escriba un DELETE por error:
    el trigger lo bloquea salvo que la sesión declare que es la purga.
    """
    res = await client.post(
        "/api/tickets/",
        json={"epic_id": epic["id"], "title": "Para borrado", "priority": "LOW"},
        headers=leader_headers,
    )
    assert res.status_code == 201

    with pytest.raises(psycopg2.errors.RaiseException):
        _ejecuta("DELETE FROM audit.audit_logs")


async def test_la_purga_autorizada_si_puede_borrar(client, leader_headers, epic):
    """
    El contrapunto del test anterior: con la marca de sesión puesta, el borrado
    pasa. Si no, la retención de TRV-08 quedaría bloqueada por su propio
    mecanismo de protección.
    """
    res = await client.post(
        "/api/tickets/",
        json={"epic_id": epic["id"], "title": "Para purga", "priority": "LOW"},
        headers=leader_headers,
    )
    assert res.status_code == 201
    assert _consulta("SELECT count(*) FROM audit.audit_logs")[0][0] > 0

    _ejecuta(
        "BEGIN; SET LOCAL corestream.audit_purge = 'on'; "
        "DELETE FROM audit.audit_logs; COMMIT;"
    )
    assert _consulta("SELECT count(*) FROM audit.audit_logs")[0][0] == 0


async def test_la_purga_del_servicio_funciona_contra_postgres(client, leader_headers, epic):
    """
    purge_expired() sobre PostgreSQL real, con los triggers puestos: es el
    único sitio donde se comprueba que la autorización de sesión que fija el
    servicio es la que el trigger espera. Los tests unitarios corren en SQLite,
    donde no hay ni GUC ni triggers.
    """
    from datetime import datetime, timedelta, timezone

    from app.database import get_session_maker
    from app.services import audit_service

    res = await client.post(
        "/api/tickets/",
        json={"epic_id": epic["id"], "title": "Para purga real", "priority": "LOW"},
        headers=leader_headers,
    )
    assert res.status_code == 201

    # Envejecer la entrada más allá de cualquier retención.
    _ejecuta(
        "UPDATE clients SET commercial_plan = 'Basico' WHERE slug = %s",
        (DEFAULT_CLIENT_SLUG,),
    )
    antiguo = datetime.now(timezone.utc) - timedelta(days=900)
    # El trigger bloquea UPDATE sobre audit_logs, así que se reinserta en vez
    # de modificar: es exactamente la garantía que se quiere.
    _ejecuta(
        "BEGIN; SET LOCAL corestream.audit_purge = 'on'; "
        "DELETE FROM audit.audit_logs; COMMIT;"
    )
    _ejecuta(
        "INSERT INTO audit.audit_logs "
        "(id, client_id, occurred_at, method, path, status_code, outcome) "
        "SELECT gen_random_uuid(), id, %s, 'POST', '/api/viejo', 201, 'SUCCESS' "
        "FROM clients WHERE slug = %s",
        (antiguo, DEFAULT_CLIENT_SLUG),
    )
    assert _consulta("SELECT count(*) FROM audit.audit_logs")[0][0] == 1

    async with get_session_maker()() as db:
        borradas = await audit_service.purge_expired(db)

    assert sum(borradas.values()) == 1
    assert _consulta("SELECT count(*) FROM audit.audit_logs")[0][0] == 0


# ---------------------------------------------------------------------------
# TRV-08 — consulta, profundidad y exportación
# ---------------------------------------------------------------------------

async def test_solo_admin_consulta_el_registro(client, dev_headers, leader_headers):
    for headers in (dev_headers, leader_headers):
        assert (await client.get("/api/audit-logs/", headers=headers)).status_code == 403


async def test_el_admin_consulta_y_recibe_su_retencion(client, admin_headers):
    _set_plan("Pro")
    res = await client.get("/api/audit-logs/", headers=admin_headers)
    assert res.status_code == 200, res.text[:300]

    cuerpo = res.json()
    assert cuerpo["retention_days"] == 180
    assert isinstance(cuerpo["items"], list)
    assert cuerpo["total"] >= 0


async def test_la_consulta_solo_devuelve_el_propio_cliente(
    client, admin_headers, admin_b_headers
):
    _set_plan("Pro")
    await client.post("/api/auth/login", json={"email": "x@y.z", "password": "mala"})

    propios = (await client.get("/api/audit-logs/?limit=200", headers=admin_headers)).json()
    ajenos = (await client.get("/api/audit-logs/?limit=200", headers=admin_b_headers)).json()

    ids_propios = {item["id"] for item in propios["items"]}
    ids_ajenos = {item["id"] for item in ajenos["items"]}
    assert not (ids_propios & ids_ajenos)


async def test_el_filtro_por_outcome_acota(client, admin_headers, dev_headers):
    _set_plan("Pro")
    await client.get("/api/users/", headers=dev_headers)  # genera un DENIED

    res = await client.get("/api/audit-logs/?outcome=DENIED&limit=200", headers=admin_headers)
    assert res.status_code == 200
    assert all(item["outcome"] == "DENIED" for item in res.json()["items"])


@pytest.mark.parametrize("plan", ["Basico", "Pro"])
async def test_la_exportacion_se_niega_sin_plan_enterprise(client, admin_headers, plan):
    _set_plan(plan)
    res = await client.get("/api/audit-logs/export?format=csv", headers=admin_headers)
    assert res.status_code == 403
    detalle = res.json()["detail"]
    assert detalle["code"] == "FEATURE_NOT_INCLUDED"
    assert detalle["feature_flag"] == "audit_export"


async def test_enterprise_exporta_en_csv(client, admin_headers, leader_headers, epic):
    await client.post(
        "/api/tickets/",
        json={"epic_id": epic["id"], "title": "Para exportar", "priority": "LOW"},
        headers=leader_headers,
    )
    _set_plan("Enterprise")

    res = await client.get("/api/audit-logs/export?format=csv", headers=admin_headers)
    assert res.status_code == 200, res.text[:300]
    assert res.headers["content-type"].startswith("text/csv")
    assert "attachment" in res.headers["content-disposition"]

    lineas = res.text.strip().splitlines()
    assert lineas[0].startswith("occurred_at,request_id,actor_user_id")
    assert len(lineas) > 1


async def test_enterprise_exporta_en_jsonl(client, admin_headers, leader_headers, epic):
    import json

    await client.post(
        "/api/tickets/",
        json={"epic_id": epic["id"], "title": "Para exportar jsonl", "priority": "LOW"},
        headers=leader_headers,
    )
    _set_plan("Enterprise")

    res = await client.get("/api/audit-logs/export?format=jsonl", headers=admin_headers)
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("application/x-ndjson")

    primera = json.loads(res.text.strip().splitlines()[0])
    assert "occurred_at" in primera and "outcome" in primera


async def test_la_exportacion_se_audita_a_si_misma(client, admin_headers):
    _set_plan("Enterprise")
    assert (
        await client.get("/api/audit-logs/export?format=csv", headers=admin_headers)
    ).status_code == 200

    filas = _consulta(
        "SELECT resource_type, outcome, actor_role FROM audit.audit_logs "
        "WHERE path = '/api/audit-logs/export' ORDER BY occurred_at DESC LIMIT 1"
    )
    assert filas, "una extracción completa del historial debe quedar registrada"
    resource_type, outcome, actor_role = filas[0]
    assert resource_type == "audit_export"
    assert outcome == "SUCCESS"
    assert actor_role == "ADMIN"


async def test_el_perfil_comercial_publica_la_retencion(client, admin_headers):
    _set_plan("Enterprise")
    res = await client.get("/api/auth/commercial-profile", headers=admin_headers)
    assert res.status_code == 200

    perfil = res.json()
    assert perfil["plan"] == "Enterprise"
    assert perfil["audit_retention_days"] == 730
    assert perfil["feature_flags"]["audit_export"] is True
    assert perfil["feature_flags"]["audit_log"] is True


async def test_la_exportacion_denegada_tambien_queda_registrada(client, admin_headers):
    _set_plan("Basico")
    assert (
        await client.get("/api/audit-logs/export?format=csv", headers=admin_headers)
    ).status_code == 403

    filas = _consulta(
        "SELECT outcome, status_code FROM audit.audit_logs "
        "WHERE path = '/api/audit-logs/export' ORDER BY occurred_at DESC LIMIT 1"
    )
    assert filas and filas[0] == ("DENIED", 403)
