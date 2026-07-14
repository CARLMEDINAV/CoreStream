"""
Fixtures compartidas para los tests de CS-044.

ORDEN CRÍTICO:
1. sys.modules mock de app.database (crea engine al importar, incompatible con SQLite)
2. Variables de entorno para get_settings() con lru_cache
3. Imports de app modules
"""

import os
import sys
from unittest.mock import MagicMock, AsyncMock

# ── Bloquear app.database antes de cualquier import de la app ──────────────
# app.database crea el engine PostgreSQL con pool_size/max_overflow en el nivel
# de módulo, lo que falla en SQLite. Lo reemplazamos con un mock.
_mock_db_module = MagicMock()
_mock_db_module.get_db = AsyncMock()
_mock_db_module.engine = MagicMock()
_mock_db_module.async_session_maker = MagicMock()
sys.modules["app.database"] = _mock_db_module

# ── Dependencias solo disponibles en Docker; mock para permitir imports ─────
# Permite que test_validations.py importe los routers sin tener
# psycopg2/arq/redis instalados localmente.
for _mod in [
    "psycopg2", "psycopg2.extras", "psycopg2.extensions",
    "arq", "arq.connections",
    "redis", "redis.asyncio",
    "aiofiles",
]:
    sys.modules.setdefault(_mod, MagicMock())

# ── Variables de entorno para Settings (antes de que lru_cache se active) ──
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-cs044-unit-tests")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ALGORITHM", "HS256")
os.environ.setdefault("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
os.environ.setdefault("REFRESH_TOKEN_EXPIRE_DAYS", "7")

# ── Patch SQLite para soportar JSONB (usado en TicketEvent.detail) ───────
# SQLAlchemy no tiene un visitor para JSONB en SQLite; lo delegamos a JSON.
from sqlalchemy.dialects.sqlite.base import SQLiteTypeCompiler

def _visit_JSONB(self, type_, **kw):
    return self.visit_JSON(type_, **kw)

SQLiteTypeCompiler.visit_JSONB = _visit_JSONB  # type: ignore[attr-defined]

# ── Imports de app (ahora seguros) ────────────────────────────────────────
import pytest
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, Role, User, Application, Epic, Ticket, TicketStatus
from app.middleware.auth import hash_password

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def db_session():
    """Sesión SQLite en memoria con todas las tablas. Se destruye al finalizar cada test."""
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest.fixture
async def sample_role(db_session: AsyncSession):
    """Rol ADMIN de prueba."""
    role = Role(name="ADMIN", description="Administrador del sistema")
    db_session.add(role)
    await db_session.flush()
    return role


@pytest.fixture
async def sample_user(db_session: AsyncSession, sample_role: Role):
    """Usuario de prueba con rol ADMIN."""
    user = User(
        email="test@corestream.com",
        full_name="Test User",
        hashed_password=hash_password("testpass123"),
        role_id=sample_role.id,
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.fixture
async def sample_app(db_session: AsyncSession):
    """Aplicación de prueba."""
    app = Application(name="Test Application", is_active=True)
    db_session.add(app)
    await db_session.flush()
    return app


@pytest.fixture
async def sample_epic(db_session: AsyncSession, sample_app: Application):
    """Épica de prueba dentro de sample_app."""
    epic = Epic(
        title="Test Epic",
        order_index=0,
        application_id=sample_app.id,
        due_date=datetime.now(timezone.utc) + timedelta(days=14),
    )
    db_session.add(epic)
    await db_session.flush()
    return epic


@pytest.fixture
async def sample_ticket(db_session: AsyncSession, sample_epic: Epic, sample_user: User):
    """Ticket de prueba en estado TODO asignado a sample_user."""
    ticket = Ticket(
        title="Test Ticket",
        status=TicketStatus.TODO,
        epic_id=sample_epic.id,
        assignee_id=sample_user.id,
        time_spent_seconds=3600,
    )
    db_session.add(ticket)
    await db_session.flush()
    return ticket
