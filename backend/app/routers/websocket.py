"""
Router de WebSocket para Notificaciones en Tiempo Real.

Endpoints disponibles:
- /api/ws/notifications?ticket=TICKET (Requerimiento WEB-20: Seguro, sin user_id en la URL)
- /api/ws/{user_id}?ticket=TICKET (Deprecado: Mantenido por retrocompatibilidad)

DISEÑO DE LA ESPERA:
Por cada conexión se lanzan dos tareas de larga vida que compiten en
asyncio.wait(..., return_when=FIRST_COMPLETED):
  - _forward_redis_messages: espera con pubsub.get_message(timeout=N)
  - _listen_for_client: espera en bucle mensajes del cliente (pong/desconexión)
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from datetime import datetime, timezone
from typing import Optional

import redis.asyncio as redis
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select

from app.config import get_settings
from app.database import get_session_maker
from app.models import User
from app.redis_client import (
    TICKETS_UPDATES_CHANNEL,
    consume_ws_ticket,
    user_notifications_channel,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["WebSocket"])

settings = get_settings()
REDIS_URL = settings.REDIS_URL

HEARTBEAT_INTERVAL_SECONDS = 30.0


class ConnectionManager:
    """Registro de conexiones activas, usado para diagnóstico y limpieza local."""

    def __init__(self) -> None:
        self.active_connections: dict[str, list[WebSocket]] = {}
        self.redis_client: Optional[redis.Redis] = None

    async def connect(self, websocket: WebSocket, user_id: str) -> None:
        await websocket.accept()
        self.active_connections.setdefault(user_id, []).append(websocket)
        logger.info(
            "Usuario %s conectado. Total conexiones: %d",
            user_id,
            len(self.active_connections[user_id]),
        )

    def disconnect(self, websocket: WebSocket, user_id: str) -> None:
        conexiones = self.active_connections.get(user_id)
        if not conexiones:
            return
        with contextlib.suppress(ValueError):
            conexiones.remove(websocket)
        if not conexiones:
            del self.active_connections[user_id]
        logger.info("Usuario %s desconectado", user_id)

    async def init_redis(self) -> None:
        if not self.redis_client:
            self.redis_client = redis.from_url(REDIS_URL)

    async def publish_ticket_event(
        self, event_type: str, ticket_data: dict, target_user_id: str | None = None
    ) -> None:
        try:
            await self.init_redis()

            event_data = {
                "type": event_type,
                "data": ticket_data,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            if target_user_id:
                channel = user_notifications_channel(target_user_id)
                await self.redis_client.publish(channel, json.dumps(event_data))
                logger.info("Evento %s publicado para usuario %s", event_type, target_user_id)

            await self.redis_client.publish(TICKETS_UPDATES_CHANNEL, json.dumps(event_data))

        except Exception:
            logger.exception("Error publicando evento %s", event_type)


manager = ConnectionManager()


async def _forward_redis_messages(pubsub, websocket: WebSocket, user_id: str) -> None:
    loop = asyncio.get_event_loop()
    deadline = loop.time() + HEARTBEAT_INTERVAL_SECONDS

    while True:
        remaining = deadline - loop.time()
        if remaining <= 0:
            await websocket.send_json({
                "type": "ping",
                "message": "Heartbeat",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            deadline = loop.time() + HEARTBEAT_INTERVAL_SECONDS
            continue

        message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=remaining)

        if message is None:
            continue

        deadline = loop.time() + HEARTBEAT_INTERVAL_SECONDS

        try:
            notification_data = json.loads(message.get("data", "{}"))
        except json.JSONDecodeError:
            logger.error("Mensaje de Redis con JSON inválido en canal %s", message.get("channel"))
            continue

        canal = message.get("channel", "")
        if isinstance(canal, bytes):
            canal = canal.decode()

        await websocket.send_json({
            "type": "update" if canal == TICKETS_UPDATES_CHANNEL else "notification",
            "data": notification_data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        logger.info("Mensaje WS reenviado a usuario %s (canal %s)", user_id, canal)


async def _listen_for_client(websocket: WebSocket, user_id: str) -> None:
    while True:
        raw = await websocket.receive_text()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if data.get("type") == "pong":
            logger.debug("Pong recibido de usuario %s", user_id)


async def _handle_connection(websocket: WebSocket, user_id: str) -> None:
    """Gestiona el ciclo de vida de la suscripción y las tareas del WebSocket."""
    await manager.init_redis()
    await manager.connect(websocket, user_id)

    channel = user_notifications_channel(user_id)
    pubsub = manager.redis_client.pubsub()
    await pubsub.subscribe(channel, TICKETS_UPDATES_CHANNEL)

    await websocket.send_json({
        "type": "connected",
        "message": f"Conectado exitosamente. Usuario ID: {user_id}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    logger.info("Usuario %s suscrito al canal %s", user_id, channel)

    redis_task = asyncio.create_task(_forward_redis_messages(pubsub, websocket, user_id))
    client_task = asyncio.create_task(_listen_for_client(websocket, user_id))

    try:
        await asyncio.wait({redis_task, client_task}, return_when=asyncio.FIRST_COMPLETED)
    except WebSocketDisconnect:
        pass
    finally:
        for task in (redis_task, client_task):
            if not task.done():
                task.cancel()

        resultados = await asyncio.gather(redis_task, client_task, return_exceptions=True)
        for resultado in resultados:
            if isinstance(resultado, Exception) and not isinstance(
                resultado, (WebSocketDisconnect, asyncio.CancelledError)
            ):
                logger.error("Error en tarea de WebSocket para usuario %s: %s", user_id, resultado)

        manager.disconnect(websocket, user_id)

        with contextlib.suppress(Exception):
            await pubsub.unsubscribe(channel, TICKETS_UPDATES_CHANNEL)
            await pubsub.close()

        logger.info("Usuario %s desconectado de notificaciones", user_id)


@router.websocket("/ws/notifications")
async def websocket_notifications_secure(
    websocket: WebSocket, ticket: Optional[str] = Query(None)
) -> None:
    """
    Endpoint WebSocket seguro (Requerimiento WEB-20).
    Resuelve la identidad del usuario desde el ticket en Redis sin exponer user_id en la URL.
    """
    if not ticket:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Ticket no proporcionado")
        logger.warning("Intento de conexión sin ticket en endpoint seguro")
        return

    ticket_user_id = await consume_ws_ticket(ticket)
    if ticket_user_id is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Ticket inválido o expirado")
        logger.warning("Ticket inválido o ya usado en endpoint seguro")
        return

    async with get_session_maker()() as db:
        result = await db.execute(select(User).where(User.id == ticket_user_id))
        if result.scalar_one_or_none() is None:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Usuario no encontrado")
            logger.warning("Intento de conexión con usuario inexistente: %s", ticket_user_id)
            return

    await _handle_connection(websocket, ticket_user_id)


@router.websocket("/ws/{user_id}")
async def websocket_notifications(
    websocket: WebSocket, user_id: str, ticket: Optional[str] = Query(None)
) -> None:
    """
    [DEPRECADO] Usar /api/ws/notifications. Mantenido por retrocompatibilidad.
    """
    if not ticket:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Ticket no proporcionado")
        logger.warning("Intento de conexión sin ticket para usuario %s", user_id)
        return

    ticket_user_id = await consume_ws_ticket(ticket)
    if ticket_user_id is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Ticket inválido o expirado")
        logger.warning("Ticket inválido o ya usado en conexión WebSocket para usuario %s", user_id)
        return

    if ticket_user_id != user_id:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Ticket user mismatch")
        logger.warning("Ticket user mismatch: ticket=%s, solicitado=%s", ticket_user_id, user_id)
        return

    async with get_session_maker()() as db:
        result = await db.execute(select(User).where(User.id == user_id))
        if result.scalar_one_or_none() is None:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Usuario no encontrado")
            logger.warning("Intento de conexión con usuario inexistente: %s", user_id)
            return

    await _handle_connection(websocket, user_id)