"""
Helpers compartidos por los tests unitarios para el multi-tenancy (TRV-01).

Todo modelo con TenantMixin exige client_id. En vez de crear un Client
distinto en cada helper o fixture, cada sesión de BD de un test usa UN solo
Client de prueba: se crea la primera vez que se pide y se guarda en
session.info, que vive lo mismo que la sesión.
"""
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Client


async def get_test_client(db: AsyncSession) -> Client:
    """Devuelve el Client de prueba de esta sesión, creándolo si aún no existe."""
    client = db.info.get("_test_client")
    if client is None:
        client = Client(name="Cliente Test", slug="cliente-test", is_active=True)
        db.add(client)
        await db.flush()
        db.info["_test_client"] = client
    return client


async def get_test_client_id(db: AsyncSession) -> UUID:
    """Atajo para pasar directo como client_id=... al crear un modelo."""
    return (await get_test_client(db)).id
