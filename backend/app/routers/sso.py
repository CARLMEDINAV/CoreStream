"""
Router de login SSO (Google / Microsoft) — NEW-08.

  GET /api/auth/sso/providers              → proveedores configurados
  GET /api/auth/sso/{provider}/login       → redirige al proveedor
  GET /api/auth/sso/{provider}/callback    → vuelve del proveedor, abre sesión

Tras un login correcto se redirige al frontend con las cookies de refresh y
CSRF ya puestas; el frontend llama a POST /api/auth/refresh para obtener su
access token en memoria (el mismo mecanismo que al recargar la página).

Los fallos responden 403 con una mini-página que reenvía al frontend con
?sso_error=<código>. Se usa un 403 y no un 302 para que la auditoría
(TRV-07) los registre como accesos denegados y no como éxitos.
"""

from __future__ import annotations

import html
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.context import set_audit_actor, set_audit_subject
from app.database import get_db
from app.middleware.rate_limit import rate_limit_sso
from app.routers.auth import issue_session
from app.schemas.mfa import SsoProviderInfo, SsoProvidersResponse
from app.services import sso_service

router = APIRouter(prefix="/api/auth/sso", tags=["SSO"])


def _frontend_login_url(**params: str) -> str:
    base = get_settings().SSO_FRONTEND_URL.rstrip("/")
    return f"{base}/login?{urlencode(params)}"


def _failure(code: str) -> HTMLResponse:
    target = html.escape(_frontend_login_url(sso_error=code), quote=True)
    body = (
        '<!doctype html><meta charset="utf-8">'
        f'<meta http-equiv="refresh" content="0;url={target}">'
        f'<p>No se pudo iniciar sesión. <a href="{target}">Volver</a></p>'
    )
    return HTMLResponse(content=body, status_code=status.HTTP_403_FORBIDDEN)


@router.get("/providers", response_model=SsoProvidersResponse)
async def list_providers() -> SsoProvidersResponse:
    return SsoProvidersResponse(
        providers=[SsoProviderInfo(id=p.id, name=p.name) for p in sso_service.get_providers().values()]
    )


@router.get("/{provider}/login")
async def sso_login(provider: str, request: Request) -> RedirectResponse:
    await rate_limit_sso(request)
    cfg = sso_service.get_providers().get(provider)
    if cfg is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Proveedor SSO no disponible")
    return RedirectResponse(await sso_service.start(cfg), status_code=status.HTTP_302_FOUND)


@router.get("/{provider}/callback")
async def sso_callback(
    provider: str,
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    await rate_limit_sso(request)

    cfg = sso_service.get_providers().get(provider)
    if cfg is None:
        return _failure("provider_unknown")
    if error:
        return _failure("provider_denied")
    if not code or not state:
        return _failure("state_invalid")

    try:
        identity = await sso_service.finish(cfg, code, state)
    except sso_service.SsoError as exc:
        return _failure(exc.code)

    if identity.email:
        set_audit_subject(identity.email.lower())

    user = await sso_service.resolve_user(db, identity)
    if user is None:
        await db.rollback()
        return _failure("no_account")
    if not user.is_active:
        await db.rollback()
        return _failure("inactive")

    role_name = user.role.name if user.role else "DEVELOPER"
    set_audit_actor(
        user_id=user.id, email=user.email, role=role_name, client_id=user.client_id
    )
    redirect = RedirectResponse(
        _frontend_login_url(sso="success"), status_code=status.HTTP_303_SEE_OTHER
    )
    issue_session(redirect, user, role_name)
    await db.commit()
    return redirect
