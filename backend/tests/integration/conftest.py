"""
Fixtures para los tests de integración.

A diferencia de tests/conftest.py, aquí NO se mockea absolutamente nada: se
levanta la aplicación real sobre una base de datos PostgreSQL efímera, con
Redis real, y se la ejercita por HTTP. Es la única capa que puede detectar
fallos como los encontrados en la auditoría: lazy-loads fuera de contexto async
(MissingGreenlet), agujeros de RBAC y desajustes de ruta o de método entre el
cliente y el servidor.

La base de datos se crea desde cero y se migra con Alembic en cada sesión de
test, lo que de paso verifica que la cadena de migraciones aplica limpia.

Variables de entorno reconocidas:
    TEST_DATABASE_URL  destino de las pruebas (por defecto: …/corestream_test)
    TEST_REDIS_URL     índice de Redis para pruebas (por defecto: db 15)
"""

import os
import tempfile
from urllib.parse import urlparse, urlunparse

# ── La configuración debe fijarse ANTES de importar nada de la aplicación,
#    porque get_settings() está cacheada con lru_cache y alembic/env.py la usa.
_DEFAULT_TEST_DB = "postgresql+asyncpg://corestream:corestream@localhost:5432/corestream_test"

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", _DEFAULT_TEST_DB)
TEST_REDIS_URL = os.environ.get("TEST_REDIS_URL", "redis://localhost:6379/15")

os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["REDIS_URL"] = TEST_REDIS_URL
os.environ.setdefault("SECRET_KEY", "clave-solo-para-tests-de-integracion-no-usar")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("ALLOWED_ORIGINS", "http://testserver")
os.environ["SQL_ECHO"] = "False"
os.environ["RUN_SEED"] = "false"

# Raíz de almacenamiento de ficheros subidos. Por defecto la app usa
# /app/storage (la ruta dentro del contenedor), que en el runner de GitHub
# Actions —o en cualquier máquina sin esa carpeta— no existe ni se puede
# crear: los tests de documentos y uploads fallaban con PermissionError.
# Un directorio temporal propio además evita que los tests escriban en el
# volumen de storage real del entorno de desarrollo. setdefault: si alguien
# define UPLOAD_DIR explícitamente, se respeta.
os.environ.setdefault("UPLOAD_DIR", tempfile.mkdtemp(prefix="corestream-test-storage-"))

import psycopg2
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# Credenciales de los usuarios de prueba. Se crean aquí, no por el seeder de la
# aplicación: ese seeder se elimina en la fase 3.6 y los tests no deben
# depender de él (ni de contraseñas conocidas embebidas en el código).
ADMIN = {"email": "admin@corestream-tests.com", "password": "TestAdmin123!@#", "role": "ADMIN"}
LEADER = {"email": "leader@corestream-tests.com", "password": "TestLeader123!@#", "role": "TEAM_LEADER"}
DEV = {"email": "dev@corestream-tests.com", "password": "TestDev123!@#", "role": "DEVELOPER"}
DEV2 = {"email": "dev2@corestream-tests.com", "password": "TestDev223!@#", "role": "DEVELOPER"}

# Cliente "por defecto" (bootstrap): donde viven los usuarios que ya usan
# test_rbac.py y test_tickets.py. Mismo id determinístico que los usuarios,
# por la misma razón (JWT estable entre truncados de _clean_database).
DEFAULT_CLIENT_SLUG = "corestream-test-default"
DEFAULT_CLIENT_NAME = "Cliente de Test por Defecto"

# Segundo tenant — solo lo usa test_tenancy.py, pero se siembra siempre
# junto con el resto para no depender de fixtures function-scoped que
# choquen con el truncado autouse de _clean_database.
CLIENT_B_SLUG = "corestream-test-cliente-b"
CLIENT_B_NAME = "Cliente B (aislamiento)"
ADMIN_B = {"email": "admin-b@corestream-tests.com", "password": "TestAdminB123!@#", "role": "ADMIN"}

LEADER_B = {"email": "leader-b@corestream-tests.com", "password": "TestLeaderB123!@#", "role": "TEAM_LEADER"}
DEV_B = {"email": "dev-b@corestream-tests.com", "password": "TestDevB123!@#", "role": "DEVELOPER"}

ALL_TEST_USERS = [ADMIN, LEADER, DEV, DEV2]
CLIENT_B_USERS = [ADMIN_B,LEADER_B, DEV_B]



def _sync_url(async_url: str) -> str:
    """URL para psycopg2 a partir de la URL async de SQLAlchemy."""
    return async_url.replace("postgresql+asyncpg://", "postgresql://", 1)


def _maintenance_url(sync_url: str) -> tuple[str, str]:
    """Devuelve (url a la base 'postgres', nombre de la base de test)."""
    parsed = urlparse(sync_url)
    db_name = parsed.path.lstrip("/")
    maintenance = urlunparse(parsed._replace(path="/postgres"))
    return maintenance, db_name


