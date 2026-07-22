#!/usr/bin/env python3
"""
Script para configurar la base de datos desde Docker
"""

import asyncio
import uuid
import sys
import os

# Agregar el path del backend
sys.path.append('/app')

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from app.models import Application, Epic
from app.database import DATABASE_URL

async def setup_database():
    """Configurar aplicaciones y épicas de ejemplo"""
    engine = create_async_engine(DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        print("=== CONFIGURACIÓN DE BASE DE DATOS CORESTREAM ===\n")
        
        # 1. Verificar/Crear aplicaciones
        result = await session.execute(select(Application))
        existing_apps = result.scalars().all()
        
        if existing_apps:
            print(f"✓ Ya existen {len(existing_apps)} aplicaciones:")
            for app in existing_apps:
                print(f"  • {app.name}: {app.id}")
        else:
            print("📝 Creando aplicaciones...")
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
            print(f"✓ Creadas {len(apps_data)} aplicaciones")
        
        # 2. Obtener aplicaciones para crear épicas
        result = await session.execute(select(Application))
        applications = result.scalars().all()
        
        # 3. Verificar/Crear épicas
        result = await session.execute(select(Epic))
        existing_epics = result.scalars().all()
        
        if existing_epics:
            print(f"\n✓ Ya existen {len(existing_epics)} épicas")
        else:
            print("\n📝 Creando épicas de ejemplo...")
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
            print(f"✓ Creadas {epic_count} épicas")
        
        # 4. Mostrar resumen final
        print("\n=== RESUMEN FINAL ===")
        
        result = await session.execute(select(Application))
        apps = result.scalars().all()
        
        result = await session.execute(select(Epic))
        epics = result.scalars().all()
        
        print(f"📊 Total aplicaciones: {len(apps)}")
        print(f"📊 Total épicas: {len(epics)}")
        
        print("\n🔗 URLs para probar:")
        for app in apps:
            print(f"  • http://localhost:5173/admin/builder?appId={app.id}")
        
        print("\n✅ Base de datos configurada exitosamente!")

if __name__ == "__main__":
    asyncio.run(setup_database())
