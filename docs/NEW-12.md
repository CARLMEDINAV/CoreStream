# NEW-12: integraciones salientes mediante webhooks

Un webhook es una integración configurada por un ADMIN que recibe un `POST`
JSON firmado cada vez que ocurre un evento clave de su cliente (tenant). Se
puede acotar a un proyecto concreto o dejarlo global, y se puede limitar a un
subconjunto de tipos de evento. Cada intento de entrega se registra y las
entregas fallidas se reintentan automáticamente.

El cuerpo se puede enviar en dos formatos (ver *Formatos de entrega*): el JSON
propio de CoreStream, o un mensaje compatible con los *Incoming Webhooks* de
Slack, para apuntar la URL directamente a un canal sin intermediarios.

El requisito se apoya en piezas que ya existían: el aislamiento multi-tenant de
TRV-01, las banderas comerciales de TRV-02, el RBAC y la cola de tareas del
worker ARQ. No se añadió un servicio de colas nuevo.

## Eventos suscribibles

Los eventos públicos son un conjunto estable, independiente de la auditoría
interna (`TicketEventType`). El mapa está en
`app/services/webhook_service.py` (`_TICKET_EVENT_MAP`).

| Valor de webhook      | Se dispara cuando...                        |
|-----------------------|---------------------------------------------|
| `TICKET_CREATED`      | se crea un ticket                           |
| `TICKET_ASSIGNED`     | se asigna o reasigna un ticket              |
| `STATUS_CHANGED`      | cambia el estado de un ticket               |
| `TICKET_REDIRECTED`   | se redirige un ticket a otro equipo         |
| `TICKET_COMPLETED`    | un ticket pasa a completado                 |
| `QUESTION_RAISED`     | se levanta una pregunta bloqueante          |
| `QUESTION_RESOLVED`   | se resuelve una pregunta bloqueante         |
| `COMMENT`             | se añade un comentario                      |
| `SUBTASK_COMPLETED`   | se completa una subtarea                    |

`TIMER_START`/`TIMER_PAUSE`/`TIMER_SYNC`, `MOVED` y `UPDATED` no disparan
webhooks: no son eventos de integración. Una lista `event_types` vacía
significa "todos los eventos".

## Carga útil (payload)

```json
{
  "event": "STATUS_CHANGED",
  "occurred_at": "2026-10-17T09:30:00+00:00",
  "project": { "id": "…", "name": "Portal de clientes" },
  "ticket": {
    "id": "…",
    "title": "El check-out falla en móvil",
    "status": "IN_PROGRESS",
    "priority": "HIGH",
    "assignee_id": "…",
    "epic_id": "…"
  },
  "actor": { "id": "…", "name": "Ana Ruiz" },
  "data": { "from_status": "TODO", "to_status": "IN_PROGRESS" }
}
```

- `project` es `null` si el ticket no cuelga de una épica con aplicación.
- `actor` es `null` en eventos sin usuario (p. ej. acciones automáticas).
- `data` sólo conserva primitivas del detalle del evento; nunca se serializan
  objetos ORM. Los identificadores se envían como cadenas.

El payload se construye a partir del ticket del propio cliente. **No incluye
datos de otros tenants bajo ninguna circunstancia** (ver la sección de
aislamiento).

### Cabeceras del `POST`

| Cabecera                 | Contenido                                   |
|--------------------------|---------------------------------------------|
| `Content-Type`           | `application/json`                          |
| `User-Agent`             | `CoreStream-Webhooks/1.0`                   |
| `X-CoreStream-Event`     | tipo de evento (`STATUS_CHANGED`, …)        |
| `X-CoreStream-Delivery`  | id de la entrega (para trazabilidad)        |
| `X-CoreStream-Signature` | `sha256=<hex>` (sólo si el webhook tiene secreto) |

### Firma HMAC

El cuerpo se firma con HMAC-SHA256 usando el secreto del webhook y el JSON
exacto que se envía:

```
X-CoreStream-Signature: sha256=<hmac_sha256_hex(secret, raw_body)>
```

El receptor debe recalcular la firma sobre el cuerpo **crudo** y compararla en
tiempo constante antes de confiar en el contenido. El secreto se genera con
256 bits de entropía (`secrets.token_hex(32)`) y **sólo se muestra una vez**
al crear o al rotar; las lecturas devuelven `has_secret` en lugar del valor.

## Formatos de entrega

El campo `format` del webhook decide el cuerpo que recibe el destino:

