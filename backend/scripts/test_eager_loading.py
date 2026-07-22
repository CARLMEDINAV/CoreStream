"""
Test script para verificar que el eager loading de roles funciona correctamente.
Este script simula lo que sucede cuando se ejecuta GET /api/users/.
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.database import AsyncSessionLocal
from app.models import User, Role
from app.schemas import UserResponse


async def test_eager_loading():
    """Test que verifica el eager loading de roles"""
    async with AsyncSessionLocal() as db:
        try:
            # Primero, verificar que hay roles en la base de datos
            role_result = await db.execute(select(Role))
            roles = role_result.scalars().all()
            print(f"✓ Roles encontrados en BD: {len(roles)}")
            for role in roles:
                print(f"  - {role.name}")

            # Obtener usuarios con eager loading
            result = await db.execute(
                select(User)
                .options(selectinload(User.role))
                .order_by(User.created_at.desc())
                .limit(5)
            )
            users = result.unique().scalars().all()
            print(f"\n✓ Usuarios obtenidos: {len(users)}")

            # Validar cada usuario
            for i, user in enumerate(users):
                try:
                    print(f"\nValidando usuario {i+1}:")
                    print(f"  ID: {user.id}")
                    print(f"  Email: {user.email}")
                    print(f"  Role (raw): {user.role} (type: {type(user.role).__name__})")

                    # Intentar crear UserResponse
                    response = UserResponse.model_validate(user)
                    print(f"  ✓ UserResponse creado exitosamente")
                    print(f"  Role (response): {response.role}")

                except Exception as e:
                    print(f"  ✗ ERROR al validar usuario: {e}")
                    import traceback
                    traceback.print_exc()
                    return False

            print("\n✓ Test completado exitosamente!")
            return True

        except Exception as e:
            print(f"✗ ERROR: {e}")
            import traceback
            traceback.print_exc()
            return False


if __name__ == "__main__":
    result = asyncio.run(test_eager_loading())
    sys.exit(0 if result else 1)
