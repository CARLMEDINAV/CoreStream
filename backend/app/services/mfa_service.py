"""
Servicio de 2FA por TOTP (NEW-08).

Piezas:
- Cifrado del secreto TOTP en reposo (Fernet).
- Verificación de códigos con ventana de ±1 paso y protección contra reuso
  (un código ya aceptado no vale una segunda vez, ni en paralelo).
- Códigos de recuperación de un solo uso, guardados como HMAC.
- Tokens intermedios: "mfa_challenge" (contraseña correcta, falta el código) y
  "mfa_setup" (la política exige 2FA y el usuario aún no lo tiene). Ninguno
  sirve como access token: verify_token exige el `type` exacto.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import io
import secrets
import time
from datetime import datetime, timedelta, timezone

import pyotp
import qrcode
import qrcode.image.svg
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.middleware.auth import _create_token
from app.models import User
from app.models.mfa import UserRecoveryCode

TOTP_PERIOD = 30
TOTP_DIGITS = 6
RECOVERY_CODE_COUNT = 10

# Sin caracteres ambiguos (0/O, 1/I/L): el código se teclea a mano desde un papel.
_RECOVERY_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"

CHALLENGE_TOKEN_TYPE = "mfa_challenge"
SETUP_TOKEN_TYPE = "mfa_setup"
SETUP_TOKEN_TTL_SECONDS = 600


# ---------------------------------------------------------------------------
# Reloj (aislado para poder adelantarlo en los tests)
# ---------------------------------------------------------------------------

def _now() -> float:
    return time.time()


# ---------------------------------------------------------------------------
# Cifrado del secreto
# ---------------------------------------------------------------------------

def _key_material() -> bytes:
    """Clave Fernet. En desarrollo, si no hay una propia, se deriva de SECRET_KEY."""
    settings = get_settings()
    if settings.MFA_ENCRYPTION_KEY:
        return settings.MFA_ENCRYPTION_KEY.encode()
    return base64.urlsafe_b64encode(
        hashlib.sha256(b"corestream-mfa:" + settings.SECRET_KEY.encode()).digest()
    )


def encrypt_secret(secret: str) -> str:
    return Fernet(_key_material()).encrypt(secret.encode()).decode()


def decrypt_secret(token: str) -> str:
    try:
        return Fernet(_key_material()).decrypt(token.encode()).decode()
    except InvalidToken as exc:  # clave rotada o dato corrupto
        raise RuntimeError("No se pudo descifrar el secreto TOTP (¿cambió MFA_ENCRYPTION_KEY?)") from exc


# ---------------------------------------------------------------------------
# Enrolamiento
# ---------------------------------------------------------------------------

def generate_secret() -> str:
    return pyotp.random_base32()  # 32 caracteres base32 = 160 bits


def provisioning_uri(secret: str, email: str) -> str:
    return pyotp.TOTP(secret, digits=TOTP_DIGITS, interval=TOTP_PERIOD).provisioning_uri(
        name=email, issuer_name=get_settings().MFA_ISSUER
    )


def qr_svg(uri: str) -> str:
    """QR como SVG (sin Pillow). El frontend lo muestra con <img src="data:image/svg+xml;...">."""
    img = qrcode.make(uri, image_factory=qrcode.image.svg.SvgPathImage, box_size=8, border=2)
    buf = io.BytesIO()
    img.save(buf)
    return buf.getvalue().decode()


# ---------------------------------------------------------------------------
# Verificación de códigos
# ---------------------------------------------------------------------------

def looks_like_totp(code: str) -> bool:
    cleaned = code.replace(" ", "")
    return len(cleaned) == TOTP_DIGITS and cleaned.isdigit()


def match_totp_step(secret: str, code: str, last_used_step: int | None) -> int | None:
    """
    Devuelve el paso de 30 s al que corresponde `code`, o None.

    Acepta el paso anterior, el actual y el siguiente (relojes algo
    desfasados), pero nunca uno <= last_used_step. Recorre los tres pasos
    siempre y compara en tiempo constante para no filtrar nada por tiempos.
    """
    cleaned = code.replace(" ", "")
    if not looks_like_totp(cleaned):
        return None

    totp = pyotp.TOTP(secret, digits=TOTP_DIGITS, interval=TOTP_PERIOD)
    current = int(_now() // TOTP_PERIOD)
    matched: int | None = None
    for step in (current - 1, current, current + 1):
        expected = totp.at(step * TOTP_PERIOD)
        if hmac.compare_digest(expected, cleaned) and (
            last_used_step is None or step > last_used_step
        ):
            matched = step
    return matched


async def consume_totp(db: AsyncSession, user: User, code: str) -> bool:
    """
    Valida `code` contra el secreto del usuario y marca el paso como usado.

    El UPDATE condicional hace la marca atómica: dos peticiones simultáneas con
    el mismo código no pueden ganar las dos (rowcount == 1 solo en una).
    No hace commit: lo hace el llamador.
    """
    if not user.totp_secret_encrypted:
        return False
    step = match_totp_step(
        decrypt_secret(user.totp_secret_encrypted), code, user.totp_last_used_step
    )
    if step is None:
        return False

    result = await db.execute(
        update(User)
        .where(
            User.id == user.id,
            (User.totp_last_used_step.is_(None)) | (User.totp_last_used_step < step),
        )
        .values(totp_last_used_step=step)
    )
    if result.rowcount != 1:
        return False
    user.totp_last_used_step = step
    return True


# ---------------------------------------------------------------------------
# Códigos de recuperación
# ---------------------------------------------------------------------------

def _recovery_hmac_key() -> bytes:
    return hashlib.sha256(b"corestream-recovery:" + _key_material()).digest()


def normalize_recovery_code(code: str) -> str:
    return code.replace("-", "").replace(" ", "").upper()


def hash_recovery_code(code: str) -> str:
    return hmac.new(
        _recovery_hmac_key(), normalize_recovery_code(code).encode(), hashlib.sha256
    ).hexdigest()


def _new_recovery_code() -> str:
    raw = "".join(secrets.choice(_RECOVERY_ALPHABET) for _ in range(10))
    return f"{raw[:5]}-{raw[5:]}"


async def replace_recovery_codes(db: AsyncSession, user: User) -> list[str]:
    """Borra los códigos anteriores y crea un lote nuevo. Devuelve los códigos en claro (única vez)."""
    await db.execute(delete(UserRecoveryCode).where(UserRecoveryCode.user_id == user.id))
    codes = [_new_recovery_code() for _ in range(RECOVERY_CODE_COUNT)]
    for code in codes:
        db.add(
            UserRecoveryCode(
                user_id=user.id, client_id=user.client_id, code_hash=hash_recovery_code(code)
            )
        )
    return codes


async def consume_recovery_code(db: AsyncSession, user: User, code: str) -> bool:
    """Marca el código como usado de forma atómica. True si esta llamada lo consumió."""
    if len(normalize_recovery_code(code)) != 10:
        return False
    result = await db.execute(
        update(UserRecoveryCode)
        .where(
            UserRecoveryCode.user_id == user.id,
            UserRecoveryCode.code_hash == hash_recovery_code(code),
            UserRecoveryCode.used_at.is_(None),
        )
        .values(used_at=datetime.now(timezone.utc))
    )
    return result.rowcount == 1


async def count_unused_recovery_codes(db: AsyncSession, user: User) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(UserRecoveryCode)
        .where(UserRecoveryCode.user_id == user.id, UserRecoveryCode.used_at.is_(None))
    )
    return int(result.scalar_one())


async def verify_second_factor(db: AsyncSession, user: User, code: str) -> bool:
    """TOTP si el código tiene forma de TOTP; si no, se intenta como código de recuperación."""
    if looks_like_totp(code):
        return await consume_totp(db, user, code)
    return await consume_recovery_code(db, user, code)


# ---------------------------------------------------------------------------
# Tokens intermedios
# ---------------------------------------------------------------------------

def _claims(user: User, role_name: str) -> dict:
    return {"sub": str(user.id), "role": role_name, "client_id": str(user.client_id)}


def create_challenge_token(user: User, role_name: str) -> str:
    ttl = get_settings().MFA_CHALLENGE_TTL_SECONDS
    return _create_token(
        _claims(user, role_name),
        token_type=CHALLENGE_TOKEN_TYPE,
        expire=datetime.now(timezone.utc) + timedelta(seconds=ttl),
    )


def create_setup_token(user: User, role_name: str) -> str:
    return _create_token(
        _claims(user, role_name),
        token_type=SETUP_TOKEN_TYPE,
        expire=datetime.now(timezone.utc) + timedelta(seconds=SETUP_TOKEN_TTL_SECONDS),
    )
