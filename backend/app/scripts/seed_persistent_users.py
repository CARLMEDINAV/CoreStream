"""
Script para inicializar usuarios persistentes (base) del sistema.

Este script crea usuarios esenciales que siempre deben existir en la BD
para que el sistema funcione correctamente. Es idempotente: si los usuarios
ya existen, no hace nada.

IMPORTANTE: Usa AuthService.hash_password para garantizar que el hashing
sea consistente con el mecanismo de verificación del backend (SHA-256 + bcrypt).

Usuarios creados:
- admin@example.com     / Admin123!@#   (ADMIN)
- leader@example.com    / Leader123!@#  (TEAM_LEADER)
- userdev@example.com   / Dev123!@#     (DEVELOPER)
"""

from __future__ import annotations

import uuid

import psycopg2

from app.config import get_settings
from app.services.auth_service import AuthService


def _to_sync_url(database_url: str) -> str:
    """Convierte URL async de SQLAlchemy a URL compatible con psycopg2."""
    return database_url.replace("postgresql+asyncpg://", "postgresql://", 1)


def seed_persistent_users() -> None:
    """Crea los usuarios base del sistema si no existen."""
    settings = get_settings()
    db_url = _to_sync_url(settings.DATABASE_URL)

    users_to_seed = [
        {
            "email": "admin@example.com",
            "full_name": "Administrador",
            "password": "Admin123!@#",
            "role_name": "ADMIN",
        },
        {
            "email": "leader@example.com",
            "full_name": "Líder de Equipo",
            "password": "Leader123!@#",
            "role_name": "TEAM_LEADER",
        },
        {
            "email": "userdev@example.com",
            "full_name": "Desarrollador Demo",
            "password": "Dev123!@#",
            "role_name": "DEVELOPER",
        },
    ]

    conn = None
    try:
        conn = psycopg2.connect(db_url)
        cursor = conn.cursor()

        # Garantizar que existen los roles mínimos necesarios
        for role_name, role_desc in [
            ("DEVELOPER", "Desarrollador regular"),
            ("TEAM_LEADER", "Líder de equipo con permisos expandidos"),
            ("ADMIN", "Administrador con acceso total al sistema"),
        ]:
            cursor.execute(
                "INSERT INTO roles (id, name, description) VALUES (%s, %s, %s) "
                "ON CONFLICT (name) DO NOTHING",
                (str(uuid.uuid4()), role_name, role_desc),
            )

        # Build role name -> role_id map
        cursor.execute("SELECT id, name FROM roles")
        role_rows = cursor.fetchall()
        role_map = {name: str(rid) for rid, name in role_rows}

        for user_data in users_to_seed:
            # Check if user already exists
            cursor.execute(
                "SELECT id FROM users WHERE email = %s",
                (user_data["email"],),
            )
            if cursor.fetchone():
                continue

            role_id = role_map.get(user_data["role_name"])
            if not role_id:
                print(f"  ⚠ Role '{user_data['role_name']}' not found, skipping {user_data['email']}")
                continue

            # Usar AuthService para garantizar hashing consistente (SHA-256 + bcrypt)
            hashed_pw = AuthService.hash_password(user_data["password"])

            cursor.execute(
                """
                INSERT INTO users (id, email, full_name, hashed_password, role_id, is_active)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    str(uuid.uuid4()),
                    user_data["email"],
                    user_data["full_name"],
                    hashed_pw,
                    role_id,
                    True,
                ),
            )
            print(f"  ✓ Usuario creado: {user_data['email']} [{user_data['role_name']}]")

        conn.commit()
        print("✅ Usuarios base inicializados correctamente")

    except Exception as e:
        if conn:
            conn.rollback()
        print(f"❌ Error al crear usuarios base: {e}")
        raise
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    seed_persistent_users()
