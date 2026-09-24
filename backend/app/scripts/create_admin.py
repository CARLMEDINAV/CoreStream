"""
Bootstrap del primer ADMIN de un cliente de CoreStream (plan 3.6 + TRV-01).

No hay ningún otro camino para crear un ADMIN: /auth/register ya no existe,
POST /api/users/ fuerza DEVELOPER, y /users/{id}/change-role exige ya ser
ADMIN para llamarlo. Este script es la única puerta de entrada, y es
deliberadamente manual: no se ejecuta en el arranque de la aplicación.

Con TRV-01 (multi-tenancy), también es la única puerta de entrada para dar
de alta un Client nuevo — no existe (ni se planea, ver TRV01_IMPLEMENTACION.md
sección 11) un endpoint HTTP para eso. Por eso este script ahora resuelve
o crea el Client antes de crear el ADMIN.

Uso:
    python -m app.scripts.create_admin --email admin@alloxentric.com \
        --client-slug alloxentric --client-name "Alloxentric"

Si el --client-slug ya existe, se reusa ese Client (no se crea uno nuevo).
Si no se pasa --password, se genera una aleatoria y se imprime una sola vez
(no queda guardada en ningún sitio salvo el hash en la base de datos).

Es idempotente y se niega a crear un segundo ADMIN del mismo cliente por
accidente: si ese cliente ya tiene un ADMIN, se detiene y lo informa — usar
la propia aplicación (gestión de equipo) para promover a más administradores
a partir de ahí. La guarda es POR CLIENTE, no global: crear el primer ADMIN
de un cliente nuevo no se bloquea porque otro cliente ya tenga el suyo.
"""

from __future__ import annotations

import argparse
import asyncio
import secrets
import string
import sys

from sqlalchemy import select

from app.database import get_session_maker
from app.models import Client, Role, User, UserRole
from app.services.auth_service import AuthService


def _generate_password(length: int = 20) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*()"
    return "".join(secrets.choice(alphabet) for _ in range(length))


async def create_admin(
    email: str,
    password: str | None,
    full_name: str,
    client_slug: str,
    client_name: str | None,
) -> None:
    email = email.lower().strip()
    client_slug = client_slug.lower().strip()

    async with get_session_maker()() as db:
        # ── Resolver o crear el Client ────────────────────────────────────
        client_result = await db.execute(select(Client).where(Client.slug == client_slug))
        client = client_result.scalars().first()

        if client is None:
            if not client_name:
                print(
                    f"No existe ningún cliente con slug '{client_slug}'. "
                    "Pasa --client-name para crearlo de una vez."
                )
                sys.exit(1)
            client = Client(name=client_name, slug=client_slug, is_active=True)
            db.add(client)
            await db.flush()  # necesitamos client.id antes del commit final
            print(f"Cliente nuevo creado: {client_name} (slug={client_slug})")
        else:
            print(f"Usando cliente existente: {client.name} (slug={client_slug})")

        # ── Guarda de idempotencia: UN ADMIN POR CLIENTE, no global ───────
        # Este script corre fuera de un request HTTP, así que
        # current_client_id_ctx nunca se setea y el filtro automático de
        # tenant (Fase 4) no actúa acá — hay que filtrar por client_id a
        # mano, explícitamente, en esta consulta puntual.
        existing_admin = await db.execute(
            select(User)
            .join(Role, User.role_id == Role.id)
            .where(Role.name == UserRole.ADMIN.value, User.client_id == client.id)
        )
        if existing_admin.scalars().first() is not None:
            print(
                f"El cliente '{client_slug}' ya tiene al menos un ADMIN. Este "
                "script no crea un segundo por seguridad — usa la gestión de "
                "equipo dentro de la aplicación (o POST /api/users/{id}/change-role) "
                "para promover a más dentro del mismo cliente."
            )
            sys.exit(1)

        # ── Email único GLOBALMENTE ──
        # Por la misma razón que la consulta anterior: sin contexto de
        # tenant, esta consulta ya es global sin necesitar skip_tenant_scope.
        existing_user = await db.execute(select(User).where(User.email == email))
        if existing_user.scalars().first() is not None:
            print(f"Ya existe un usuario con el email {email} (en algún cliente). Aborta.")
            sys.exit(1)

        role_result = await db.execute(select(Role).where(Role.name == UserRole.ADMIN.value))
        admin_role = role_result.scalars().first()
        if admin_role is None:
            print(
                "El rol ADMIN no existe en la base de datos todavía. "
                "Aplica las migraciones (alembic upgrade head) antes de correr esto."
            )
            sys.exit(1)

        final_password = password or _generate_password()

        # AuthService.hash_password, NO middleware.auth.hash_password: el
        # login (routers/auth.py) verifica con AuthService.verify_password,
        # que antes de bcrypt aplica un pre-hash SHA-256 (evita el límite de
        # 72 bytes de bcrypt). middleware.auth.hash_password es un bcrypt
        # liso sin ese pre-hash — un hash suyo nunca verifica en el login.
        # Se detectó porque este mismo bootstrap fallaba con "credenciales
        # incorrectas" usando la contraseña recién creada.
        admin_user = User(
            email=email,
            full_name=full_name,
            hashed_password=AuthService.hash_password(final_password),
            role_id=admin_role.id,
            is_active=True,
            client_id=client.id,
        )
        db.add(admin_user)
        await db.commit()

    print(f"ADMIN creado: {email} (cliente: {client_slug})")
    if not password:
        print(f"Contraseña generada (guárdala ahora, no se puede recuperar): {final_password}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Crea el primer usuario ADMIN de un cliente de CoreStream."
    )
    parser.add_argument("--email", required=True, help="Correo del administrador")
    parser.add_argument("--full-name", default="Administrador", help="Nombre completo")
    parser.add_argument(
        "--client-slug",
        required=True,
        help="Slug del cliente (tenant). Si ya existe, se reusa; si no, requiere --client-name.",
    )
    parser.add_argument(
        "--client-name",
        default=None,
        help="Nombre del cliente, solo necesario si --client-slug todavía no existe.",
    )
    parser.add_argument(
        "--password",
        default=None,
        help="Contraseña a usar. Si se omite, se genera una aleatoria y se imprime una vez.",
    )
    args = parser.parse_args()

    asyncio.run(
        create_admin(args.email, args.password, args.full_name, args.client_slug, args.client_name)
    )


if __name__ == "__main__":
    main()