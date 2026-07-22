"""
Router de WebSocket para Notificaciones en Tiempo Real.

Proporciona conexión WebSocket para:
- Recibir notificaciones en tiempo real
- Mantener actualización automática de cambios
- Escuchar eventos de Redis pub/sub
- Enviar pings periódicos para mantener la conexión viva
- Manejar reconexiones y desconexiones graciosas
- Validar JWT tokens para conexiones seguras

El cliente se conecta a /ws/{user_id}?token=JWT_TOKEN y recibe eventos
cada vez que hay actividad relevante para ese usuario.
"""

from fastapi import APIRouter, WebSocketDisconnect, HTTPException, status, WebSocket, Query
from sqlalchemy import select
import asyncio
import json
import redis.asyncio as redis
from datetime import datetime
import logging
from typing import Optional
from jose import JWTError, jwt

from app.database import async_session_maker
from app.models import User
from app.config import get_settings

# Configurar logging para WebSocket
logger = logging.getLogger(__name__)

# Router para WebSocket
router = APIRouter(tags=["WebSocket"])

# Obtener URL de Redis de configuración
settings = get_settings()
REDIS_URL = settings.REDIS_URL


async def verify_ws_token(token: Optional[str] = Query(None)) -> str:
    """
    Verifica el JWT token proporcionado en el query parameter del WebSocket.
    
    El token debe ser pasado como: ws://host/ws/{user_id}?token=JWT_TOKEN
    
    Args:
        token: Token JWT del query parameter
        
    Returns:
        user_id: ID del usuario del token verificado
        
    Raises:
        HTTPException: Si el token no es válido o no existe
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token no proporcionado en query parameters"
        )
    
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise JWTError("Token inválido: sin user_id")
        return user_id
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token inválido: {str(e)}"
        )


class ConnectionManager:
    """
    Gestor de conexiones WebSocket para notificaciones en tiempo real.
    
    Maneja múltiples conexiones concurrentes y distribuye mensajes
    usando Redis pub/sub como backend de mensajería.
    """

    def __init__(self):
        # Almacenar conexiones activas: {user_id: [websocket, ...]}
        # user_id es un UUID como string
        self.active_connections: dict = {}
        self.redis_client = None
        self._heartbeat_tasks: dict = {}  # {user_id: [task, ...]}

    async def connect(self, websocket: WebSocket, user_id: str):
        """
        Acepta una conexión WebSocket y la registra.

        Args:
            websocket (WebSocket): Conexión WebSocket
            user_id (str): ID del usuario que se conecta (UUID)
        """
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
            self._heartbeat_tasks[user_id] = []
        
        self.active_connections[user_id].append(websocket)
        logger.info(f"Usuario {user_id} conectado. Total conexiones: {len(self.active_connections[user_id])}")

    def disconnect(self, websocket: WebSocket, user_id: str):
        """
        Registra una desconexión WebSocket.

        Args:
            websocket (WebSocket): Conexión WebSocket
            user_id (str): ID del usuario (UUID)
        """
        if user_id in self.active_connections:
            try:
                self.active_connections[user_id].remove(websocket)
                if not self.active_connections[user_id]:
                    del self.active_connections[user_id]
                    # Cancelar heartbeat tasks
                    if user_id in self._heartbeat_tasks:
                        for task in self._heartbeat_tasks[user_id]:
                            task.cancel()
                        del self._heartbeat_tasks[user_id]
            except ValueError:
                pass  # Connection already removed
        logger.info(f"Usuario {user_id} desconectado")

    async def broadcast_to_user(self, user_id: str, data: dict):
        """
        Envía un mensaje a todas las conexiones de un usuario.

        Args:
            user_id (str): ID del usuario (UUID)
            data (dict): Datos del mensaje
        """
        if user_id in self.active_connections:
            # Crear copia de la lista para evitar modificación durante iteración
            connections = self.active_connections[user_id].copy()
            for connection in connections:
                try:
                    await connection.send_json(data)
                except Exception as e:
                    logger.error(f"Error enviando mensaje a usuario {user_id}: {str(e)}")
                    # Intentar desconectar si hay error
                    try:
                        self.disconnect(connection, user_id)
                    except Exception:
                        pass

    async def init_redis(self):
        """Inicializa conexión a Redis si no existe."""
        if not self.redis_client:
            self.redis_client = await redis.from_url(REDIS_URL)

    async def publish_ticket_event(self, event_type: str, ticket_data: dict, target_user_id: str = None):
        """
        Publica eventos de tickets para notificaciones en tiempo real.
        
        Args:
            event_type: Tipo de evento (TICKET_ASSIGNED, TICKET_STATUS_CHANGED, TIMER_SYNC)
            ticket_data: Datos del ticket
            target_user_id: ID del usuario destino (si aplica)
        """
        try:
            await self.init_redis()
            
            event_data = {
                "type": event_type,
                "data": ticket_data,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Publicar al canal específico del usuario si se especifica
            if target_user_id:
                channel = f"user:{target_user_id}:notifications"
                await self.redis_client.publish(channel, json.dumps(event_data))
                logger.info(f"Evento {event_type} publicado para usuario {target_user_id}")
            
            # También publicar al canal general de tickets para actualizaciones globales
            general_channel = "tickets:updates"
            await self.redis_client.publish(general_channel, json.dumps(event_data))
            
        except Exception as e:
            logger.error(f"Error publicando evento {event_type}: {str(e)}")

    async def start_heartbeat(self, websocket: WebSocket, user_id: str):
        """
        Inicia el heartbeat para mantener la conexión activa.
        
        Args:
            websocket: Conexión WebSocket
            user_id: ID del usuario
        """
        async def heartbeat_task():
            try:
                while True:
                    await asyncio.sleep(30)  # Heartbeat cada 30 segundos
                    try:
                        await websocket.send_json({
                            "type": "ping",
                            "message": "Heartbeat",
                            "timestamp": datetime.utcnow().isoformat()
                        })
                    except Exception:
                        break  # Conexión cerrada
            except asyncio.CancelledError:
                pass
        
        task = asyncio.create_task(heartbeat_task())
        if user_id not in self._heartbeat_tasks:
            self._heartbeat_tasks[user_id] = []
        self._heartbeat_tasks[user_id].append(task)


# Instancia global del gestor de conexiones
manager = ConnectionManager()


@router.websocket("/ws/{user_id}")
async def websocket_notifications(websocket: WebSocket, user_id: str, token: Optional[str] = Query(None)):
    """
    Endpoint WebSocket para recibir notificaciones en tiempo real.
    
    Requiere autenticación JWT mediante token en query parameters.
    El cliente se conecta con: ws://host/ws/{user_id}?token=JWT_TOKEN

    Recibe mensajes JSON con formato:
    {
        "type": "notification|ping|error",
        "data": {...}
    }

    Args:
        websocket (WebSocket): Conexión WebSocket
        user_id (str): ID del usuario (UUID como string)
        token (str): JWT token para autenticación

    El servidor:
    - Valida JWT token
    - Verifica que el usuario existe
    - Se suscribe al canal Redis del usuario
    - Escucha eventos del canal
    - Envía pings cada 30 segundos para mantener la conexión
    - Maneja reconexiones y desconexiones graciosas
    """
    pubsub = None
    
    try:
        # Verificar token JWT
        if not token:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Token no proporcionado")
            logger.warning(f"Intento de conexión sin token para usuario {user_id}")
            return
        
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            token_user_id: str = payload.get("sub")
            if token_user_id != user_id:
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Token user mismatch")
                logger.warning(f"Token user mismatch: token={token_user_id}, requested={user_id}")
                return
        except JWTError as e:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Token inválido")
            logger.warning(f"Token inválido para usuario {user_id}: {str(e)}")
            return

        # Inicializar Redis si es necesario
        await manager.init_redis()

        # Verificar que el usuario existe en BD
        async with async_session_maker() as db:
            result = await db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()

            if not user:
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Usuario no encontrado")
                logger.warning(f"Intento de conexión con usuario inexistente: {user_id}")
                return

        # Aceptar conexión y registrarla
        await manager.connect(websocket, user_id)

        # Crear nombre del canal Redis
        channel = f"user:{user_id}:notifications"

        # Suscribirse al canal personal y al canal global de cambios de estado
        pubsub = manager.redis_client.pubsub()
        await pubsub.subscribe(channel)
        await pubsub.subscribe("tickets:updates")

        # Enviar mensaje de bienvenida
        await websocket.send_json({
            "type": "connected",
            "message": f"Conectado exitosamente. Usuario ID: {user_id}",
            "timestamp": datetime.utcnow().isoformat()
        })

        logger.info(f"Usuario {user_id} suscrito al canal {channel}")

        # Iniciar heartbeat mejorado
        await manager.start_heartbeat(websocket, user_id)

        try:
            # Escuchar mensajes del cliente (para heartbeat de cliente)
            while True:
                # Escuchar tanto mensajes de cliente como de Redis concurrentemente
                client_msg = asyncio.create_task(websocket.receive_text())
                redis_msg = asyncio.create_task(pubsub.get_message())

                done, pending = await asyncio.wait(
                    [client_msg, redis_msg],
                    timeout=1.0,
                    return_when=asyncio.FIRST_COMPLETED
                )

                # Procesar mensaje del cliente (heartbeat)
                if client_msg in done:
                    try:
                        message = client_msg.result()
                        # El cliente puede enviar pong para confirmar conexión viva
                        if message:
                            data = json.loads(message)
                            if data.get("type") == "pong":
                                logger.debug(f"Pong recibido de usuario {user_id}")
                    except json.JSONDecodeError:
                        pass
                    except Exception as e:
                        logger.error(f"Error procesando mensaje del cliente: {str(e)}")
                else:
                    client_msg.cancel()

                # Procesar mensaje de Redis (notificación o actualización de estado)
                if redis_msg in done:
                    try:
                        message = redis_msg.result()
                        if message and message.get("type") == "message":
                            notification_data = json.loads(message.get("data", "{}"))
                            # Determinar tipo WS según el canal de origen
                            msg_channel = message.get("channel", "")
                            if isinstance(msg_channel, bytes):
                                msg_channel = msg_channel.decode()
                            if msg_channel == "tickets:updates":
                                ws_type = "update"
                            else:
                                ws_type = "notification"
                            await websocket.send_json({
                                "type": ws_type,
                                "data": notification_data,
                                "timestamp": datetime.utcnow().isoformat()
                            })
                            logger.info(f"Mensaje WS ({ws_type}) enviado a usuario {user_id}")
                    except json.JSONDecodeError:
                        logger.error("Error decodificando mensaje de Redis")
                    except Exception as e:
                        logger.error(f"Error procesando mensaje de Redis: {str(e)}")
                else:
                    redis_msg.cancel()

        except WebSocketDisconnect:
            logger.info(f"WebSocket desconectado para usuario {user_id}")
        except Exception as e:
            logger.error(f"Error en WebSocket: {str(e)}")
        
    except Exception as e:
        logger.error(f"Error en conexión WebSocket: {str(e)}")
        try:
            await websocket.close(code=status.WS_1011_SERVER_ERROR)
        except Exception:
            pass
    finally:
        # Limpiar recursos
        if user_id in manager.active_connections:
            manager.disconnect(websocket, user_id)

        if pubsub:
            try:
                await pubsub.close()
            except Exception:
                pass


async def send_periodic_pings(websocket: WebSocket, user_id: str, interval: int = 30):
    """
    Envía pings periódicos para mantener la conexión WebSocket activa.

    Args:
        websocket (WebSocket): Conexión WebSocket
        user_id (str): ID del usuario (UUID)
        interval (int): Intervalo en segundos entre pings (default: 30)
    """
    try:
        while True:
            await asyncio.sleep(interval)
            try:
                await websocket.send_json({
                    "type": "ping",
                    "message": "Heartbeat",
                    "timestamp": datetime.utcnow().isoformat()
                })
                logger.debug(f"Ping enviado a usuario {user_id}")
            except Exception as e:
                logger.error(f"Error enviando ping: {str(e)}")
                break
    except asyncio.CancelledError:
        logger.info(f"Tarea de pings cancelada para usuario {user_id}")
    except Exception as e:
        logger.error(f"Error en envío de pings: {str(e)}")


# Función auxiliar para publicar notificaciones en Redis
async def publish_notification(user_id: str, notification_data: dict):
    """
    Publica una notificación a un usuario específico a través de Redis.

    Esta función es utilizada por los servicios de notificación para
    enviar eventos en tiempo real a usuarios conectados.

    Args:
        user_id (str): ID del usuario destino (UUID)
        notification_data (dict): Datos de la notificación
    """
    try:
        redis_client = await redis.from_url(settings.REDIS_URL)
        channel = f"user:{user_id}:notifications"
        await redis_client.publish(channel, json.dumps(notification_data))
        await redis_client.close()
    except Exception as e:
        logger.error(f"Error publicando notificación a usuario {user_id}: {str(e)}")