# ---------------------------------------------------------------------------
# Preparación de la base de datos (síncrona, a nivel de sesión)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def _prepared_database():
    """
    Recrea la base de datos de test desde cero y le aplica todas las migraciones.

    Se hace de forma síncrona y a nivel de sesión para no pelear con el bucle de
    eventos de asyncio. Que Alembic aplique limpio sobre una base vacía es en sí
    mismo una comprobación: detecta cabezas múltiples y migraciones rotas.
    """
    sync_url = _sync_url(TEST_DATABASE_URL)
    maintenance_url, db_name = _maintenance_url(sync_url)

    conn = psycopg2.connect(maintenance_url)
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    try:
        cur = conn.cursor()
        # Cortar conexiones vivas antes de borrar (p. ej. de una ejecución previa)
        cur.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            "WHERE datname = %s AND pid <> pg_backend_pid()",
            (db_name,),
        )
        cur.execute(f'DROP DATABASE IF EXISTS "{db_name}"')
        cur.execute(f'CREATE DATABASE "{db_name}"')
    finally:
        conn.close()

    # Migraciones con la API de Alembic, apuntando a la base recién creada.
    from alembic.config import Config

    from alembic import command

    alembic_cfg = Config(os.path.join(os.path.dirname(__file__), "..", "..", "alembic.ini"))
    alembic_cfg.set_main_option(
        "script_location", os.path.join(os.path.dirname(__file__), "..", "..", "alembic")
    )
    command.upgrade(alembic_cfg, "head")

    # Sembrar roles y usuarios de prueba ya aquí, no solo en _clean_database:
    # admin_headers/leader_headers/dev_headers/dev2_headers son fixtures de
    # sesión y pytest instancia los fixtures de mayor scope antes que los de
    # función dentro de un mismo test — si el primer test de la sesión pide
    # directa o indirectamente admin_headers, ese login puede intentar correr
    # antes de que el _clean_database (function-scoped) de ese test llegue a
    # sembrar nada. Sembrar aquí garantiza que la tabla users nunca está vacía
    # cuando se intenta el primer login.
    # Se trunca primero: la migración a2b3c4d5e6f7 ya deja los tres roles
    # insertados (con sus propios ids) como parte de "alembic upgrade head".
    conn = psycopg2.connect(sync_url)
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    try:
        cur = conn.cursor()
        cur.execute("TRUNCATE TABLE users, roles, clients RESTART IDENTITY CASCADE")
        _seed_roles_and_users(cur)
    finally:
        conn.close()

    yield TEST_DATABASE_URL


async def _flush_rate_limit_counters() -> None:
    """
    Borra los contadores de rate limiting (plan 3.5) entre tests.

    Sin esto, un test que deliberadamente agota el límite (fuerza bruta contra
    /auth/login) deja el contador de su IP —compartida por todo el cliente de
    pruebas— por encima del umbral, y CUALQUIER login real de CUALQUIER cuenta
    en tests posteriores de la misma sesión de pytest empieza a devolver 429.
    """
    import redis.asyncio as aioredis

    client = aioredis.from_url(TEST_REDIS_URL)
    try:
        async for key in client.scan_iter(match="corestream:ratelimit:*"):
            await client.delete(key)
    finally:
        await client.aclose()


@pytest_asyncio.fixture(loop_scope="session", autouse=True)
async def _clean_database(client):
    """
    Deja la base y el rate limiter en un estado conocido antes de cada test.

    Se trunca en lugar de usar transacciones con rollback porque la aplicación
    abre sus propias sesiones a través de get_db(): una transacción externa no
    las envolvería. Con el volumen de datos de los tests, truncar es inmediato.

    Depende de `client` a propósito: así el lifespan de la aplicación (que hoy
    todavía siembra usuarios de demostración) se ejecuta antes del primer
    truncado y no contamina ningún test.
    """
    from app.models import Base

    tables = [t.name for t in Base.metadata.sorted_tables if t.name != "alembic_version"]

    conn = psycopg2.connect(_sync_url(TEST_DATABASE_URL))
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    try:
        cur = conn.cursor()
        cur.execute(
            "TRUNCATE TABLE {} RESTART IDENTITY CASCADE".format(
                ", ".join(f'"{t}"' for t in tables)
            )
        )
        _seed_roles_and_users(cur)
    finally:
        conn.close()

    await _flush_rate_limit_counters()

    yield


