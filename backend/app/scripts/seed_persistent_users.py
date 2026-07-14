"""
Inicializa roles y (opcionalmente) usuarios de demo de forma idempotente.

Roles siempre se crean — el sistema RBAC los requiere.
Usuarios de demo solo se crean cuando RUN_SEED=true, para evitar
contaminar entornos de producción con cuentas @example.com ficticias.
"""

from __future__ import annotations

import os
from uuid import uuid4
import hashlib
import base64

import psycopg2

from app.config import get_settings
from app.services.auth_service import pwd_context


def _prepare_password(password: str) -> str:
    """Prepara contraseña con SHA-256 para bcrypt (mismo que AuthService)."""
    digest = hashlib.sha256(password.encode()).digest()
    return base64.b64encode(digest).decode()


DEFAULT_ROLES = [
    ("ADMIN", "Administrator with full system access"),
    ("DEVELOPER", "Regular developer with standard permissions"),
    ("TEAM_LEADER", "Team leader with expanded permissions"),
]

DEMO_USERS = [
    {
        "email": "admin@example.com",
        "password": "Admin@123!",
        "full_name": "Administrador",
        "specialty": "Project Management",
        "role": "ADMIN",
    },
    {
        "email": "leader@example.com",
        "password": "Leader@123!",
        "full_name": "Líder de Equipo",
        "specialty": "Team Leadership",
        "role": "TEAM_LEADER",
    },
    {
        "email": "userdev@example.com",
        "password": "Jjgg11@!",
        "full_name": "Desarrollador",
        "specialty": "Backend Development",
        "role": "DEVELOPER",
    },
]


def _to_sync_database_url(database_url: str) -> str:
    """Convierte URL async de SQLAlchemy a URL compatible con psycopg2."""
    return database_url.replace("postgresql+asyncpg://", "postgresql://", 1)


def seed_persistent_users() -> None:
    """Crea roles siempre; usuarios de demo solo cuando RUN_SEED=true."""
    settings = get_settings()
    db_url = _to_sync_database_url(settings.DATABASE_URL)
    run_seed = os.getenv("RUN_SEED", "false").lower() == "true"

    conn = None
    try:
        conn = psycopg2.connect(db_url)
        cursor = conn.cursor()

        role_ids: dict[str, str] = {}
        for role_name, role_desc in DEFAULT_ROLES:
            cursor.execute("SELECT id FROM roles WHERE name = %s", (role_name,))
            row = cursor.fetchone()

            if row:
                role_ids[role_name] = str(row[0])
                continue

            role_id = str(uuid4())
            cursor.execute(
                """
                INSERT INTO roles (id, name, description)
                VALUES (%s, %s, %s)
                """,
                (role_id, role_name, role_desc),
            )
            role_ids[role_name] = role_id

        demo_emails = tuple(u["email"] for u in DEMO_USERS)

        if run_seed:
            for user in DEMO_USERS:
                cursor.execute("SELECT id FROM users WHERE email = %s", (user["email"],))
                if cursor.fetchone():
                    continue

                prepared = _prepare_password(user["password"])
                hashed_password = pwd_context.hash(prepared)
                cursor.execute(
                    """
                    INSERT INTO users
                        (id, email, hashed_password, full_name, specialty, is_active, role_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        str(uuid4()),
                        user["email"],
                        hashed_password,
                        user["full_name"],
                        user["specialty"],
                        True,
                        role_ids[user["role"]],
                    ),
                )
        else:
            # Production mode: remove any demo accounts that leaked into the DB.
            cursor.execute(
                "DELETE FROM users WHERE email = ANY(%s::text[])",
                (list(demo_emails),),
            )

        conn.commit()

    except Exception:
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()
