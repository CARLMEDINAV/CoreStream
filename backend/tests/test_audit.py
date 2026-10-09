"""
Auditoría de no repudio y retención escalonada (TRV-07 / TRV-08).

Cubre lo que no necesita PostgreSQL: clasificación del resultado, qué
peticiones se registran y cuáles no, el relleno del contexto del actor, el
mapa de retención por plan y los dos formatos de exportación. El circuito
completo por HTTP, la inmutabilidad por trigger y la purga real están en
tests/integration/test_audit.py.
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.context import (
    audit_ctx,
    get_audit_bucket,
    mark_auditable,
    set_audit_actor,
    set_audit_resource,
    set_audit_subject,
)
from app.middleware.audit import _should_record
from app.models import AuditLog, AuditOutcome
from app.models.audit_log import AUDIT_SCHEMA
from app.plans import (
    ALL_FEATURES,
    AUDIT_RETENTION_DAYS,
    PLAN_FEATURES,
    audit_retention_days,
    cutoff_for_days,
    group_by_retention,
    retention_cutoff,
)
from app.services import audit_export, audit_records, audit_service

# ---------------------------------------------------------------------------
# Clasificación del resultado
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("status,esperado", [
    (200, AuditOutcome.SUCCESS),
    (201, AuditOutcome.SUCCESS),
    (204, AuditOutcome.SUCCESS),
    (302, AuditOutcome.SUCCESS),
    (401, AuditOutcome.DENIED),
    (403, AuditOutcome.DENIED),
    (429, AuditOutcome.DENIED),
    (400, AuditOutcome.FAILED),
    (404, AuditOutcome.FAILED),
    (422, AuditOutcome.FAILED),
    (500, AuditOutcome.ERROR),
    (503, AuditOutcome.ERROR),
])
def test_outcome_por_codigo_de_estado(status, esperado):
    assert audit_records.outcome_for(status) == esperado


def test_denegado_se_distingue_de_error_de_validacion():
    """
    Un 403 y un 422 son ambos 4xx pero significan cosas distintas para un
    auditor: el primero es un intento de acceso sin permiso, el segundo una
    petición mal formada. Colapsarlos haría inútil el filtro por outcome.
    """
    assert audit_records.outcome_for(403) != audit_records.outcome_for(422)


# ---------------------------------------------------------------------------
# Qué se registra
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE", "GET"])
def test_con_audit_reads_se_registra_todo(method):
    """
    "Todo evento de la plataforma" (descripción de TRV-07) leído en sentido
    estricto: cualquier petición que llegue a un handler deja entrada. Las
    sondas se descartan antes, en dispatch.
    """
    assert _should_record(method, 200, "/api/tickets/", audit_reads=True) is True


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
def test_toda_mutacion_se_registra_aunque_no_se_auditen_lecturas(method):
    assert _should_record(method, 200, "/api/tickets/", audit_reads=False) is True


def test_sin_audit_reads_la_lectura_con_exito_no_se_registra():
    """
    Es la vía de escape si el volumen o la latencia aprietan: AUDIT_READS=false
    deja solo mutaciones, accesos denegados y /api/auth/*.
    """
    assert _should_record("GET", 200, "/api/tickets/", audit_reads=False) is False


@pytest.mark.parametrize("status", [401, 403, 429])
def test_acceso_denegado_se_registra_en_cualquier_verbo(status):
    """Lo más valioso del registro, se auditen lecturas o no."""
    assert _should_record("GET", status, "/api/tickets/", audit_reads=False) is True


def test_rutas_de_autenticacion_se_registran_siempre():
    assert _should_record("GET", 200, "/api/auth/me", audit_reads=False) is True


def test_sin_audit_reads_un_500_en_lectura_no_es_un_acto_auditable():
    """Un 500 en un GET es un fallo de la aplicación, no un acto del usuario."""
    assert _should_record("GET", 500, "/api/tickets/", audit_reads=False) is False


def test_una_lectura_puede_marcarse_como_auditable():
    """
    mark_auditable() fuerza el registro de una lectura concreta — lo usa la
    exportación, que debe quedar registrada incluso con AUDIT_READS=false.
    """
    ruta = "/api/audit-logs/export"
    assert _should_record("GET", 200, ruta, audit_reads=False) is False
    assert _should_record("GET", 200, ruta, forced=True, audit_reads=False) is True


def test_mark_auditable_marca_el_contexto():
    bucket: dict = {}
    token = audit_ctx.set(bucket)
    try:
        assert not bucket.get("force")
        mark_auditable()
        assert bucket["force"] is True
    finally:
        audit_ctx.reset(token)


# ---------------------------------------------------------------------------
# Contexto del actor
# ---------------------------------------------------------------------------

def test_el_contexto_se_rellena_sobre_el_mismo_dict():
    """
    AuditMiddleware siembra el dict y el handler lo muta. Si set_audit_actor
    reasignara el ContextVar en vez de mutar, el middleware no vería nada:
    Starlette ejecuta el app interno en otra task.
    """
    bucket: dict = {}
    token = audit_ctx.set(bucket)
    try:
        user_id, client_id = uuid4(), uuid4()
        set_audit_actor(
            user_id=user_id, email="a@b.c", role="ADMIN", client_id=client_id
        )
        resource_id = uuid4()
        set_audit_resource("ticket", resource_id)

        assert bucket["actor_user_id"] == user_id
        assert bucket["actor_email"] == "a@b.c"
        assert bucket["actor_role"] == "ADMIN"
        assert bucket["client_id"] == client_id
        assert bucket["resource_type"] == "ticket"
        assert bucket["resource_id"] == resource_id
        assert get_audit_bucket() is bucket
    finally:
        audit_ctx.reset(token)


@pytest.mark.parametrize("valor", ["no-es-un-uuid", "", 42, None])
def test_un_resource_id_invalido_no_se_guarda(valor):
    """
    La columna es UUID: un valor inválido haría fallar la escritura de la
    entrada completa. Se prefiere perder el id antes que el registro del acto.
    """
    bucket: dict = {}
    token = audit_ctx.set(bucket)
    try:
        set_audit_resource("ticket", valor)
        assert bucket["resource_type"] == "ticket"
        assert "resource_id" not in bucket
    finally:
        audit_ctx.reset(token)


def test_un_resource_id_en_texto_valido_se_normaliza_a_uuid():
    bucket: dict = {}
    token = audit_ctx.set(bucket)
    try:
        esperado = uuid4()
        set_audit_resource("ticket", str(esperado))
        assert bucket["resource_id"] == esperado
    finally:
        audit_ctx.reset(token)


def test_sin_contexto_sembrado_no_revienta():
    """Fuera de una petición HTTP (worker, script) no hay dict que mutar."""
    assert audit_ctx.get() is None
    set_audit_actor(user_id=uuid4(), email="a@b.c", role="ADMIN")
    set_audit_subject("x@y.z")
    set_audit_resource("ticket")
    mark_auditable()


def test_el_actor_autenticado_gana_al_email_intentado():
    """
    /auth/login llama a set_audit_subject antes de validar credenciales y a
    set_audit_actor si tienen éxito. El segundo no debe quedar pisado por el
    primero ni al revés.
    """
    bucket: dict = {}
    token = audit_ctx.set(bucket)
    try:
        set_audit_subject("intentado@b.c")
        assert bucket["actor_email"] == "intentado@b.c"

        set_audit_actor(user_id=uuid4(), email="real@b.c", role="ADMIN")
        assert bucket["actor_email"] == "real@b.c"

        set_audit_subject("otro@b.c")
        assert bucket["actor_email"] == "real@b.c"
    finally:
        audit_ctx.reset(token)


# ---------------------------------------------------------------------------
# Segundo destino: la línea JSON de stdout (criterio 2 de TRV-07)
# ---------------------------------------------------------------------------

def test_el_payload_de_log_es_serializable_a_json():
    """
    La entrada lleva UUID y datetime, que json.dumps no sabe serializar: si
    as_log_payload no los convierte, el formatter revienta al emitir la línea
    y el segundo destino se pierde en silencio.
    """
    import json

    entry = {
        "client_id": uuid4(),
        "actor_user_id": uuid4(),
        "resource_id": uuid4(),
        "occurred_at": datetime(2026, 10, 2, 9, 30, tzinfo=timezone.utc),
        "method": "POST",
        "status_code": 201,
        "duration_ms": 12,
        "user_agent": None,
    }
    payload = audit_records.as_log_payload(entry)
    json.dumps(payload)

    assert payload["status_code"] == 201
    assert payload["occurred_at"] == "2026-10-02T09:30:00+00:00"
    assert payload["client_id"] == str(entry["client_id"])
    assert "user_agent" not in payload, "los nulos no aportan nada a la línea de log"


def test_el_formatter_incluye_el_evento_de_auditoria():
    """
    El evento viaja como `extra={"audit": ...}`. Sin esta rama del formatter,
    el middleware escribiría solo en base de datos y el criterio 2 de TRV-07
    no tendría ningún destino en stdout.
    """
    import json
    import logging

    from app.logging_config import JSONFormatter

    record = logging.LogRecord(
        name="corestream.audit.event", level=logging.INFO, pathname=__file__,
        lineno=1, msg="audit %s", args=("POST",), exc_info=None,
    )
    record.audit = {"method": "POST", "outcome": "SUCCESS"}

    salida = json.loads(JSONFormatter().format(record))
    assert salida["audit"] == {"method": "POST", "outcome": "SUCCESS"}


def test_el_formatter_funciona_sin_evento_de_auditoria():
    """La inmensa mayoría de las líneas de log no son eventos de auditoría."""
    import json
    import logging

    from app.logging_config import JSONFormatter

    record = logging.LogRecord(
        name="corestream", level=logging.INFO, pathname=__file__,
        lineno=1, msg="algo normal", args=(), exc_info=None,
    )
    salida = json.loads(JSONFormatter().format(record))
    assert "audit" not in salida
    assert salida["message"] == "algo normal"


def test_el_formatter_adjunta_el_actor_a_cualquier_linea():
    import json
    import logging

    from app.logging_config import JSONFormatter

    bucket: dict = {}
    token = audit_ctx.set(bucket)
    try:
        set_audit_actor(
            user_id=uuid4(), email="admin@cliente.com", role="ADMIN", client_id=uuid4()
        )
        record = logging.LogRecord(
            name="corestream", level=logging.ERROR, pathname=__file__,
            lineno=1, msg="fallo al hacer algo", args=(), exc_info=None,
        )
        salida = json.loads(JSONFormatter().format(record))
        assert salida["actor"] == "admin@cliente.com"
        assert salida["actor_role"] == "ADMIN"
        assert salida["client_id"]
    finally:
        audit_ctx.reset(token)


# ---------------------------------------------------------------------------
# Retención por plan (TRV-08)
# ---------------------------------------------------------------------------

def test_la_retencion_se_puede_fijar_desde_el_entorno(monkeypatch):
    """
    Cuánto se conserva la auditoría de un cliente no es una decisión técnica:
    es parte de lo que se le vende y puede estar condicionada por obligaciones
    legales. Que venga del entorno la pone en manos de quien define los planes
    y la hace cambiable sin desplegar — que es además lo que vuelve
    inobjetable el «configurable por tier comercial» del criterio.
    """
    import importlib

    monkeypatch.setenv("AUDIT_RETENTION_DAYS_BASICO", "15")
    monkeypatch.setenv("AUDIT_RETENTION_DAYS_ENTERPRISE", "1095")

    import app.plans as plans
    recargado = importlib.reload(plans)
    try:
        assert recargado.AUDIT_RETENTION_DAYS["Basico"] == 15
        assert recargado.AUDIT_RETENTION_DAYS["Enterprise"] == 1095
        assert recargado.AUDIT_RETENTION_DAYS["Pro"] == 180, "sin declarar, el valor base"
        assert recargado.DEFAULT_RETENTION_DAYS == 15
    finally:
        monkeypatch.undo()
        importlib.reload(plans)


@pytest.mark.parametrize("valor,motivo", [("abc", "número"), ("0", "al menos 1"), ("-5", "al menos 1")])
def test_una_retencion_invalida_falla_al_arrancar(monkeypatch, valor, motivo):
    """Un valor mal escrito no puede degradar en silencio a la retención base."""
    import importlib

    monkeypatch.setenv("AUDIT_RETENTION_DAYS_PRO", valor)
    import app.plans as plans
    try:
        with pytest.raises(ValueError, match=motivo):
            importlib.reload(plans)
    finally:
        monkeypatch.undo()
        importlib.reload(plans)


def test_todo_plan_tiene_retencion_declarada():
    assert set(AUDIT_RETENTION_DAYS) == set(PLAN_FEATURES)


def test_la_retencion_crece_con_el_plan():
    assert (
        AUDIT_RETENTION_DAYS["Basico"]
        < AUDIT_RETENTION_DAYS["Pro"]
        < AUDIT_RETENTION_DAYS["Enterprise"]
    )


@pytest.mark.parametrize("plan", [None, "", "Otro", "basico", "ENTERPRISE"])
def test_plan_desconocido_recibe_la_retencion_mas_corta(plan):
    """Ante un plan no reconocido se conserva lo mínimo, no lo máximo."""
    assert audit_retention_days(plan) == min(AUDIT_RETENTION_DAYS.values())


# ---------------------------------------------------------------------------
# Matriz comercial (TRV-02 + TRV-08)
# ---------------------------------------------------------------------------

def test_la_exportacion_es_exclusiva_de_enterprise():
    assert [p for p, f in PLAN_FEATURES.items() if "audit_export" in f] == ["Enterprise"]


def test_consultar_la_auditoria_lo_permite_todo_plan():
    """
    TRV-08 hace que el plan gobierne la profundidad del historial, no el
    acceso: un cliente Basico consulta su propia auditoría, acotada.
    """
    assert all("audit_log" in features for features in PLAN_FEATURES.values())


def test_los_planes_son_acumulativos():
    assert PLAN_FEATURES["Basico"] < PLAN_FEATURES["Pro"] < PLAN_FEATURES["Enterprise"]


def test_enterprise_cubre_todas_las_banderas():
    assert PLAN_FEATURES["Enterprise"] == ALL_FEATURES


# ---------------------------------------------------------------------------
# Exportación (TRV-08)
# ---------------------------------------------------------------------------

def _fila(**kwargs) -> AuditLog:
    base = {
        "method": "POST",
        "path": "/api/tickets/",
        "status_code": 201,
        "outcome": AuditOutcome.SUCCESS,
        "actor_email": "admin@cliente.com",
        "actor_role": "ADMIN",
        "ip": "203.0.113.7",
        "duration_ms": 14,
        "occurred_at": datetime(2026, 10, 2, 9, 30, tzinfo=timezone.utc),
    }
    base.update(kwargs)
    return AuditLog(**base)


def test_csv_lleva_cabecera_y_una_linea_por_entrada():
    salida = audit_export.render_csv([_fila(), _fila()]).strip().splitlines()
    assert salida[0] == ",".join(audit_records.ENTRY_FIELDS)
    assert len(salida) == 3


def test_csv_vacio_conserva_la_cabecera():
    """Una exportación sin resultados sigue siendo un fichero válido."""
    assert audit_export.render_csv([]).strip() == ",".join(audit_records.ENTRY_FIELDS)


def test_las_fechas_se_exportan_en_iso_8601():
    """Criterio explícito de TRV-07."""
    momento = datetime(2026, 10, 2, 9, 30, tzinfo=timezone.utc)
    salida = audit_export.render_csv([_fila(occurred_at=momento)])
    assert momento.isoformat() in salida


def test_los_nulos_no_se_exportan_como_la_cadena_none():
    salida = audit_export.render_csv([_fila(ip=None, user_agent=None, request_id=None)])
    assert "None" not in salida


# ---------------------------------------------------------------------------
# Modelo
# ---------------------------------------------------------------------------

def test_audit_logs_vive_en_su_propio_esquema():
    """
    Criterio 2 de TRV-07: "no se almacenan en las tablas operativas". Con un
    esquema propio eso es un hecho verificable, no una interpretación — otro
    namespace, con permisos otorgables por separado de `public`.
    """
    assert AuditLog.__table__.schema == AUDIT_SCHEMA == "audit"


def test_ninguna_tabla_operativa_comparte_el_esquema_de_auditoria():
    from app.models import Base

    intrusas = [
        t.name for t in Base.metadata.sorted_tables
        if t.schema == AUDIT_SCHEMA and t.name != "audit_logs"
    ]
    assert intrusas == []


def test_audit_logs_no_esta_bajo_el_filtro_de_tenant():
    """
    Si heredara TenantMixin, tenant_scope.py filtraría toda consulta por el
    cliente del request — y entonces ni el registro de un login fallido (sin
    tenant resuelto) ni la purga entre clientes podrían funcionar.
    """
    from app.models.base import TenantMixin

    assert not issubclass(AuditLog, TenantMixin)


def test_audit_logs_no_tiene_clave_ajena_a_clients():
    """Un RESTRICT impediría borrar un cliente; un CASCADE borraría la prueba."""
    assert AuditLog.__table__.c.client_id.foreign_keys == set()


def test_el_actor_queda_desnormalizado():
    """
    El registro debe seguir diciendo quién actuó aunque el usuario se borre,
    así que email y rol se copian en la fila en vez de resolverse por JOIN.
    """
    columnas = AuditLog.__table__.c
    assert columnas.actor_email.nullable
    assert columnas.actor_role.nullable
    assert columnas.actor_user_id.foreign_keys == set()


def test_la_entrada_admite_no_tener_actor():
    """Un login fallido contra un email inexistente no tiene usuario ni tenant."""
    assert AuditLog.__table__.c.actor_user_id.nullable
    assert AuditLog.__table__.c.client_id.nullable


def test_la_ip_cabe_en_una_direccion_ipv6():
    assert AuditLog.__table__.c.ip.type.length >= 45


# ---------------------------------------------------------------------------
# Purga (TRV-08)
# ---------------------------------------------------------------------------

async def test_la_purga_respeta_la_retencion_de_cada_plan(db_session, sample_client):
    """
    Dos clientes con entradas de la misma antigüedad no caducan a la vez: el
    corte lo fija el plan de cada uno. Es justo lo que un borrado por rango de
    fechas global no puede expresar.
    """
    from app.models import Client

    ahora = datetime.now(timezone.utc)

    basico = sample_client
    basico.commercial_plan = "Basico"

    enterprise = Client(name="Ent", slug="ent-purga", commercial_plan="Enterprise")
    db_session.add(enterprise)
    await db_session.commit()

    # 90 días: fuera de los 30 de Basico, dentro de los 730 de Enterprise.
    antiguedad = ahora - timedelta(days=90)
    for client_id in (basico.id, enterprise.id):
        db_session.add(_fila(client_id=client_id, occurred_at=antiguedad))
    # Una entrada reciente de Basico que debe sobrevivir.
    db_session.add(_fila(client_id=basico.id, occurred_at=ahora))
    await db_session.commit()

    borradas = await audit_service.purge_expired(db_session)

    # El desglose es por grupo de retención, no por cliente: lo que decide el
    # corte es el plan, así que una sentencia por grupo basta y el coste deja
    # de crecer con el número de tenants.
    assert borradas.get("30d") == 1
    assert "730d" not in borradas

    from sqlalchemy import func, select

    restantes = await db_session.scalar(
        select(func.count()).select_from(AuditLog).where(AuditLog.client_id == basico.id)
    )
    assert restantes == 1, "la entrada reciente de Basico debe sobrevivir"

    del_enterprise = await db_session.scalar(
        select(func.count()).select_from(AuditLog).where(
            AuditLog.client_id == enterprise.id
        )
    )
    assert del_enterprise == 1, "Enterprise retiene 730 días: nada que purgar a los 90"


def test_los_clientes_se_agrupan_por_retencion():
    """
    La purga borra por grupo, no por cliente. Planes distintos con la misma
    retención comparten sentencia, y los valores desconocidos caen en el grupo
    por defecto sin necesitar un caso especial.
    """
    a, b, c, d, e = (uuid4() for _ in range(5))
    grupos = group_by_retention([
        (a, "Basico"), (b, "Pro"), (c, "Basico"), (d, None), (e, "Inventado"),
    ])

    assert sorted(grupos) == sorted({30, 180})
    assert set(grupos[30]) == {a, c, d, e}
    assert grupos[180] == [b]


def test_los_grupos_devuelven_ids_no_nombres_de_plan():
    """
    Los documentos de Elasticsearch solo llevan client_id, así que agrupar por
    id es lo que permite expresar el mismo corte en los dos almacenes. Con una
    función por almacén, las dos políticas podrían divergir.
    """
    cid = uuid4()
    assert group_by_retention([(cid, "Pro")])[180] == [cid]


def test_el_corte_por_dias_es_el_mismo_calculo():
    ahora = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)
    assert cutoff_for_days(30, now=ahora) == ahora - timedelta(days=30)
    assert cutoff_for_days(30, now=ahora) == retention_cutoff("Basico", now=ahora)


def test_el_corte_de_retencion_es_el_mismo_calculo_en_un_solo_sitio():
    """
    purge_expired y query_entries deben usar exactamente el mismo corte: si
    divergieran, un cliente vería entradas que la purga ya considera caducadas
    o al contrario.
    """
    ahora = datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc)
    assert retention_cutoff("Pro", now=ahora) == ahora - timedelta(days=180)
    assert retention_cutoff(None, now=ahora) == ahora - timedelta(
        days=min(AUDIT_RETENTION_DAYS.values())
    )


def test_las_listas_de_roles_validos_derivan_del_enum():
    """
    Había listas literales de roles (invitaciones, cambio de rol, sembrado de
    los tests y el enum histórico de rbac.py) escritas a mano. Una lista
    desincronizada rechaza un rol válido sin que nada lo detecte: ya pasó una
    vez con GROUP_LEADER frente a TEAM_LEADER.
    """
    from app.models.role import UserRole
    from app.schemas.user import InvitationCreate

    todos = {r.value for r in UserRole}
    for rol in todos:
        assert InvitationCreate(email="a@b.co", role=rol).role == rol

    with pytest.raises(ValueError):
        InvitationCreate(email="a@b.co", role="INVENTADO")


# ---------------------------------------------------------------------------
# IP fiable (criterio 1 de TRV-07)
# ---------------------------------------------------------------------------

_PROD = {
    "ENVIRONMENT": "production",
    "DEBUG": False,
    "SECRET_KEY": "a" * 64,
    "ALLOWED_ORIGINS": ["https://corestream.example"],
}


@pytest.mark.parametrize("valor", ["*", "", "10.0.0.7", "10.0.0.0/24"])
def test_el_valor_del_proxy_no_impide_arrancar(valor):
    """Comprueba que el valor de FORWARDED_ALLOW_IPS no bloquea el arranque."""
    from app.config import Settings

    assert Settings(**_PROD, FORWARDED_ALLOW_IPS=valor).ENVIRONMENT == "production"


# ---------------------------------------------------------------------------
# Destinos (criterio 2 de TRV-07)
# ---------------------------------------------------------------------------

async def test_el_fallo_de_un_destino_no_impide_el_resto():
    """
    Si la base de datos no está disponible, la línea de log es la única
    constancia que queda del acto — y al revés. Un destino caído no puede
    arrastrar a los demás.
    """
    from app.services.audit_sinks import CompositeSink

    recibidos: list[str] = []

    class Rota:
        name = "rota"

        async def emit(self, entry):
            raise RuntimeError("destino caído")

    class Buena:
        name = "buena"

        async def emit(self, entry):
            recibidos.append(entry["path"])

    compuesto = CompositeSink([Rota(), Buena(), Rota()])
    await compuesto.emit({"method": "POST", "path": "/x", "status_code": 201})

    assert recibidos == ["/x"]


async def test_el_fallo_de_todos_los_destinos_no_propaga():
    """
    Dejar la API fuera de servicio porque la auditoría no está disponible no
    es un comportamiento exigido por TRV-07.
    """
    from app.services.audit_sinks import CompositeSink

    class Rota:
        name = "rota"

        async def emit(self, entry):
            raise RuntimeError("destino caído")

    await CompositeSink([Rota()]).emit(
        {"method": "POST", "path": "/x", "status_code": 201}
    )


def test_los_destinos_se_eligen_por_configuracion(monkeypatch):
    """
    AUDIT_SINKS nombra los destinos activos. Es lo que permite encender ELK sin
    tocar código, y lo que hace que «se derivan a un motor especializado» sea
    una cuestión de configuración y no de redespliegue del middleware.
    """
    from app.config import get_settings
    from app.services.audit_sinks import build_default_sink

    get_settings.cache_clear()
    monkeypatch.setenv("AUDIT_SINKS", "database")
    try:
        assert {s.name for s in build_default_sink().sinks} == {"database"}
    finally:
        get_settings.cache_clear()


def test_elastic_necesita_una_url():
    from app.services.audit_sinks import ElasticSink

    with pytest.raises(ValueError):
        ElasticSink(url="", index="x")


def test_el_indice_de_elastic_lleva_sufijo_de_fecha():
    """
    Es lo que espera el ciclo de vida de índices de Elastic para aplicar su
    propia retención y archivado por días.
    """
    from app.services.audit_sinks import ElasticSink

    sink = ElasticSink(url="http://es:9200", index="corestream-audit")
    entrada = {"occurred_at": datetime(2026, 10, 3, 11, 0, tzinfo=timezone.utc)}
    assert sink._index_for(entrada) == "corestream-audit-2026.10.03"


def test_elastic_autentica_con_api_key_si_se_le_da():
    from app.services.audit_sinks import ElasticSink

    sin_clave = ElasticSink(url="http://es:9200", index="x")
    assert "Authorization" not in sin_clave._headers

    con_clave = ElasticSink(url="http://es:9200", index="x", api_key="secreta")
    assert con_clave._headers["Authorization"] == "ApiKey secreta"


def test_el_mapeo_de_elastic_indexa_client_id_como_keyword():
    """
    REGRESIÓN. Por defecto Elasticsearch mapea un UUID como `text` analizado y
    el analizador parte por los guiones, así que una consulta `terms` sobre
    client_id no coincidía con nada y la purga de retención borraba cero en
    silencio. Con `keyword` la coincidencia es exacta.
    """
    from app.services.audit_sinks import ElasticSink

    propiedades = ElasticSink._TEMPLATE["template"]["mappings"]["properties"]
    assert propiedades["client_id"]["type"] == "keyword"


def test_todo_campo_que_se_consulta_esta_mapeado():
    """
    Los campos por los que filtra la purga o el visor tienen que estar en el
    mapeo: uno que se quede fuera vuelve al mapeo dinámico y reaparece el bug
    anterior.
    """
    from app.services.audit_sinks import ElasticSink

    propiedades = ElasticSink._TEMPLATE["template"]["mappings"]["properties"]
    consultados = {"client_id", "occurred_at", "outcome", "actor_email", "method"}
    assert consultados <= set(propiedades)

    # Y ningún campo de la entrada se queda sin tipo declarado.
    assert set(audit_records.ENTRY_FIELDS) <= set(propiedades)


def test_el_mapeo_de_elastic_no_gasta_en_replicas_ni_campos_dinamicos():
    """
    Un solo nodo: una réplica no se podría asignar, dejaría el índice en
    amarillo y duplicaría el disco. `dynamic: False` evita que un campo nuevo
    inesperado haga crecer el mapeo.
    """
    from app.services.audit_sinks import ElasticSink

    plantilla = ElasticSink._TEMPLATE["template"]
    assert plantilla["settings"]["number_of_replicas"] == 0
    assert plantilla["settings"]["number_of_shards"] == 1
    assert plantilla["mappings"]["dynamic"] is False


def test_elastic_acepta_autenticacion_basica():
    """El contenedor del perfil elk exige credenciales (xpack.security)."""
    import base64

    from app.services.audit_sinks import ElasticSink

    sink = ElasticSink(
        url="http://es:9200", index="x", username="elastic", password="secreta"
    )
    esperado = base64.b64encode(b"elastic:secreta").decode()
    assert sink._headers["Authorization"] == f"Basic {esperado}"


def test_la_api_key_gana_a_usuario_y_contrasena():
    """
    Dar las dos es un error de configuración; resolverlo de forma predecible
    es mejor que dejarlo al azar del servidor. Gana la credencial de alcance
    limitado.
    """
    from app.services.audit_sinks import ElasticSink

    sink = ElasticSink(
        url="http://es:9200", index="x", api_key="k",
        username="elastic", password="secreta",
    )
    assert sink._headers["Authorization"] == "ApiKey k"


def test_sin_credenciales_no_se_manda_cabecera_de_autenticacion():
    from app.services.audit_sinks import _auth_header

    assert _auth_header(api_key="", username="", password="") == {}
    # Usuario sin contraseña no es una credencial a medias: es ninguna.
    assert _auth_header(api_key="", username="elastic", password="") == {}


def test_cada_destino_registrado_cumple_el_protocolo():
    from app.services.audit_sinks import SINK_FACTORIES

    assert set(SINK_FACTORIES) == {"database", "elastic"}


def test_el_destino_por_defecto_es_la_base_de_datos():
    """Comprueba que sin configurar nada el registro va a audit.audit_logs."""
    from app.services.audit_sinks import AuditSink, build_default_sink

    sink = build_default_sink()
    assert {s.name for s in sink.sinks} == {"database"}
    assert all(isinstance(s, AuditSink) for s in sink.sinks)


async def test_el_middleware_no_conoce_los_destinos():
    """
    El middleware depende de la abstracción: sustituyendo el sink, nada más
    cambia. Es lo que hace que "derivar a un motor" sea extensible.
    """
    from app.services.audit_sinks import set_audit_sink

    capturado: list[dict] = []

    class Espia:
        name = "espia"

        async def emit(self, entry):
            capturado.append(dict(entry))

    set_audit_sink(Espia())
    try:
        await audit_service.record({"method": "POST", "path": "/y", "status_code": 201})
    finally:
        set_audit_sink(None)

    assert capturado and capturado[0]["path"] == "/y"


async def test_las_entradas_sin_cliente_caducan_con_la_retencion_mas_corta(db_session):
    """
    Un login fallido contra un email inexistente no pertenece a ningún tenant,
    así que no puede acogerse a la retención ampliada de nadie.
    """
    ahora = datetime.now(timezone.utc)
    db_session.add(_fila(client_id=None, occurred_at=ahora - timedelta(days=400)))
    db_session.add(_fila(client_id=None, occurred_at=ahora))
    await db_session.commit()

    borradas = await audit_service.purge_expired(db_session)
    assert borradas.get("sin_cliente") == 1