def _seed_roles_and_users(cur) -> None:
    """
    Crea roles, dos clientes (tenants) y un usuario por rol en cada uno.

    IDs determinísticos (uuid5), igual que antes: admin_headers/leader_headers/
    etc. son fixtures de sesión, pero _clean_database trunca y re-siembra
    antes de CADA test. Con ids estables, el JWT del primer test sigue
    resolviendo al usuario/cliente correcto en el resto de la sesión.
    """
    import uuid

    from app.services.auth_service import AuthService

    role_ids = {}
    for name, desc in [
        ("DEVELOPER", "Desarrollador"),
        ("TEAM_LEADER", "Líder de equipo"),
        ("ADMIN", "Administrador"),
    ]:
        rid = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"corestream-test-role:{name}"))
        cur.execute(
            "INSERT INTO roles (id, name, description) VALUES (%s, %s, %s)",
            (rid, name, desc),
        )
        role_ids[name] = rid

    def _client_id_for(slug: str) -> str:
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"corestream-test-client:{slug}"))

    default_client_id = _client_id_for(DEFAULT_CLIENT_SLUG)
    client_b_id = _client_id_for(CLIENT_B_SLUG)

    for cid, name, slug in [
        (default_client_id, DEFAULT_CLIENT_NAME, DEFAULT_CLIENT_SLUG),
        (client_b_id, CLIENT_B_NAME, CLIENT_B_SLUG),
    ]:
        cur.execute(
            "INSERT INTO clients (id, name, slug, is_active) VALUES (%s, %s, %s, %s)",
            (cid, name, slug, True),
        )

    def _seed_user(user: dict, client_id: str) -> None:
        cur.execute(
            "INSERT INTO users (id, email, full_name, hashed_password, role_id, is_active, client_id) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (
                str(uuid.uuid5(uuid.NAMESPACE_DNS, f"corestream-test-user:{user['email']}")),
                user["email"],
                user["email"].split("@")[0].title(),
                AuthService.hash_password(user["password"]),
                role_ids[user["role"]],
                True,
                client_id,
            ),
        )

    for user in ALL_TEST_USERS:
        _seed_user(user, default_client_id)
    for user in CLIENT_B_USERS:
        _seed_user(user, client_b_id)


# ---------------------------------------------------------------------------
# Cliente HTTP sobre la aplicación real
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def client(_prepared_database):
    """
    Cliente HTTP contra la aplicación real, con su lifespan ejecutado.

    Ejecutar el lifespan importa: es donde se inicializan Redis y el pool de ARQ,
    y sin ellos las notificaciones no se encolan. Queremos ejercitar ese camino,
    no esquivarlo.
    """
    from app.database import configure_engine, dispose_engine

    configure_engine(TEST_DATABASE_URL)

    from app.main import app

    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as ac:
            yield ac

    await dispose_engine()


# ---------------------------------------------------------------------------
# Autenticación
# ---------------------------------------------------------------------------

async def _login(client: AsyncClient, user: dict) -> dict:
    """Inicia sesión y devuelve las cabeceras de autorización."""
    res = await client.post(
        "/api/auth/login", json={"email": user["email"], "password": user["password"]}
    )
    assert res.status_code == 200, f"login de {user['email']} falló: {res.status_code} {res.text[:200]}"
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def admin_headers(client: AsyncClient) -> dict:
    return await _login(client, ADMIN)

@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def admin_b_headers(client: AsyncClient) -> dict:
    return await _login(client, ADMIN_B)


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def leader_headers(client: AsyncClient) -> dict:
    return await _login(client, LEADER)

@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def leader_b_headers(client: AsyncClient) -> dict:
    return await _login(client, LEADER_B)


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def dev_headers(client: AsyncClient) -> dict:
    return await _login(client, DEV)

@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def dev_b_headers(client: AsyncClient) -> dict:
    return await _login(client, DEV_B)


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def dev2_headers(client: AsyncClient) -> dict:
    return await _login(client, DEV2)


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def dev_id(client: AsyncClient, dev_headers: dict) -> str:
    res = await client.get("/api/auth/me", headers=dev_headers)
    return res.json()["id"]


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def dev2_id(client: AsyncClient, dev2_headers: dict) -> str:
    res = await client.get("/api/auth/me", headers=dev2_headers)
    return res.json()["id"]


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def leader_id(client: AsyncClient, leader_headers: dict) -> str:
    res = await client.get("/api/auth/me", headers=leader_headers)
    return res.json()["id"]


# ---------------------------------------------------------------------------
# Datos de dominio
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(loop_scope="session")
async def application(client: AsyncClient, admin_headers: dict) -> dict:
    res = await client.post(
        "/api/applications/",
        json={
            "name": "App de prueba",
            "description": "Creada por los tests de integración",
            "color": "#2563EB",
            "icon": "folder",
        },
        headers=admin_headers,
    )
    assert res.status_code == 201, res.text[:300]
    return res.json()


@pytest_asyncio.fixture(loop_scope="session")
async def epic(client: AsyncClient, leader_headers: dict, application: dict) -> dict:
    res = await client.post(
        "/api/epics/",
        json={
            "application_id": application["id"],
            "title": "Épica de prueba",
            "description": "Creada por los tests de integración",
        },
        headers=leader_headers,
    )
    assert res.status_code == 201, res.text[:300]
    return res.json()


@pytest_asyncio.fixture(loop_scope="session")
async def ticket(client: AsyncClient, leader_headers: dict, epic: dict, dev_id: str) -> dict:
    res = await client.post(
        "/api/tickets/",
        json={
            "epic_id": epic["id"],
            "title": "Ticket de prueba",
            "description": "Creado por los tests de integración",
            "priority": "HIGH",
            "assignee_id": dev_id,
        },
        headers=leader_headers,
    )
    assert res.status_code == 201, res.text[:300]
    return res.json()
