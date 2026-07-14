import asyncio
import uuid
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from app.models import Application, Epic
from app.database import DATABASE_URL

async def create_sample_epics():
    """Crear épicas de ejemplo para probar drag & drop"""
    engine = create_async_engine(DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        # Obtener aplicaciones existentes
        result = await session.execute(select(Application))
        applications = result.scalars().all()
        
        if not applications:
            print("No hay aplicaciones. Primero ejecuta setup_apps.py")
            return
        
        # Verificar si ya existen épicas
        result = await session.execute(select(Epic))
        existing_epics = result.scalars().all()
        
        if existing_epics:
            print(f"Ya existen {len(existing_epics)} épicas")
            return
        
        # Crear épicas de ejemplo para cada aplicación
        epic_data = {
            'Base de Datos': [
                'Optimización de consultas SQL',
                'Migración a nueva versión',
                'Configuración de backups automáticos'
            ],
            'Frontend Web': [
                'Implementar sistema de autenticación',
                'Diseñar dashboard principal',
                'Optimizar rendimiento de componentes'
            ],
            'Integraciones API': [
                'Conectar con servicio de pagos',
                'Implementar webhook de notificaciones',
                'Documentar endpoints públicos'
            ],
            'Panel de Administración': [
                'Gestión de usuarios',
                'Reportes y estadísticas',
                'Configuración del sistema'
            ],
            'Sistema de Autenticación': [
                'Login con redes sociales',
                'Recuperación de contraseña',
                'Seguridad y encriptación'
            ]
        }
        
        epic_count = 0
        for app in applications:
            app_epics = epic_data.get(app.name, [])
            for i, title in enumerate(app_epics):
                epic = Epic(
                    id=uuid.uuid4(),
                    title=title,
                    description=f"Épica para {app.name}: {title}",
                    application_id=app.id,
                    order_index=i,
                    is_collapsed=False
                )
                session.add(epic)
                epic_count += 1
        
        await session.commit()
        print(f'Created {epic_count} epics across {len(applications)} applications')

if __name__ == "__main__":
    asyncio.run(create_sample_epics())
