"""
Script para inicializar aplicaciones y épicas de forma idempotente.
Se ejecuta automáticamente al arrancar el backend si no existen los datos.
"""

import uuid
from app.database import async_session_maker
from app.models.application import Application
from app.models.epic import Epic
from sqlalchemy import select


APPLICATIONS_DATA = [
    {
        'name': 'Base de Datos',
        'description': 'Optimización y mantenimiento',
        'color': '#F59E0B',
        'icon': 'database'
    },
    {
        'name': 'Frontend Web',
        'description': 'Interfaz de usuario principal',
        'color': '#8B5CF6',
        'icon': 'monitor'
    },
    {
        'name': 'Integraciones API', 
        'description': 'Conexiones con servicios externos',
        'color': '#EF4444',
        'icon': 'link'
    },
    {
        'name': 'Panel de Administración',
        'description': 'Dashboard para administradores', 
        'color': '#10B981',
        'icon': 'dashboard'
    },
    {
        'name': 'Sistema de Autenticación',
        'description': 'Gestión de usuarios y autenticación',
        'color': '#3B82F6', 
        'icon': 'shield'
    }
]

EPICS_BY_APPLICATION = {
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


async def setup_applications_and_epics():
    """
    Crea aplicaciones y épicas de forma idempotente.
    Si ya existen, no crea duplicados.
    Se ejecuta automáticamente en el startup del backend.
    """
    async with async_session_maker() as session:
        try:
            # Crear aplicaciones si no existen
            print("Verificando aplicaciones...")
            app_ids = {}
            
            for app_data in APPLICATIONS_DATA:
                # Verificar si la aplicación ya existe
                stmt = select(Application).where(
                    Application.name == app_data['name']
                )
                result = await session.execute(stmt)
                existing_app = result.scalar_one_or_none()
                
                if existing_app:
                    print(f"  ✅ Aplicación ya existe: {app_data['name']}")
                    app_ids[app_data['name']] = existing_app.id
                else:
                    # Crear nueva aplicación
                    new_app = Application(
                        id=uuid.uuid4(),
                        name=app_data['name'],
                        description=app_data['description'],
                        color=app_data['color'],
                        icon=app_data['icon'],
                        is_active=True
                    )
                    session.add(new_app)
                    app_ids[app_data['name']] = new_app.id
                    print(f"  ✅ Aplicación creada: {app_data['name']}")
            
            # Hacer commit de aplicaciones
            await session.flush()
            
            # Crear épicas si no existen
            print("\nVerificando épicas...")
            epic_count = 0
            
            for app_name, epic_titles in EPICS_BY_APPLICATION.items():
                app_id = app_ids[app_name]
                
                for order_index, title in enumerate(epic_titles):
                    # Verificar si la épica ya existe
                    stmt = select(Epic).where(
                        (Epic.title == title) & 
                        (Epic.application_id == app_id)
                    )
                    result = await session.execute(stmt)
                    existing_epic = result.scalar_one_or_none()
                    
                    if existing_epic:
                        print(f"  ✅ Épica ya existe: {title}")
                    else:
                        # Crear nueva épica
                        new_epic = Epic(
                            id=uuid.uuid4(),
                            title=title,
                            description=f"Épica para {app_name}: {title}",
                            application_id=app_id,
                            order_index=order_index,
                            is_collapsed=False
                        )
                        session.add(new_epic)
                        epic_count += 1
                        print(f"  ✅ Épica creada: {title}")
            
            # Hacer commit de épicas
            await session.commit()
            
            if epic_count > 0:
                print(f"\n✅ Setup completado: {epic_count} épica(s) nueva(s) creada(s)")
            else:
                print("\n✅ Todas las aplicaciones y épicas ya existen")
                
        except Exception as e:
            await session.rollback()
            print(f"❌ Error durante setup de aplicaciones: {e}")
            raise
