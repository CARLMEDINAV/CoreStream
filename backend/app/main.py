# Archivo principal de la aplicación FastAPI
# Configura la aplicación, middleware, rutas, eventos de startup/shutdown y WebSockets

from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Importar routers (estos se crearían en carpetas routers/)
# Mantenemos las importaciones individuales para asegurar que cada módulo cargue bien
from app.routers import (
    auth,
    users,
    applications,
    epics,
    tickets,
    subtasks,
    analytics,
    documents,
    notifications,
    websocket,
    ticket_redirection,
    uploads,
    support_tickets,
    incidents,
    meetings,
)

from arq import create_pool
from arq.connections import RedisSettings

from app.config import get_settings
from app.database import engine
from app.models.base import Base
from app.redis_client import (
    init_redis,
    close_redis,
    subscribe_channel,
)
from app.services.notification_service import set_arq_pool
from app.scripts.seed_persistent_users import seed_persistent_users
from app.scripts.seed_demo_tickets import seed_demo_tickets
from app.scripts.setup_applications import setup_applications_and_epics

# Obtener configuración
settings = get_settings()


# Contexto de ciclo de vida de la aplicación
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gestor de contexto que controla el ciclo de vida de la aplicación FastAPI.
    
    Maneja eventos de startup (inicialización) y shutdown (cierre) de la aplicación.
    En startup se inicializan conexiones a recursos externos como BD y Redis.
    En shutdown se cierran correctamente todas las conexiones.
    
    Args:
        app: Instancia de FastAPI
        
    Yields:
        Control a FastAPI durante la ejecución
    """
    # Evento de STARTUP - Ejecuta cuando la aplicación inicia
    print("Iniciando aplicación CoreStream...")
    
    try:
        # Inicializar conexión a Redis para sistema de notificaciones
        await init_redis()
        print("Redis inicializado correctamente")
    except Exception as e:
        print(f"⚠️  Warning: Redis no disponible al arrancar: {e}")

    try:
        # Inicializar pool ARQ para encolar notificaciones
        arq_pool = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
        set_arq_pool(arq_pool)
        print("ARQ pool inicializado correctamente")
    except Exception as e:
        print(f"⚠️  Warning: ARQ pool no disponible: {e}")

    try:
        # Crear tablas de base de datos si no existen
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            print("Tablas de base de datos inicializadas")
    except Exception as e:
        print(f"⚠️  Warning: No se pudieron inicializar tablas: {e}")

    import os
    # RUN_SEED debe setearse explícitamente en Railway/docker para correr demo seed
    # Por defecto es "false" para evitar sobreescribir datos en producción
    _run_demo_seed = os.getenv("RUN_SEED", "false").lower() == "true"

    # seed_persistent_users es idempotente (chequea por email) — siempre seguro
    try:
        seed_persistent_users()
        print("Usuarios base inicializados")
    except Exception as e:
        print(f"⚠️  Warning: No se pudieron inicializar usuarios base: {e}")

    if _run_demo_seed:
        try:
            await setup_applications_and_epics()
            print("Aplicaciones y épicas inicializadas")
        except Exception as e:
            print(f"⚠️  Warning: No se pudieron inicializar aplicaciones y épicas: {e}")

        try:
            seed_demo_tickets()
            print("Tickets de demostración inicializados")
        except Exception as e:
            print(f"⚠️  Warning: No se pudieron crear tickets de demostración: {e}")
    else:
        print("RUN_SEED no activo: seed de datos de demo omitido")

    print("\nAplicación CoreStream iniciada")
    
    # Ceder control a FastAPI
    yield
    
    # Evento de SHUTDOWN - Ejecuta cuando la aplicación se detiene
    print("Cerrando aplicación CoreStream...")
    
    try:
        # Cerrar pool ARQ
        from app.services.notification_service import get_arq_pool
        pool = get_arq_pool()
        if pool:
            await pool.close()
            print("ARQ pool cerrado correctamente")

        # Cerrar conexión a Redis
        await close_redis()
        print("Redis cerrado correctamente")
        
        # Cerrar conexión a la base de datos
        await engine.dispose()
        print("Base de datos desconectada")
        
        print("Aplicación CoreStream cerrada correctamente")
        
    except Exception as e:
        print(f"Error durante shutdown: {e}")


# Crear instancia de la aplicación FastAPI
app = FastAPI(
    title=settings.APP_NAME,
    description="API RESTful para gestión de aplicaciones, épicas, tickets y analítica de equipo",
    version="1.0.0",
    docs_url="/api/docs",  # Documentación Swagger UI
    redoc_url="/api/redoc",  # Documentación ReDoc
    openapi_url="/api/openapi.json",  # Esquema OpenAPI JSON
    lifespan=lifespan,
)


# Configurar CORS (Cross-Origin Resource Sharing)
# Permite solicitudes desde el frontend en localhost:5173
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


# Incluir routers con prefijos de API
# Cada router maneja un dominio específico de la aplicación
# Estos routers se crearían en carpeta app/routers/

app.include_router(auth.router, prefix="/api/auth")
app.include_router(users.router, prefix="/api/users")
app.include_router(applications.router, prefix="/api/applications")
app.include_router(epics.router, prefix="/api/epics") # Resulta en /api/epics/...
app.include_router(ticket_redirection.router)  # Ticket redirection endpoints: /api/tickets/... — MUST come before tickets.router
app.include_router(tickets.router, prefix="/api/tickets")
app.include_router(subtasks.router, prefix="/api/tickets/{ticket_id}/subtasks")
app.include_router(analytics.router, prefix="/api/analytics")
app.include_router(documents.router, prefix="/api/documents")
app.include_router(notifications.router, prefix="/api/notifications")
app.include_router(websocket.router, prefix="/api")  # WebSocket endpoints: /api/ws/...
app.include_router(uploads.router)  # prefijo embebido en el router: /api/uploads
app.include_router(support_tickets.router, prefix="/api/support-tickets")
app.include_router(incidents.router, prefix="/api")
app.include_router(meetings.router, prefix="/api")


# Endpoint raíz de salud — Railway lo usa como healthcheck en /health
@app.get("/health", tags=["Health"], include_in_schema=False)
async def health_check_root():
    return {"status": "ok", "service": "CoreStream API"}


# Endpoint de salud para verificar que la API está funcionando
@app.get(
    "/api/health",
    tags=["Health"],
    summary="Verificar salud de la API",
    description="Endpoint para monitoreo que verifica si la API está funcionando correctamente"
)
async def health_check():
    """
    Verifica el estado de la API.
    
    Retorna un estado OK si la aplicación está funcionando correctamente.
    Se utiliza típicamente para health checks en orquestadores como Kubernetes.
    
    Returns:
        dict: Mensaje de estado con timestamp
    """
    from datetime import datetime
    
    return {
        "status": "ok",
        "message": "API CoreStream funcionando correctamente",
        "timestamp": datetime.now().isoformat(),
    }


# Endpoint raíz con información de la API
@app.get(
    "/api",
    tags=["Root"],
    summary="Información de la API",
    description="Retorna información general sobre la API CoreStream"
)
async def root():
    """
    Endpoint raíz que proporciona información sobre la API.
    
    Returns:
        dict: Información de la aplicación, versión y enlaces a documentación
    """
    return {
        "app_name": settings.APP_NAME,
        "version": "1.0.0",
        "description": "API RESTful para gestión de aplicaciones, épicas y tickets",
        "documentation": "/api/docs",
        "redoc": "/api/redoc",
        "openapi_schema": "/api/openapi.json",
    }


# WebSocket para notificaciones en tiempo real
@app.websocket("/api/ws/notifications/{user_id}")
async def websocket_notifications(websocket: WebSocket, user_id: str):
    """
    Endpoint WebSocket para recibir notificaciones en tiempo real.
    
    Los clientes se conectan a este endpoint y reciben notificaciones cuando se
    producen eventos relevantes (tickets asignados, preguntas, etc.).
    
    El cliente debe proporcionar un token JWT válido en la querystring:
    ws://localhost:8000/api/ws/notifications/user-id?token=jwt-token
    
    Args:
        websocket: Conexión WebSocket del cliente
        user_id: ID del usuario para el cual recibir notificaciones
        
    Raises:
        WebSocketDisconnect: Cuando el cliente desconecta
        
    Ejemplo de cliente JavaScript:
        const token = localStorage.getItem('access_token');
        const ws = new WebSocket(
            `ws://localhost:8000/api/ws/notifications/${userId}?token=${token}`
        );
        ws.onmessage = (event) => {
            const notification = JSON.parse(event.data);
            console.log('Notificación:', notification);
        };
    """
    # Extraer token del query string
    token = websocket.query_params.get("token")
    
    if not token:
        # Cerrar la conexión si no se proporciona token
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    
    try:
        # Validar el token JWT
        from app.middleware import verify_token
        
        token_data = verify_token(token)
        
        # Verificar que el usuario está accediendo sus propias notificaciones
        if token_data.sub != user_id:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        
        # Aceptar la conexión WebSocket
        await websocket.accept()
        
        # Suscribirse al canal de notificaciones del usuario
        channel = f"notifications:{user_id}"
        pubsub = await subscribe_channel(channel)
        
        try:
            # Escuchar mensajes del canal Redis
            async for message in pubsub.listen():
                if message["type"] == "message":
                    # Enviar el mensaje al cliente WebSocket
                    await websocket.send_text(message["data"])
                    
        except WebSocketDisconnect:
            # Cliente desconectó
            await pubsub.unsubscribe(channel)
            print(f"Usuario {user_id} desconectado de notificaciones")
            
    except Exception as e:
        # Error en validación o suscripción
        print(f"Error en WebSocket: {e}")
        await websocket.close(code=status.WS_1011_SERVER_ERROR)


# Manejo de errores global para excepciones no capturadas
@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """
    Manejador global de excepciones para cualquier error no capturado.
    
    Registra la excepción y retorna una respuesta JSON con estado 500.
    """
    import logging
    logging.error(f"Error no manejado en {request.url}: {exc}")
    
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Error interno del servidor",
            "error": "Se ha producido un error inesperado."
        }
    )


# Punto de entrada para ejecutar la aplicación
if __name__ == "__main__":
    import uvicorn
    
    # Ejecutar servidor Uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,  # Recargar automáticamente en cambios (desarrollo)
        log_level="info",
    )