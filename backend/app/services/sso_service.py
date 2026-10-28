"""
Login SSO con Google y Microsoft (NEW-08) — OpenID Connect, flujo de código
de autorización con PKCE.

Sin librerías nuevas: httpx (ya instalado) para hablar con el proveedor y
python-jose (ya instalado) para validar la firma del id_token. El estado de la
operación (state, nonce, code_verifier) vive en Redis, 10 minutos, y se
consume de un solo uso; así no hace falta SessionMiddleware ni cookies extra.

Regla de producto: SSO NO crea usuarios. Solo entra quien ya existe y está
activo en CoreStream; rol y cliente salen de su cuenta, no del proveedor.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import re
import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlencode

import httpx
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.models import User
from app.models.mfa import UserIdentity
from app.redis_client import get_redis

logger = logging.getLogger("corestream.sso")

_STATE_PREFIX = "corestream:sso_state:"
_STATE_TTL = 600
_HTTP_TIMEOUT = 10.0
_GUID = re.compile(r"^[0-9a-fA-F]{8}-([0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}$")


class SsoError(Exception):
    """Fallo del login SSO. `code` es un identificador corto y seguro de mostrar."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(detail or code)
        self.code = code


@dataclass(frozen=True)
class ProviderConfig:
    id: str
    name: str
    client_id: str
    client_secret: str
    authorize_url: str
    token_url: str
    jwks_url: str
    scope: str = "openid email profile"


@dataclass(frozen=True)
class SsoIdentity:
    provider: str
    subject: str
    email: str | None
    email_trusted: bool  # ¿se puede enlazar a un usuario por este correo?


# ---------------------------------------------------------------------------
# Proveedores configurados
# ---------------------------------------------------------------------------

def get_providers() -> dict[str, ProviderConfig]:
    s = get_settings()
    out: dict[str, ProviderConfig] = {}
    if s.GOOGLE_CLIENT_ID and s.GOOGLE_CLIENT_SECRET:
        out["google"] = ProviderConfig(
            id="google",
            name="Google",
            client_id=s.GOOGLE_CLIENT_ID,
            client_secret=s.GOOGLE_CLIENT_SECRET,
            authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
            token_url="https://oauth2.googleapis.com/token",
            jwks_url="https://www.googleapis.com/oauth2/v3/certs",
        )
    if s.MICROSOFT_CLIENT_ID and s.MICROSOFT_CLIENT_SECRET:
        t = s.MICROSOFT_TENANT
        base = f"https://login.microsoftonline.com/{t}"
        out["microsoft"] = ProviderConfig(
            id="microsoft",
            name="Microsoft",
            client_id=s.MICROSOFT_CLIENT_ID,
            client_secret=s.MICROSOFT_CLIENT_SECRET,
            authorize_url=f"{base}/oauth2/v2.0/authorize",
            token_url=f"{base}/oauth2/v2.0/token",
            jwks_url=f"{base}/discovery/v2.0/keys",
        )
    return out


def redirect_uri(provider_id: str) -> str:
    return f"{get_settings().SSO_PUBLIC_BASE_URL.rstrip('/')}/api/auth/sso/{provider_id}/callback"


# ---------------------------------------------------------------------------
# Paso 1: construir la URL de autorización
# ---------------------------------------------------------------------------

def _pkce_challenge(verifier: str) -> str:
    return base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()


async def start(cfg: ProviderConfig) -> str:
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)

    redis = await get_redis()
    await redis.set(
        f"{_STATE_PREFIX}{state}",
        json.dumps({"provider": cfg.id, "nonce": nonce, "verifier": verifier}),
        ex=_STATE_TTL,
    )

    params = {
        "response_type": "code",
        "client_id": cfg.client_id,
        "redirect_uri": redirect_uri(cfg.id),
        "scope": cfg.scope,
        "state": state,
        "nonce": nonce,
        "code_challenge": _pkce_challenge(verifier),
        "code_challenge_method": "S256",
    }
    if cfg.id == "google":
        params["prompt"] = "select_account"
    return f"{cfg.authorize_url}?{urlencode(params)}"


# ---------------------------------------------------------------------------
# Paso 2: validar el id_token (función pura, testeable con un JWKS local)
# ---------------------------------------------------------------------------

def _microsoft_tenant_is_specific(tenant: str) -> bool:
    return bool(_GUID.match(tenant))


