"""
Script de emergencia: regenera el hash del usuario TEAM_LEADER con el método actual.

Ejecutar en Railway console o localmente apuntando a la DB de producción:
    python -m app.scripts.fix_leader_password

El script:
1. Lee el hash actual del leader y lo muestra para diagnóstico
2. Verifica si el hash actual fue creado con _prepare_password (SHA-256 wrap) o sin él
3. Regenera el hash con el método correcto (SHA-256 + bcrypt)
"""
import hashlib
import base64
import psycopg2
from app.config import get_settings
from app.services.auth_service import pwd_context

LEADER_EMAIL = "leader@example.com"
LEADER_PASSWORD = "Leader@123!"


def _prepare_password(password: str) -> str:
    digest = hashlib.sha256(password.encode()).digest()
    return base64.b64encode(digest).decode()


def main() -> None:
    settings = get_settings()
    db_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://", 1)

    conn = psycopg2.connect(db_url)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id, hashed_password FROM users WHERE email = %s",
        (LEADER_EMAIL,),
    )
    row = cursor.fetchone()

    if not row:
        print(f"[ERROR] Usuario {LEADER_EMAIL} no encontrado en BD")
        conn.close()
        return

    user_id, current_hash = row
    if isinstance(current_hash, (bytes, memoryview)):
        current_hash = bytes(current_hash).decode("utf-8")
    current_hash = str(current_hash).strip()

    print(f"[INFO] user_id     = {user_id}")
    print(f"[INFO] hash actual = {current_hash[:20]}...")

    # Verificar con método actual (SHA-256 wrap)
    prepared = _prepare_password(LEADER_PASSWORD)
    with_prepare = pwd_context.verify(prepared, current_hash)
    without_prepare = pwd_context.verify(LEADER_PASSWORD, current_hash)

    print(f"[CHECK] verify con _prepare_password  = {with_prepare}")
    print(f"[CHECK] verify sin _prepare_password  = {without_prepare}")

    if with_prepare:
        print("[OK] El hash es correcto con el método actual. No se requiere regeneración.")
        conn.close()
        return

    if without_prepare:
        print("[FIX] Hash fue creado SIN _prepare_password. Regenerando con método actual...")
    else:
        print("[FIX] Hash no coincide con ningún método. Regenerando igualmente...")

    new_hash = pwd_context.hash(prepared)
    cursor.execute(
        "UPDATE users SET hashed_password = %s WHERE id = %s",
        (new_hash, str(user_id)),
    )
    conn.commit()
    print(f"[OK] Hash actualizado para {LEADER_EMAIL}")
    print(f"[INFO] nuevo hash  = {new_hash[:20]}...")

    conn.close()


if __name__ == "__main__":
    main()
