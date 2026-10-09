"""valida el plan del cliente antes de ejecutar una funcion protegida."""

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models import Client, User
from app.plans import ALL_FEATURES, features_for, is_known_feature
from app.schemas.commercial import CommercialProfile


async def get_commercial_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CommercialProfile:
    # usa el cliente del usuario autenticado
    client = await db.scalar(select(Client).where(Client.id == current_user.client_id))
    if client is None:
        raise HTTPException(403, detail="Perfil comercial no disponible")

    enabled = features_for(client.commercial_plan, is_active=client.is_active)
    return CommercialProfile(
        client_id=client.id, plan=client.commercial_plan, is_active=client.is_active,
        feature_flags={key: key in enabled for key in sorted(ALL_FEATURES)},
    )


def require_feature(feature_flag: str):
    if not is_known_feature(feature_flag):
        raise ValueError(f"Feature flag desconocida: {feature_flag}")

    async def check(profile: CommercialProfile = Depends(get_commercial_profile)) -> None:
        if not profile.feature_flags.get(feature_flag, False):
            raise HTTPException(403, detail={
                "code": "FEATURE_NOT_INCLUDED", "feature_flag": feature_flag,
                "plan": profile.plan,
                "message": "Funcionalidad no incluida en el perfil comercial activo",
            })

    return check
