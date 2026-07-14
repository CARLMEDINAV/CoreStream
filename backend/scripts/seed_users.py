"""
Seed de usuarios de producción para CoreStream.

Ejecutar UNA VEZ después del primer deploy en Railway:

  railway run python scripts/seed_users.py

O dentro del contenedor:

  python scripts/seed_users.py

El script es idempotente: no duplica usuarios ni roles si ya existen.
"""

from __future__ import annotations

import hashlib
import base64
import os
import sys
from uuid import uuid4

# Añadir el directorio raíz del backend al path para importar app.*
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ─── Usuarios de producción ────────────────────────────────────────────────────
# Cambiar contraseñas antes de primer deploy en producción.
PRODUCTION_USERS = [
    {
        "email": "admin@corestream.app",
        "password": "Admin@Demo2026!",
        "full_name": "Administrador CoreStream",
        "specialty": "Project Management",
        "role": "ADMIN",
    },
    {
        "email": "leader@corestream.app",
        "password": "Leader@Demo2026!",
        "full_name": "Paolo Sepúlveda",
        "specialty": "Full-Stack Development",
        "role": "TEAM_LEADER",
    },
    {
        "email": "mauricio@corestream.app",
        "password": "Dev@Demo2026!",
        "full_name": "Mauricio Reynoso",
        "specialty": "Frontend Development",
        "role": "DEVELOPER",
    },
    {
        "email": "benjamin@corestream.app",
        "password": "Dev@Demo2026!",
        "full_name": "Benjamín Farías",
        "specialty": "Backend Development",
        "role": "DEVELOPER",
    },
    {
        "email": "nicolas@corestream.app",
        "password": "Dev@Demo2026!",
        "full_name": "Nicolás Céspedes",
        "specialty": "Infrastructure",
        "role": "DEVELOPER",
    },
]

ROLES = [
    ("ADMIN", "Administrator with full system access"),
    ("DEVELOPER", "Regular developer with standard permissions"),
    ("TEAM_LEADER", "Team leader with expanded permissions"),
]
# ──────────────────────────────────────────────────────────────────────────────


def _hash_password(password: str) -> str:
    """Misma lógica de hash que usa AuthService: SHA-256 → bcrypt."""
    digest = hashlib.sha256(password.encode()).digest()
    prepared = base64.b64encode(digest).decode()
    return pwd_context.hash(prepared)


def _to_sync_url(database_url: str) -> str:
    """Convierte URL asyncpg a psycopg2 (sync)."""
    return database_url.replace("postgresql+asyncpg://", "postgresql://", 1)


def seed() -> None:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ DATABASE_URL no está definida.")
        sys.exit(1)

    sync_url = _to_sync_url(database_url)
    conn = psycopg2.connect(sync_url)

    try:
        cur = conn.cursor()

        # 1. Crear roles si no existen
        role_ids: dict[str, str] = {}
        for role_name, role_desc in ROLES:
            cur.execute("SELECT id FROM roles WHERE name = %s", (role_name,))
            row = cur.fetchone()
            if row:
                role_ids[role_name] = str(row[0])
                print(f"  rol {role_name} ya existe")
            else:
                role_id = str(uuid4())
                cur.execute(
                    "INSERT INTO roles (id, name, description) VALUES (%s, %s, %s)",
                    (role_id, role_name, role_desc),
                )
                role_ids[role_name] = role_id
                print(f"  ✅ rol {role_name} creado")

        # 2. Crear usuarios si no existen
        for user in PRODUCTION_USERS:
            cur.execute("SELECT id FROM users WHERE email = %s", (user["email"],))
            if cur.fetchone():
                print(f"  usuario {user['email']} ya existe")
                continue

            cur.execute(
                """
                INSERT INTO users
                    (id, email, hashed_password, full_name, specialty, is_active, role_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    str(uuid4()),
                    user["email"],
                    _hash_password(user["password"]),
                    user["full_name"],
                    user["specialty"],
                    True,
                    role_ids[user["role"]],
                ),
            )
            print(f"  ✅ usuario {user['email']} ({user['role']}) creado")

        conn.commit()
        print("\n✅ Seed completado.")

    except Exception as e:
        conn.rollback()
        print(f"❌ Error durante seed: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    print("Iniciando seed de usuarios de producción...\n")
    seed()