| Valor   | Cuerpo                                                  | Uso |
|---------|---------------------------------------------------------|-----|
| `JSON`  | el payload completo documentado arriba (por defecto)     | integraciones que consumen el esquema de CoreStream |
| `SLACK` | `{"text": …}` (compatible con Incoming Webhooks)         | pegar la URL de Slack directamente |

Con `SLACK`, CoreStream traduce el payload a un mensaje legible
(`app/services/webhook_service.py`, `build_slack_payload`). Ejemplo del evento
de prueba `PING`:

```json
{ "text": ":bell: *PING*\nAutor: Ana Ruiz\nEvento de prueba enviado desde CoreStream" }
```

Notas:

- La **firma HMAC cubre el cuerpo realmente enviado**: con `SLACK` se firma el
  mensaje de Slack, no el JSON interno.
- El payload canónico sigue guardándose en `webhook_deliveries.payload` (esquema
  CoreStream) para auditoría, sea cual sea el formato de envío.
- El formato sólo afecta al cuerpo; las cabeceras `X-CoreStream-*` se envían
  igual en ambos casos.

## Entrega y reintentos

1. El servicio de tickets registra el evento de negocio y, en la **misma
   transacción**, crea un `WebhookDelivery` en estado `PENDING` por cada
   webhook aplicable. Así nunca hay evento sin entrega registrada.
2. Tras el `commit`, la entrega se encola en ARQ
   (`worker.tasks.deliver_webhook`).
3. El worker hace el `POST` y guarda el resultado. Ante timeout, error de red o
   respuesta no-2xx, **relanza la excepción** para que ARQ reintente con la
   configuración de `WorkerSettings`: `max_tries = 3`, `retry_delay = 5 s`.
4. El estado final y el contador de intentos quedan en `webhook_deliveries` y
   en el resumen del webhook (`last_status`, `last_triggered_at`,
   `failure_count`).

Un fallo al preparar webhooks **nunca** tumba el cambio de negocio: el registro
es defensivo y silencioso (sólo deja traza en logs). El encolado posterior al
commit también es tolerante a fallos.

## Aislamiento multi-tenant

`Webhook` y `WebhookDelivery` heredan de `TenantMixin`, así que el filtro
automático de TRV-01 restringe cualquier consulta al cliente autenticado. Como
defensa adicional (y para no depender de que el `ContextVar` esté inicializado,
p. ej. en tests), la selección de webhooks filtra `client_id` de forma
**explícita** contra el cliente del ticket. Un ADMIN no puede leer, modificar ni
recibir eventos de webhooks de otro cliente.

## Roles y plan comercial

- **Sólo ADMIN.** El router se registra con `require_role([UserRole.ADMIN])`;
  TEAM_LEADER y DEVELOPER reciben 403.
- **Bandera comercial `webhooks`.** Se añadió a `CORE_FEATURES`, así que está
  incluida en `Basico`, `Pro` y `Enterprise`. Un cliente inactivo o con un plan
  desconocido no la obtiene (403 `FEATURE_NOT_INCLUDED`).
- Notificaciones al usuario se siguen sirviendo por el canal existente; NEW-12
  no introduce canales nuevos.

## Endpoints (`/api/webhooks`)

| Método | Ruta                              | Descripción                              |
|--------|-----------------------------------|------------------------------------------|
| GET    | `/`                               | Lista webhooks (filtros `project_id`, `is_active`) |
| POST   | `/`                               | Crea un webhook (devuelve `secret` una vez) |
| GET    | `/{id}`                           | Obtiene un webhook                       |
| PUT    | `/{id}`                           | Actualización parcial                    |
| DELETE | `/{id}`                           | Elimina el webhook y sus entregas        |
| POST   | `/{id}/rotate-secret`             | Rota el secreto (se muestra una vez)     |
| GET    | `/{id}/deliveries`                | Últimas entregas (`limit` 1–200)         |
| POST   | `/{id}/test`                      | Encola un evento de prueba (`PING`)      |
| GET    | `/deliveries/{delivery_id}`       | Obtiene una entrega concreta             |
| POST   | `/deliveries/{delivery_id}/retry` | Reencola una entrega fallida             |
| GET    | `/event-types`                    | Catálogo de eventos suscribibles         |

Validación de entrada: `name` (≤255, no vacío), `url` (≤1024, http/https,
ver SSRF), `event_types` (normalizados a mayúsculas y sin duplicados).

## Configuración

| Variable                      | Por defecto | Uso                                             |
|-------------------------------|-------------|-------------------------------------------------|
| `WEBHOOK_TIMEOUT_SECONDS`     | `10`        | Timeout del `POST` en el worker                 |
| `WEBHOOK_ALLOW_PRIVATE_URLS`  | `false`     | Permitir hosts privados/loopback (sólo pruebas) |

