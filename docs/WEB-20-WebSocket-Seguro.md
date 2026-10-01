# WEB-20 — WebSocket seguro con ticket de un solo uso

## Objetivo
Permitir comunicación en tiempo real de notificaciones sin exponer el JWT en el query string del WebSocket. El token viaja en logs de acceso de proxies y navegadores; su exposición es un riesgo de replay.

## Diseño
- Autenticación por ticket opaco de un solo uso y vida corta.
- El cliente nunca manda el JWT al WebSocket; manda `?ticket=...`.
- El backend valida el ticket en Redis, lo consume y mapea a `user_id`.

Flujo:
1. Login → el cliente guarda `accessToken` en memoria y recibe refresh token en cookie HttpOnly.
2. Al iniciar sesión el store `auth` llama `useWebSocket().connect(user.id)`.
3. `useWebSocket` hace `POST /api/auth/ws-ticket` con Bearer JWT.
4. El backend genera un ticket aleatorio, lo guarda en Redis `corestream:ws_ticket:{ticket}` → `user_id` con TTL 15s y lo devuelve.
5. El cliente abre `ws://host/api/ws/mobile/notifications?ticket=...`.
6. El router `/api/ws/mobile/notifications` consume el ticket con `consume_ws_ticket`. Si existe, se borra y se obtiene `user_id`. Si no existe/expiró/ya se usó → cierre 1008.
7. Con `user_id` válido se acepta la conexión, se suscribe a `user_notifications_channel(user_id)` y a `TICKETS_UPDATES_CHANNEL` vía Redis PubSub.
8. Cierre intencional → code 1000 sin reconexión. Cierre inesperado → backoff exponencial hasta 10 intentos.

## Endpoints
### HTTP
`POST /api/auth/ws-ticket`
- Auth: Bearer JWT
- Response: `{ "ticket": "<opaque>" }`
- TTL ticket: 15s, one-time use.

### WebSocket
`WS /api/ws/mobile/notifications?ticket=<ticket>`
- Query `ticket` obligatorio.
- Código de cierre:
  - 1008 sin ticket → `Ticket no proporcionado`
  - 1008 ticket inválido/expirado → `Ticket inválido o expirado`
  - 1008 usuario no encontrado → `Usuario no encontrado`
- Mensajes soportados:
  - Servidor → cliente: `connected`, `notification`, `update`, `ping`, `error`
  - Cliente → servidor: `pong` (heartbeat), mensajes de aplicación según necesidad.

## Arquitectura relevante
- Frontend composable singleton:
  `frontend/src/composables/useWebSocket.ts`
  Estado a nivel de módulo para evitar múltiples conexiones. La URL correcta es:
  ```ts
  const wsUrl = `${protocol}//${window.location.host}/api/ws/mobile/notifications?ticket=${encodeURIComponent(ticket)}`
  ```
  Antes incorrecta: `/api/ws/notifications` → 403.

- Store de auth:
  `frontend/src/stores/auth.ts`
  `connectRealtime()` / `disconnectRealtime()` se invocan en login/logout/initialize.

- Backend router:
  `backend/app/routers/websocket.py`
  `@router.websocket("/ws/mobile/notifications")` con validación de ticket y suscripción Redis.

- Generación/consumo de ticket:
  `backend/app/redis_client.py`
  `create_ws_ticket(user_id)` / `consume_ws_ticket(ticket)`
  Prefijo `corestream:ws_ticket:`, TTL 15s.

- Integración con FastAPI:
  `backend/app/main.py`
  `app.include_router(websocket.router, prefix="/api")`

## Proxy y desarrollo
- `vite.config.ts` proxy `/api` → `process.env.VITE_API_TARGET ?? 'http://backend:8000'`, `ws: true`.
- En `docker-compose.dev.yml`:
  - Frontend Vite expuesto en `127.0.0.1:5173:5173`
  - Backend en `127.0.0.1:8000:8000`
  - Proxy de Vite reenvía `/api/ws/mobile/notifications` al backend dentro de la misma origen.
- En producción el mismo origen sirve frontend y `/api`, por lo que la URL relativa sigue funcionando sin cambiar `VITE_API_BASE_URL`.

## Seguridad
- El JWT nunca aparece en URL ni logs de acceso.
- Ticket de un solo uso: tras `consume_ws_ticket` se borra de Redis → no replay.
- TTL corto 15s → ventana mínima de explotación si se filtra.
- Validación de existencia de usuario en BD antes de aceptar la conexión.
- Heartbeat bidireccional 30s y reconexión con backoff exponencial.

## Observabilidad
Logs típicos de éxito:
```
POST /api/auth/ws-ticket 200
WebSocket /api/ws/mobile/notifications?ticket=... 101
```
Logs de fallo por ruta incorrecta:
```
WebSocket /api/ws/notifications?ticket=... 403
connection rejected (403 Forbidden)
```
Corregir la ruta en `useWebSocket.ts` elimina el 403.

## Pruebas manuales
1. `docker compose -f docker-compose.yml -f docker-compose.dev.yml ps`
2. `http://127.0.0.1:8000/api/health` → ok
3. Login en `http://127.0.0.1:5173/login` con usuario creado por `create_admin`.
4. DevTools → Network → WS → `ws://127.0.0.1:5173/api/ws/mobile/notifications?ticket=...` estado 101.
5. `docker compose ... logs backend --tail 50` → sin 403.

## Cambios realizados
- `frontend/src/composables/useWebSocket.ts` línea 253: `/api/ws/notifications` → `/api/ws/mobile/notifications`.
- Reinicio de contenedores frontend/backend para aplicar cambio de Vite.

## Referencias
- `backend/app/routers/websocket.py`
- `backend/app/routers/auth.py` → `POST /auth/ws-ticket`
- `backend/app/redis_client.py` → gestión de tickets
- `frontend/src/composables/useWebSocket.ts`
- `frontend/src/stores/auth.ts`
- `frontend/vite.config.ts`
- `docker-compose.dev.yml`
