"""consola comercial reservada a operadores internos."""
from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, StrictBool, field_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.middleware.auth import get_current_user
from app.middleware.request_id import get_request_id
from app.models import AuditLog, Client, User
from app.plans import (
    ALL_FEATURES,
    ENTERPRISE_FEATURES,
    PREMIUM_FEATURES,
    features_for,
    retention_cutoff,
)
from app.services.audit_records import build_entry


async def require_platform_admin(
    usuario: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
) -> User:
    ajustes = get_settings()
    if (
        not usuario.is_active
        or usuario.id not in ajustes.PLATFORM_ADMIN_IDS
        or usuario.client_id != ajustes.PLATFORM_CLIENT_ID
    ):
        raise HTTPException(403, "Acceso exclusivo de administración de plataforma")
    cliente = await db.get(Client, usuario.client_id)
    if cliente is None or not cliente.is_active:
        raise HTTPException(403, "Organización interna inactiva")
    return usuario


router = APIRouter(
    prefix="/api/platform", tags=["Plataforma"],
    dependencies=[Depends(require_platform_admin)],
)


@router.get("/access")
async def consultar_acceso():
    return {"allowed": True}


class PerfilComercial(BaseModel):
    model_config = ConfigDict(extra="forbid")
    plan: Literal["Basico", "Pro", "Enterprise"]
    feature_overrides: dict[str, StrictBool]

    @field_validator("feature_overrides")
    @classmethod
    def validar_banderas(cls, banderas):
        if banderas.keys() - ALL_FEATURES:
            raise ValueError("Feature flag desconocida")
        return banderas


def perfil_cliente(cliente: Client) -> dict:
    habilitadas = features_for(
        cliente.commercial_plan, is_active=cliente.is_active, overrides=cliente.feature_overrides,
    )
    return {
        "id": cliente.id, "name": cliente.name, "is_active": cliente.is_active,
        "plan": cliente.commercial_plan, "feature_overrides": cliente.feature_overrides,
        "feature_flags": {bandera: bandera in habilitadas for bandera in sorted(ALL_FEATURES)},
    }


@router.get("/clients")
async def listar_clientes(
    offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    clientes = (await db.scalars(
        select(Client).order_by(Client.name, Client.id).offset(offset).limit(limit)
    )).all()
    return [perfil_cliente(cliente) for cliente in clientes]


@router.put("/clients/{cliente_id}")
async def actualizar_perfil(
    cliente_id: UUID, datos: PerfilComercial, request: Request,
    usuario: User = Depends(require_platform_admin), db: AsyncSession = Depends(get_db),
):
    cliente = await db.scalar(select(Client).where(Client.id == cliente_id).with_for_update())
    if cliente is None:
        raise HTTPException(404, "Cliente no encontrado")
    anterior = {"plan": cliente.commercial_plan, "feature_overrides": cliente.feature_overrides}
    cliente.commercial_plan = datos.plan
    cliente.feature_overrides = datos.feature_overrides
    # el cambio y su evidencia se confirman en la misma transaccion.
    db.add(AuditLog(
        **build_entry(
            method="PUT", path=request.url.path, status_code=200,
            request_id=get_request_id(), client_id=cliente.id,
            actor_user_id=usuario.id, actor_email=usuario.email,
            actor_role="PLATFORM_ADMIN", resource_type="commercial_profile", resource_id=cliente.id,
            ip=request.client.host if request.client else None,
            user_agent=(request.headers.get("user-agent") or "")[:512] or None,
        ),
        commercial_detail={"before": anterior, "after": datos.model_dump()},
    ))
    await db.commit()
    return perfil_cliente(cliente)


@router.get("/clients/{cliente_id}/usage")
async def consultar_uso(
    cliente_id: UUID, days: int = Query(30, ge=1, le=730),
    db: AsyncSession = Depends(get_db),
):
    cliente = await db.get(Client, cliente_id)
    if cliente is None:
        raise HTTPException(404, "Cliente no encontrado")
    desde = max(
        datetime.now(timezone.utc) - timedelta(days=days),
        retention_cutoff(cliente.commercial_plan),
    )
    filas = (await db.execute(
        select(AuditLog.feature_flag, func.count(AuditLog.id))
        .where(
            AuditLog.client_id == cliente_id, AuditLog.occurred_at >= desde,
            AuditLog.feature_flag.in_(PREMIUM_FEATURES | ENTERPRISE_FEATURES),
            AuditLog.outcome == "SUCCESS",
        ).group_by(AuditLog.feature_flag)
    )).all()
    conteos = dict(filas)
    return {
        "since": desde,
        "requests": {bandera: conteos.get(bandera, 0) for bandera in sorted(PREMIUM_FEATURES | ENTERPRISE_FEATURES)},
    }


@router.get("/clients/{cliente_id}/changes")
async def consultar_cambios(cliente_id: UUID, db: AsyncSession = Depends(get_db)):
    cliente = await db.get(Client, cliente_id)
    if cliente is None:
        raise HTTPException(404, "Cliente no encontrado")
    cambios = (await db.scalars(
        select(AuditLog).where(
            AuditLog.client_id == cliente_id, AuditLog.resource_type == "commercial_profile",
            AuditLog.occurred_at >= retention_cutoff(cliente.commercial_plan),
        ).order_by(AuditLog.occurred_at.desc(), AuditLog.id.desc()).limit(50)
    )).all()
    return [{
        "id": cambio.id, "date": cambio.occurred_at, "actor": cambio.actor_email,
        "detail": cambio.commercial_detail,
    } for cambio in cambios]