### Limitación conocida (SSRF)

`validate_webhook_url` rechaza esquemas que no sean http/https y bloquea
hosts `localhost` y direcciones IP privadas/reservadas cuando
`WEBHOOK_ALLOW_PRIVATE_URLS` está desactivado. **No resuelve DNS**, así que un
nombre de dominio que resuelva a una IP interna no se detecta en este punto.
Es una defensa básica, suficiente para un destino configurado por un ADMIN del
propio cliente; un endurecimiento completo (resolución y comprobación por
salto) queda como trabajo futuro.

## Backend

- `app/models/webhook.py` — `Webhook`, `WebhookDelivery` y sus enums
  (`WebhookEventType`, `WebhookDeliveryStatus`, `WebhookFormat`).
- `app/schemas/webhook.py` — validación y contratos de API.
- `app/services/webhook_service.py` — selección, payload, firma, encolado y
  traducción a Slack (`build_slack_payload`).
- `app/routers/webhooks.py` — CRUD y operaciones de ADMIN.
- `app/worker/tasks.py` — `deliver_webhook` (con `payload_format`) + `_update_delivery`.
- `app/worker/settings.py` — registra la tarea; reutiliza los reintentos.
- `app/middleware/commercial.py` — bandera `webhooks`.
- `app/main.py` — inclusión del router con feature + rol.

Se dispara desde el embudo de eventos de ticket ya existente
(`TransitionAuditService`, `TicketStateMachine.log_ticket_event`,
`TicketRedirectionService.redirect_ticket`). El volcado de entregas se acopló a
`flush_pending_notifications`, de modo que todos los puntos post-commit
existentes encolan también los webhooks.

## Frontend

- `src/views/admin/WebhooksView.vue` — alta/edición, activar/desactivar,
  enviar prueba, rotar secreto e historial de entregas con reintento.
- Entrada `AdminWebhooks` en el router (`/admin/webhooks`) y enlace en
  `AdminLayout`. La vista es exclusiva de ADMIN.
- `webhooks` en `src/services/api.ts` y tipos en `src/types/index.ts`.
- Los textos nuevos están en los cinco diccionarios (`es`, `en`, `fr`, `de`,
  `pt`).

## Aplicar y probar en local

Con el entorno y las variables del backend configurados, desde `backend`:

```powershell
..\.venv\Scripts\python.exe -m alembic upgrade head
```

Migraciones nuevas, en este orden: `b7c8d9e0f1a2` (tablas de webhooks) y
`c1d2e3f4a5b6` (columna `webhooks.format`). En este checkout quedan encadenadas
tras el head real de la base (`k7l8m9n0o1p2`).

Para probar de extremo a extremo hace falta un worker ARQ vivo
(`python -m arq app.worker.settings.WorkerSettings`) y un receptor HTTP que
registre los `POST`. En pruebas locales se puede apuntar a un receptor propio
activando `WEBHOOK_ALLOW_PRIVATE_URLS`; en producción debe permanecer en
`false`.

```powershell
# desde backend
..\.venv\Scripts\python.exe -m pytest tests/test_webhooks.py -q
..\.venv\Scripts\python.exe -m pytest tests/integration/test_webhooks.py -q

# desde frontend
npm run type-check
npm run build
```

## Verificación realizada

- 23 pruebas unitarias en `backend/tests/test_webhooks.py`: correctas.
  Cubren validación de URL, firma HMAC, selección por proyecto/tipo de evento,
  aislamiento multi-tenant del payload, encolado post-commit, la tarea de
  entrega (éxito y fallo con reintento) y el formato Slack (incluida la firma
  calculada sobre el cuerpo real enviado).
- Suite unitaria completa del backend: 312 correctas, 1 omitida.
- `ruff check app tests`: sin avisos.
- Frontend: `npm run type-check` correcto.
- Migración aplicada sobre PostgreSQL real (`alembic upgrade head` →
  `c1d2e3f4a5b6`) y recorrido manual de extremo a extremo con backend, worker y
  un receptor HTTP en la red de Docker: alta de un webhook `SLACK`, envío de
  prueba, entrega `SUCCESS` con cuerpo `{"text": …}` y firma válida, cambio de
  formato y borrado.
- Las pruebas de integración de `backend/tests/integration/test_webhooks.py`
  (RBAC, aislamiento por tenant y disparo real al crear un ticket) requieren
  PostgreSQL y Redis con permiso para crear la base de pruebas; el recorrido
  manual anterior cubre el mismo camino de extremo a extremo.
