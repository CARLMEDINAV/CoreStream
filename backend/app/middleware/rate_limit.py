"""
Rate limiting sencillo basado en Redis (plan 3.5).

No se usa slowapi ni ninguna dependencia nueva: un contador de ventana fija
por clave (IP, o IP+email) es suficiente para lo que hace falta aquí —
frenar fuerza bruta contra /auth/login — y Redis ya está disponible en toda
la aplicación.

Antes: 25 intentos de login fallidos consecutivos, todos respondidos con 401,
ninguno bloqueado. Verificado en la auditoría inicial.

Criterio de diseño (NEW-08): la barrera real contra la fuerza bruta es el
límite POR CUENTA (y, en el 2FA, por desafío). El límite por IP es solo un
freno contra inundaciones y debe ser holgado, porque una IP NO identifica a
un usuario: toda una oficina sale por la misma IP pública, y detrás de un
proxy mal configurado todos los usuarios aparecerían con la misma. Un tope
por IP estricto permite que unos pocos intentos de uno bloqueen a todos.
"""

from __future__ import annotations

import logging

from fastapi import HTTPException, Request, status

from app.redis_client import get_redis

logger = logging.getLogger(__name__)

_PREFIX = "corestream:ratelimit:"

# ---- Topes (ventana de 5 min en todos) -------------------------------------
# Por IP: holgados a propósito (ver docstring del módulo).
LOGIN_IP_MAX = 60
MFA_IP_MAX = 100
SSO_IP_MAX = 60
# Por cuenta / desafío: estrictos, son la protección de verdad.
LOGIN_EMAIL_MAX = 8
MFA_USER_MAX = 6      # un TOTP son solo 10^6 combinaciones
MFA_CHALLENGE_MAX = 5
WINDOW_SECONDS = 300


async def _hit(
    key: str,
    *,
    max_attempts: int,
    window_seconds: int,
    fail_open: bool = True,
) -> None:
    """
    Incrementa el contador de `key` y lanza 429 si supera max_attempts
    dentro de la ventana.

    Si Redis falla (caído, o el plan gratuito de Upstash sin comandos):
    - fail_open=True  -> se deja pasar la petición (se registra el error).
      Es lo que queremos para los límites por IP y por email del login: una
      caída de Redis no debe impedir que TODOS inicien sesión.
    - fail_open=False -> 503. Para los límites del 2FA por cuenta/desafío,
      donde dejar pasar sin límite permitiría adivinar el código.

    Si el proceso muere entre INCR y EXPIRE, la clave quedaría sin caducidad
    y bloquearía a esa IP/cuenta para siempre. Se repara aquí: cuando la
    clave está bloqueando y no tiene TTL, se le pone uno.
    """
    full_key = f"{_PREFIX}{key}"
    ttl = window_seconds
    try:
        redis = await get_redis()
        count = await redis.incr(full_key)
        if count == 1:
            await redis.expire(full_key, window_seconds)

        if count > max_attempts:
            ttl = await redis.ttl(full_key)
            if ttl < 0:  # -1: sin caducidad (clave huérfana); -2: ya no existe
                await redis.expire(full_key, window_seconds)
                ttl = window_seconds
    except Exception:
        logger.exception("Rate limit: Redis no disponible (clave %s)", key)
        if fail_open:
            return
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Servicio temporalmente no disponible. Intenta de nuevo en unos minutos.",
        )

    if count > max_attempts:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiados intentos. Intenta de nuevo más tarde.",
            headers={"Retry-After": str(max(ttl, 1))},
        )


def _client_ip(request: Request) -> str:
    # uvicorn ya resuelve X-Forwarded-For por su cuenta (--forwarded-allow-ips
    # en backend/Dockerfile, o la variable FORWARDED_ALLOW_IPS en Render), así
    # que request.client.host es la IP del cliente y no hay que leer la
    # cabecera a mano. Es de fiar solo si esa variable apunta al proxy
    # concreto: con "*" el cliente puede elegir qué IP se cuenta aquí. Por eso
    # el límite por IP es holgado y no es la barrera principal.
    return request.client.host if request.client else "desconocido"


async def rate_limit_login(request: Request, email: str | None = None) -> None:
    """
    Límite combinado por IP y por cuenta sobre /auth/login.

    Por IP: freno de inundación / barrido de credenciales contra muchos
    emails (holgado: ver docstring del módulo).
    Por cuenta: una cuenta concreta no puede recibir más de LOGIN_EMAIL_MAX
    intentos/5min sin importar desde cuántas IPs (frena el ataque distribuido
    contra una sola cuenta).
    """
    ip = _client_ip(request)
    await _hit(f"login:ip:{ip}", max_attempts=LOGIN_IP_MAX, window_seconds=WINDOW_SECONDS)
    if email:
        await _hit(
            f"login:email:{email.lower().strip()}",
            max_attempts=LOGIN_EMAIL_MAX,
            window_seconds=WINDOW_SECONDS,
        )


async def rate_limit_mfa(request: Request, user_id: str, challenge_jti: str) -> None:
    """
    Frena la fuerza bruta contra el segundo factor (NEW-08). Un TOTP son solo
    10^6 combinaciones: sin límite por cuenta sería adivinable.

    Por IP: holgado (freno de inundación, fail-open).
    Por cuenta: 6/5min sin importar el origen (fail-closed).
    Por desafío: 5 intentos, pasados los cuales hay que volver a introducir
    la contraseña (fail-closed).
    """
    await _hit(
        f"mfa:ip:{_client_ip(request)}",
        max_attempts=MFA_IP_MAX,
        window_seconds=WINDOW_SECONDS,
    )
    await _hit(
        f"mfa:user:{user_id}",
        max_attempts=MFA_USER_MAX,
        window_seconds=WINDOW_SECONDS,
        fail_open=False,
    )
    await _hit(
        f"mfa:jti:{challenge_jti}",
        max_attempts=MFA_CHALLENGE_MAX,
        window_seconds=WINDOW_SECONDS,
        fail_open=False,
    )


async def rate_limit_sso(request: Request) -> None:
    """Límite por IP sobre el inicio y el retorno del login SSO."""
    await _hit(
        f"sso:ip:{_client_ip(request)}",
        max_attempts=SSO_IP_MAX,
        window_seconds=WINDOW_SECONDS,
    )
