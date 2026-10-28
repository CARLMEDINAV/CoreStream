"""Esquemas de 2FA (TOTP) y SSO (NEW-08)."""

from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.user import TokenResponse


class LoginResponse(TokenResponse):
    """
    Respuesta de /auth/login. Igual que TokenResponse cuando no hay segundo
    factor; si lo hay, access_token viene vacío y se rellenan los otros campos.
    """

    access_token: Optional[str] = None
    token_type: str = "bearer"
    mfa_required: bool = False
    mfa_setup_required: bool = False
    mfa_token: Optional[str] = None


class MfaVerifyRequest(BaseModel):
    mfa_token: str = Field(..., max_length=2048)
    # 6 dígitos del autenticador, o un código de recuperación (XXXXX-XXXXX).
    code: str = Field(..., min_length=1, max_length=32)


class MfaSetupResponse(BaseModel):
    secret: str  # para quien prefiera teclearlo en vez de escanear el QR
    otpauth_uri: str
    qr_svg: str


class MfaConfirmRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=16)


class MfaConfirmResponse(BaseModel):
    recovery_codes: list[str]
    # Solo si el enrolamiento se hizo con un mfa_token (política obligatoria):
    # entonces la confirmación abre la sesión directamente.
    access_token: Optional[str] = None
    token_type: str = "bearer"
    expires_in: Optional[int] = None
    must_change_password: bool = False


class MfaPasswordCodeRequest(BaseModel):
    """Acciones sensibles: contraseña actual + un código válido."""

    password: str = Field(..., max_length=128)
    code: str = Field(..., min_length=1, max_length=32)


class MfaRecoveryCodesResponse(BaseModel):
    recovery_codes: list[str]


class MfaStatusResponse(BaseModel):
    totp_enabled: bool
    recovery_codes_remaining: int
    client_requires_2fa: bool
    sso_linked: list[str]


class MfaPolicyUpdate(BaseModel):
    require_2fa: bool


class MfaPolicyResponse(BaseModel):
    require_2fa: bool


class SsoProviderInfo(BaseModel):
    id: str
    name: str


class SsoProvidersResponse(BaseModel):
    providers: list[SsoProviderInfo]
