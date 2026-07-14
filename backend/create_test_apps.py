import asyncio
import uuid
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.models import Application
from app.database import DATABASE_URL

async def create_test_apps():
    engine = create_async_engine(DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        apps_data = [
            {
                'id': uuid.uuid4(),
                'name': 'Base de Datos',
                'description': 'Optimización y mantenimiento',
                'color': '#F59E0B',
                'icon': 'database',
                'is_active': True
            },
            {
                'id': uuid.uuid4(), 
                'name': 'Frontend Web',
                'description': 'Interfaz de usuario principal',
                'color': '#8B5CF6',
                'icon': 'monitor',
                'is_active': True
            },
            {
                'id': uuid.uuid4(),
                'name': 'Integraciones API', 
                'description': 'Conexiones con servicios externos',
                'color': '#EF4444',
                'icon': 'link',
                'is_active': True
            },
            {
                'id': uuid.uuid4(),
                'name': 'Panel de Administración',
                'description': 'Dashboard para administradores', 
                'color': '#10B981',
                'icon': 'dashboard',
                'is_active': True
            },
            {
                'id': uuid.uuid4(),
                'name': 'Sistema de Autenticación',
                'description': 'Gestión de usuarios y autenticación',
                'color': '#3B82F6', 
                'icon': 'shield',
                'is_active': True
            }
        ]
        
        for app_data in apps_data:
            app = Application(**app_data)
            session.add(app)
        
        await session.commit()
        print(f'Created {len(apps_data)} applications with UUIDs:')
        for app in apps_data:
            print(f'  {app["name"]}: {app["id"]}')

if __name__ == "__main__":
    asyncio.run(create_test_apps())
