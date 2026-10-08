"""
Comprueba si un .env dejaría arrancar el backend, sin levantar nada.

Las reglas de producción de app/config.py abortan el proceso antes de servir
la primera petición: con el contenedor eso se traduce en un reinicio en bucle
y hay que ir a buscar el motivo en los logs. Esto las evalúa en seco.

    python scripts/check_env.py ../.env

Sin argumento usa ../.env. Devuelve 0 si arrancaría, 1 si no.
"""

from __future__ import annotations

import pathlib
import sys

from dotenv import dotenv_values
from pydantic import ValidationError

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app.config import Settings, validate_http_runtime

DEFAULT_ENV = pathlib.Path(__file__).resolve().parents[2] / ".env"


def main() -> int:
    ruta = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_ENV

    if not ruta.exists():
        print(f"No existe {ruta}")
        return 1

    # Solo las claves que Settings conoce: el .env compartido también lleva
    # variables de Compose y del frontend que no son de la aplicación.
    crudo = {k: v for k, v in dotenv_values(ruta).items() if v is not None}
    conocidas = {k: v for k, v in crudo.items() if k in Settings.model_fields}

    try:
        settings = Settings(**conocidas)
    except ValidationError as error:
        print(f"ABORTA — el backend no arrancaría con {ruta}:\n")
        for detalle in error.errors():
            print("  -", detalle["msg"].replace("Value error, ", ""))
        return 1

    # Lo que solo aplica al proceso que sirve HTTP (el worker no lo valida).
    try:
        validate_http_runtime(settings)
    except ValueError as error:
        print(f"ABORTA — la API no arrancaría con {ruta}:\n")
        print("  -", error)
        return 1

    print(f"OK — el backend arrancaría con {ruta}")
    print(f"    ENVIRONMENT         = {settings.ENVIRONMENT}")
    print(f"    DEBUG               = {settings.DEBUG}")
    print(f"    SECRET_KEY          = {len(settings.SECRET_KEY)} caracteres")
    print(f"    ALLOWED_ORIGINS     = {settings.ALLOWED_ORIGINS}")
    print(f"    FORWARDED_ALLOW_IPS = {settings.FORWARDED_ALLOW_IPS!r}")

    # Lo que config.py no puede comprobar: que PostgreSQL y Redis respondan.
    # Alembic corre antes de uvicorn, así que un Postgres inalcanzable también
    # impide arrancar, pero eso solo se sabe intentándolo.
    print("\n  Falta por comprobar en la VM (esto no lo valida la config):")
    print("    - PostgreSQL alcanzable: alembic upgrade head corre antes de uvicorn")
    print("    - el usuario debe poder crear el esquema audit (es dueño de la base)")
    print("    - Redis alcanzable: no impide arrancar, pero deja /api/health en 503")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
