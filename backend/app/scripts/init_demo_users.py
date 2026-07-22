"""
Script para inicializar usuarios de demostración.

Este script crea usuarios de prueba para que los desarrolladores
puedan testear el sistema sin necesidad de registrar usuarios manualmente.

Usuarios creados:
- admin@example.dev / Admin123!@# (ADMIN)
- dev@example.dev / Dev123!@# (DEVELOPER)
- leader@example.dev / Leader123!@# (TEAM_LEADER)

Ejecutar con:
    python -m app.scripts.init_demo_users
"""

import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

from app.models import User, Role
from app.services.auth_service import auth_service
from app.config import get_settings
from app.schemas import UserCreate

settings = get_settings()
DATABASE_URL = settings.DATABASE_URL


async def init_demo_users():
    """Inicializa usuarios de demostración"""
    
    # Crear engine y session
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session() as session:
        try:
            # Verificar si ya existen usuarios
            result = await session.execute(select(User).limit(1))
            result.scalar_one_or_none()
            
            # if existing_user:
                # print("✓ La base de datos ya tiene usuarios. Saltando inicialización.")
                # return
            
            # Crear roles si no existen
            print("📝 Creando roles...")
            roles_to_create = [
                ('ADMIN', 'Administrator with full system access'),
                ('DEVELOPER', 'Regular developer with standard permissions'),
                ('TEAM_LEADER', 'Team leader with expanded permissions')
            ]
            
            role_map = {}
            for role_name, role_desc in roles_to_create:
                result = await session.execute(
                    select(Role).where(Role.name == role_name)
                )
                role = result.scalar_one_or_none()
                if not role:
                    role = Role(name=role_name, description=role_desc)
                    session.add(role)
                    await session.flush()
                role_map[role_name] = role
            
            await session.commit()
            print("✓ Roles creados")
            
            # Crear usuarios de demo
            demo_users = [
                {
                    "email": "admin@example.dev",
                    "password": "Admin123!@#",
                    "full_name": "Administrador",
                    "role_name": "ADMIN",
                    "specialty": "Project Management"
                },
                {
                    "email": "dev@example.dev",
                    "password": "Dev123!@#",
                    "full_name": "Desarrollador",
                    "role_name": "DEVELOPER",
                    "specialty": "Backend Development"
                },
                {
                    "email": "leader@example.dev",
                    "password": "Leader123!@#",
                    "full_name": "Líder de Grupo",
                    "role_name": "TEAM_LEADER",
                    "specialty": "Team Lead"
                }
            ]
            
            print("\n👤 Creando usuarios de demostración...\n")
            
            for user_data in demo_users:
                # Verificar que no exista
                result = await session.execute(
                    select(User).where(User.email == user_data["email"])
                )
                if result.scalar_one_or_none():
                    print(f"  ⊘ {user_data['email']} ya existe")
                    continue
                
                # Crear usuario
                user_create = UserCreate(
                    email=user_data["email"],
                    password=user_data["password"],
                    full_name=user_data["full_name"]
                )
                
                new_user = await auth_service.create_user(session, user_create)
                
                # Asignar rol y especialidad
                new_user.role = role_map[user_data["role_name"]]
                new_user.specialty = user_data["specialty"]
                
                session.add(new_user)
                await session.flush()
                
                print(f"  ✓ {user_data['email']:30} [{user_data['role_name']}]")
            
            await session.commit()
            
            print("\n" + "="*60)
            print("✓ USUARIOS DE DEMOSTRACIÓN CREADOS EXITOSAMENTE")
            print("="*60)
            print("\n📋 Credenciales disponibles:\n")
            
            for user_data in demo_users:
                print(f"  👤 {user_data['role_name']:15} | Email: {user_data['email']:30}")
                print(f"     {'':15} | Pass:  {user_data['password']:30}")
                print()
            
            print("="*60)
            print("\n💡 Prueba el sistema con estas credenciales en:")
            print("   http://localhost:5173/login\n")
            
        except Exception as e:
            print(f"\n❌ Error al inicializar usuarios: {e}")
            print(f"   Tipo de error: {type(e).__name__}")
            import traceback
            traceback.print_exc()
            await session.rollback()
            raise
        finally:
            await engine.dispose()


if __name__ == "__main__":
    asyncio.run(init_demo_users())
