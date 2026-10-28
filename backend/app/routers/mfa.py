"""
Router de 2FA por TOTP (NEW-08). Todo cuelga de /api/auth/mfa, y por eso el
middleware de auditoría lo registra siempre (prefijo /api/auth/), incluso con
AUDIT_READS=false.

Flujo de login con 2FA:
  POST /api/auth/login              → {mfa_required, mfa_token}
  POST /api/auth/mfa/verify         → sesión completa (mfa_token + código)

Enrolamiento (voluntario, con sesión; u obligatorio, con mfa_token de setup):
  POST /api/auth/mfa/setup          → secreto + QR
  POST /api/auth/mfa/confirm        → activa y entrega los códigos de recuperación
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.context import current_client_id_ctx, set_audit_actor, set_audit_resource
from app.database import get_db
from app.middleware.auth import (
    get_access_token_payload,
    get_current_user,
    require_role,
    verify_token,
)
from app.middleware.rate_limit import rate_limit_mfa
from app.models import Client, User, UserRole
from app.models.mfa import UserIdentity, UserRecoveryCode
from app.redis_client import consume_jti
from app.routers.auth import _remaining_seconds, issue_session
from app.schemas import TokenPayload, TokenResponse
from app.schemas.mfa import (
    MfaConfirmRequest,
    MfaConfirmResponse,
    MfaPasswordCodeRequest,
    MfaPolicyResponse,
    MfaPolicyUpdate,
    MfaRecoveryCodesResponse,
    MfaSetupResponse,
    MfaStatusResponse,
    MfaVerifyRequest,
)
from app.services import mfa_service
from app.services.auth_service import AuthService

router = APIRouter(prefix="/api/auth/mfa", tags=["2FA"])
_bearer = HTTPBearer()


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


async def _load_active_user(db: AsyncSession, user_id: str) -> User:
    try:
        uid = UUID(user_id)
    except (ValueError, TypeError):
        raise _unauthorized("Token inválido")
    user = (
        await db.execute(select(User).options(selectinload(User.role)).where(User.id == uid))
    ).unique().scalar_one_or_none()
    if user is None or not user.is_active:
        raise _unauthorized("Token inválido")
    return user


def _role_name(user: User) -> str:
    return user.role.name if user.role else "DEVELOPER"


def _bind_actor(user: User) -> None:
    current_client_id_ctx.set(user.client_id)
    set_audit_actor(
        user_id=user.id, email=user.email, role=_role_name(user), client_id=user.client_id
    )


# ---------------------------------------------------------------------------
# Quién puede enrolarse: sesión normal, o el mfa_token de setup (política)
# ---------------------------------------------------------------------------

@dataclass
class EnrolmentContext:
    user: User
    payload: TokenPayload
    via_setup_token: bool


async def get_enrolment_context(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> EnrolmentContext:
    token = credentials.credentials
    via_setup = False
    try:
        payload = await verify_token(token, expected_type="access")
    except HTTPException:
        payload = await verify_token(token, expected_type=mfa_service.SETUP_TOKEN_TYPE)
        via_setup = True
    user = await _load_active_user(db, payload.sub)
    _bind_actor(user)
    return EnrolmentContext(user=user, payload=payload, via_setup_token=via_setup)


# ---------------------------------------------------------------------------
# Segundo paso del login
# ---------------------------------------------------------------------------

@router.post("/verify", response_model=TokenResponse, summary="Completar el login con el segundo factor")
async def verify_login(
    body: MfaVerifyRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    payload = await verify_token(body.mfa_token, expected_type=mfa_service.CHALLENGE_TOKEN_TYPE)
    await rate_limit_mfa(request, payload.sub, payload.jti)

    user = await _load_active_user(db, payload.sub)
    _bind_actor(user)
    if not user.totp_enabled:
        raise _unauthorized("Token inválido")

    if not await mfa_service.verify_second_factor(db, user, body.code):
        await db.rollback()
        raise _unauthorized("Código incorrecto")

    # El desafío es de un solo uso: dos /verify simultáneos con el mismo token
    # no pueden abrir dos sesiones.
    if not await consume_jti(payload.jti, _remaining_seconds(payload.exp)):
        await db.rollback()
        raise _unauthorized("El desafío ya fue utilizado")

    await db.commit()
    return issue_session(response, user, _role_name(user))


# ---------------------------------------------------------------------------
# Enrolamiento
# ---------------------------------------------------------------------------

@router.post("/setup", response_model=MfaSetupResponse, summary="Iniciar la configuración del 2FA")
async def setup(
    ctx: EnrolmentContext = Depends(get_enrolment_context),
    db: AsyncSession = Depends(get_db),
) -> MfaSetupResponse:
    user = ctx.user
    if user.totp_enabled:
        raise HTTPException(status.HTTP_409_CONFLICT, "El 2FA ya está activado")

    secret = mfa_service.generate_secret()
    user.totp_secret_encrypted = mfa_service.encrypt_secret(secret)
    user.totp_last_used_step = None
    await db.commit()

    uri = mfa_service.provisioning_uri(secret, user.email)
    return MfaSetupResponse(secret=secret, otpauth_uri=uri, qr_svg=mfa_service.qr_svg(uri))


@router.post("/confirm", response_model=MfaConfirmResponse, summary="Confirmar y activar el 2FA")
async def confirm(
    body: MfaConfirmRequest,
    request: Request,
    response: Response,
    ctx: EnrolmentContext = Depends(get_enrolment_context),
    db: AsyncSession = Depends(get_db),
) -> MfaConfirmResponse:
    user = ctx.user
    await rate_limit_mfa(request, str(user.id), ctx.payload.jti)

    if user.totp_enabled:
        raise HTTPException(status.HTTP_409_CONFLICT, "El 2FA ya está activado")
    if not user.totp_secret_encrypted:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Primero inicia la configuración")
    if not await mfa_service.consume_totp(db, user, body.code):
        await db.rollback()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Código incorrecto")

    user.totp_enabled = True
    user.totp_enabled_at = datetime.now(timezone.utc)
    codes = await mfa_service.replace_recovery_codes(db, user)

    if not ctx.via_setup_token:
        await db.commit()
        return MfaConfirmResponse(recovery_codes=codes)

    # Enrolamiento obligatorio: quien acaba de demostrar que controla el TOTP
    # entra directamente, sin repetir el login.
    if not await consume_jti(ctx.payload.jti, _remaining_seconds(ctx.payload.exp)):
        await db.rollback()
        raise _unauthorized("El token de configuración ya fue utilizado")
    await db.commit()
    session = issue_session(response, user, _role_name(user))
    return MfaConfirmResponse(
        recovery_codes=codes,
        access_token=session.access_token,
        expires_in=session.expires_in,
        must_change_password=session.must_change_password,
    )


# ---------------------------------------------------------------------------
# Gestión (sesión normal)
# ---------------------------------------------------------------------------

async def _require_password_and_code(
    db: AsyncSession, request: Request, user: User, jti: str, body: MfaPasswordCodeRequest
) -> None:
    await rate_limit_mfa(request, str(user.id), jti)
    if not user.totp_enabled:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "El 2FA no está activado")
    if not AuthService.verify_password(body.password, user.hashed_password):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Contraseña incorrecta")
    if not await mfa_service.verify_second_factor(db, user, body.code):
        await db.rollback()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Código incorrecto")


@router.get("/status", response_model=MfaStatusResponse, summary="Estado del 2FA del usuario")
async def mfa_status(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> MfaStatusResponse:
    require = (
        await db.execute(select(Client.require_2fa).where(Client.id == user.client_id))
    ).scalar_one_or_none()
    linked = (
        await db.execute(select(UserIdentity.provider).where(UserIdentity.user_id == user.id))
    ).scalars().all()
    return MfaStatusResponse(
        totp_enabled=user.totp_enabled,
        recovery_codes_remaining=await mfa_service.count_unused_recovery_codes(db, user),
        client_requires_2fa=bool(require),
        sso_linked=sorted(linked),
    )


@router.post("/disable", status_code=status.HTTP_204_NO_CONTENT, summary="Desactivar el 2FA propio")
async def disable(
    body: MfaPasswordCodeRequest,
    request: Request,
    user: User = Depends(get_current_user),
    token: TokenPayload = Depends(get_access_token_payload),
    db: AsyncSession = Depends(get_db),
) -> Response:
    require = (
        await db.execute(select(Client.require_2fa).where(Client.id == user.client_id))
    ).scalar_one_or_none()
    if require:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Tu organización exige 2FA: no se puede desactivar"
        )
    await _require_password_and_code(db, request, user, token.jti, body)
    await _clear_totp(db, user)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/recovery-codes/regenerate",
    response_model=MfaRecoveryCodesResponse,
    summary="Generar un lote nuevo de códigos de recuperación (invalida los anteriores)",
)
async def regenerate_recovery_codes(
    body: MfaPasswordCodeRequest,
    request: Request,
    user: User = Depends(get_current_user),
    token: TokenPayload = Depends(get_access_token_payload),
    db: AsyncSession = Depends(get_db),
) -> MfaRecoveryCodesResponse:
    await _require_password_and_code(db, request, user, token.jti, body)
    codes = await mfa_service.replace_recovery_codes(db, user)
    await db.commit()
    return MfaRecoveryCodesResponse(recovery_codes=codes)


async def _clear_totp(db: AsyncSession, user: User) -> None:
    user.totp_enabled = False
    user.totp_enabled_at = None
    user.totp_secret_encrypted = None
    user.totp_last_used_step = None
    await db.execute(delete(UserRecoveryCode).where(UserRecoveryCode.user_id == user.id))


# ---------------------------------------------------------------------------
# Administración (solo ADMIN del cliente)
# ---------------------------------------------------------------------------

@router.put("/policy", response_model=MfaPolicyResponse, summary="Exigir o no 2FA a todo el cliente")
async def set_policy(
    body: MfaPolicyUpdate,
    admin: User = Depends(require_role([UserRole.ADMIN])),
    db: AsyncSession = Depends(get_db),
) -> MfaPolicyResponse:
    # Evita que el ADMIN se deje fuera: tiene que haber activado el suyo antes.
    if body.require_2fa and not admin.totp_enabled:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Activa primero tu propio 2FA antes de exigirlo a la organización",
        )
    await db.execute(
        update(Client).where(Client.id == admin.client_id).values(require_2fa=body.require_2fa)
    )
    set_audit_resource("client", admin.client_id)
    await db.commit()
    return MfaPolicyResponse(require_2fa=body.require_2fa)


@router.delete(
    "/users/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Resetear el 2FA de un usuario (perdió el dispositivo y los códigos)",
)
async def admin_reset_user_mfa(
    user_id: UUID,
    admin: User = Depends(require_role([UserRole.ADMIN])),
    db: AsyncSession = Depends(get_db),
) -> Response:
    target = (
        await db.execute(
            select(User).where(User.id == user_id, User.client_id == admin.client_id)
        )
    ).scalar_one_or_none()
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario no encontrado")
    set_audit_resource("user", target.id)
    await _clear_totp(db, target)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