def verify_id_token(
    cfg: ProviderConfig, id_token: str, expected_nonce: str, jwks: dict
) -> SsoIdentity:
    try:
        claims = jwt.decode(
            id_token,
            jwks,
            algorithms=["RS256"],
            audience=cfg.client_id,
            options={"verify_iss": False, "verify_at_hash": False},
        )
    except JWTError as exc:
        raise SsoError("token_invalid", str(exc)) from exc

    nonce = claims.get("nonce")
    if not isinstance(nonce, str) or not hmac.compare_digest(nonce, expected_nonce):
        raise SsoError("nonce_invalid")

    subject = claims.get("sub")
    if not subject:
        raise SsoError("token_invalid", "sin sub")
    iss = claims.get("iss", "")

    if cfg.id == "google":
        if iss not in ("https://accounts.google.com", "accounts.google.com"):
            raise SsoError("issuer_invalid")
        verified = claims.get("email_verified")
        trusted = verified is True or verified == "true"
        return SsoIdentity("google", subject, claims.get("email"), trusted)

    if cfg.id == "microsoft":
        tid = claims.get("tid")
        if not tid or iss != f"https://login.microsoftonline.com/{tid}/v2.0":
            raise SsoError("issuer_invalid")
        tenant = get_settings().MICROSOFT_TENANT
        specific = _microsoft_tenant_is_specific(tenant)
        if specific and tid.lower() != tenant.lower():
            raise SsoError("tenant_invalid")
        # El claim `email` de Microsoft no está verificado y en multi-tenant lo
        # puede fijar el administrador de cualquier organización ("nOAuth"):
        # solo es de fiar si el tenant es el de la empresa. Con "common" el
        # correo no sirve para el PRIMER enlace; las cuentas ya enlazadas por
        # `sub` siguen entrando.
        email = claims.get("email") or claims.get("preferred_username")
        return SsoIdentity("microsoft", subject, email, specific)

    raise SsoError("provider_unknown")


# ---------------------------------------------------------------------------
# Paso 3: canjear el código
# ---------------------------------------------------------------------------

_jwks_cache: dict[str, tuple[float, dict]] = {}
_JWKS_TTL = 3600


async def _get_jwks(url: str, *, force: bool = False) -> dict:
    cached = _jwks_cache.get(url)
    if cached and not force and time.time() - cached[0] < _JWKS_TTL:
        return cached[1]
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        jwks = resp.json()
    _jwks_cache[url] = (time.time(), jwks)
    return jwks


async def finish(cfg: ProviderConfig, code: str, state: str) -> SsoIdentity:
    redis = await get_redis()
    raw = await redis.getdel(f"{_STATE_PREFIX}{state}")  # de un solo uso
    if raw is None:
        raise SsoError("state_invalid")
    saved = json.loads(raw)
    if saved.get("provider") != cfg.id:
        raise SsoError("state_invalid")

    try:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            resp = await client.post(
                cfg.token_url,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri(cfg.id),
                    "client_id": cfg.client_id,
                    "client_secret": cfg.client_secret,
                    "code_verifier": saved["verifier"],
                },
                headers={"Accept": "application/json"},
            )
        if resp.status_code != 200:
            logger.warning("SSO %s: el proveedor rechazó el código (%s)", cfg.id, resp.status_code)
            raise SsoError("exchange_failed")
        id_token = resp.json().get("id_token")
        if not id_token:
            raise SsoError("exchange_failed", "sin id_token")

        jwks = await _get_jwks(cfg.jwks_url)
        try:
            return verify_id_token(cfg, id_token, saved["nonce"], jwks)
        except SsoError as exc:
            if exc.code != "token_invalid":
                raise
            # Posible rotación de claves del proveedor: un reintento con JWKS fresco.
            jwks = await _get_jwks(cfg.jwks_url, force=True)
            return verify_id_token(cfg, id_token, saved["nonce"], jwks)
    except httpx.HTTPError as exc:
        logger.warning("SSO %s: error de red con el proveedor: %s", cfg.id, exc)
        raise SsoError("provider_unreachable") from exc


# ---------------------------------------------------------------------------
# Paso 4: resolver el usuario (solo existentes)
# ---------------------------------------------------------------------------

async def resolve_user(db: AsyncSession, ident: SsoIdentity) -> User | None:
    """
    1. Identidad ya enlazada (provider, sub) → ese usuario.
    2. Si no, y el correo es de fiar → usuario con ese correo, y se enlaza.
    3. En cualquier otro caso → None (no se crea nada).
    El llamador comprueba is_active y hace commit.
    """
    identity = (
        await db.execute(
            select(UserIdentity).where(
                UserIdentity.provider == ident.provider, UserIdentity.subject == ident.subject
            )
        )
    ).scalar_one_or_none()

    if identity is not None:
        user = (
            await db.execute(
                select(User).options(selectinload(User.role)).where(User.id == identity.user_id)
            )
        ).unique().scalar_one_or_none()
        if user is not None:
            identity.last_login_at = datetime.now(timezone.utc)
        return user

    if not ident.email or not ident.email_trusted:
        return None

    user = (
        await db.execute(
            select(User)
            .options(selectinload(User.role))
            .where(User.email == ident.email.lower().strip())
        )
    ).unique().scalar_one_or_none()
    if user is None:
        return None

    already = (
        await db.execute(
            select(UserIdentity.id).where(
                UserIdentity.user_id == user.id, UserIdentity.provider == ident.provider
            )
        )
    ).first()
    if already:
        # Esta cuenta ya está enlazada a OTRA identidad del proveedor: no se
        # permite que una segunda cuenta externa con el mismo correo la tome.
        return None

    db.add(
        UserIdentity(
            user_id=user.id,
            client_id=user.client_id,
            provider=ident.provider,
            subject=ident.subject,
            email=ident.email,
            last_login_at=datetime.now(timezone.utc),
        )
    )
    return user
