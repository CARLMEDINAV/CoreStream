# WEB-16: Centro de notificaciones

El sistema incorpora un centro de notificaciones que permite a los usuarios autenticados consultar, gestionar y mantener actualizado el estado de sus notificaciones.

El requerimiento contempla la consulta de notificaciones, el contador de pendientes de lectura y las operaciones para marcar notificaciones individuales o todas las notificaciones como leídas.

---

## Backend

`app/routers/notifications.py` implementa los endpoints necesarios para la gestión de notificaciones del usuario autenticado.

| Operación          | Endpoint                                      | Descripción                                           |
| ------------------ | --------------------------------------------- | ----------------------------------------------------- |
| Listar             | `GET /api/notifications/`                     | Obtiene las notificaciones del usuario                |
| Contador           | `GET /api/notifications/unread-count`         | Obtiene la cantidad de notificaciones no leídas       |
| Marcar como leídas | `POST /api/notifications/mark-read`           | Marca una o varias notificaciones como leídas         |
| Marcar todas       | `POST /api/notifications/mark-all-read`       | Marca todas las notificaciones pendientes como leídas |
| Eliminar leídas    | `DELETE /api/notifications/read`              | Elimina las notificaciones ya leídas                  |
| Eliminar una       | `DELETE /api/notifications/{notification_id}` | Elimina una notificación específica                   |

La consulta de notificaciones siempre se realiza utilizando el usuario autenticado como referencia. El parámetro `unread_only` permite filtrar únicamente las notificaciones pendientes.

El contador de no leídas utiliza una consulta `COUNT` directamente sobre la base de datos, evitando cargar las notificaciones completas y manteniendo una operación de baja latencia.

La operación `mark-read` realiza una actualización SQL sobre las notificaciones recibidas, verificando que:

* la notificación pertenezca al usuario autenticado;
* el ID corresponda a una notificación existente;
* la notificación todavía se encuentre sin leer.

`mark-all-read` realiza una única actualización SQL sobre todas las notificaciones no leídas del usuario, manteniendo la operación atómica por usuario.

---

## Seguridad y aislamiento

Las operaciones reutilizan el sistema de autenticación existente.

Cada operación de modificación incorpora el usuario autenticado como condición de acceso, evitando que un usuario pueda modificar o eliminar notificaciones pertenecientes a otro usuario.

El aislamiento se mantiene mediante la condición:

```text
Notification.user_id == current_user.id
```

Por lo tanto, proporcionar directamente el ID de una notificación no permite acceder a ella si pertenece a otro usuario.

El `client_id` de la notificación continúa siendo asignado por el backend a partir del usuario destinatario. No se permite definir arbitrariamente el cliente desde el frontend.

---

## Modelo de datos

WEB-16 reutiliza el modelo existente `Notification`, sin incorporar cambios adicionales a su estructura.

Los principales campos utilizados son:

* `user_id`
* `client_id`
* `ticket_id`
* `incident_id`
* `title`
* `message`
* `type`
* `is_read`
* `read_at`
* `created_at`

Los tipos de notificación existentes incluyen:

* `TICKET_ASSIGNED`
* `STATUS_CHANGED`
* `TICKET_REDIRECTED`
* `TICKET_COMPLETED`
* `QUESTION_RAISED`
* `INCIDENT_REPORTED`
* `INCIDENT_ASSIGNED`
* `SYSTEM`

El servicio existente de notificaciones continúa siendo responsable de crear las notificaciones y asociarlas al usuario correspondiente.

---

## Esquemas

`app/schemas/notification.py` utiliza `NotificationMarkRead` para las operaciones de marcado de lectura.

El esquema recibe una lista de UUID:

```json
{
  "notification_ids": [
    "<notification_id>"
  ]
}
```

La validación exige que la lista contenga al menos una notificación.

Las respuestas de consulta utilizan `NotificationResponse`.

---

## Frontend

El frontend consume los endpoints del backend para proporcionar el centro de notificaciones al usuario autenticado.

Se permite:

* consultar las notificaciones;
* visualizar el contador de pendientes;
* marcar notificaciones individuales como leídas;
* marcar todas las notificaciones como leídas.

Las operaciones utilizan el sistema de autenticación existente, incluyendo la renovación del access token mediante el mecanismo de refresh.

No se modificó el mecanismo de autenticación para implementar WEB-16.

---

## Aplicación y pruebas en local

WEB-16 no requiere una nueva migración ni modificaciones adicionales del esquema de base de datos.

Con los servicios levantados mediante Docker:

```powershell
docker compose -f docker-compose.yml -f docker-compose.dev.yml ps
```

se pueden verificar los endpoints desde el entorno local.

### Consulta del contador

```text
GET /api/notifications/unread-count
```

### Consulta de notificaciones

```text
GET /api/notifications/
```

### Marcar notificaciones como leídas

```text
POST /api/notifications/mark-read
```

con un cuerpo similar a:

```json
{
  "notification_ids": [
    "<notification_id>"
  ]
}
```

### Marcar todas como leídas

```text
POST /api/notifications/mark-all-read
```

---

## Verificación realizada

Se realizó una prueba funcional completa del flujo de notificaciones.

Inicialmente, el usuario no tenía notificaciones pendientes:

```text
GET /api/notifications/unread-count
→ 0
```

Se creó posteriormente una notificación de prueba asociada al usuario autenticado.

El contador pasó correctamente a:

```text
GET /api/notifications/unread-count
→ 1
```

La consulta de notificaciones devolvió correctamente el registro creado con:

```text
is_read: false
```

Posteriormente se ejecutó:

```text
POST /api/notifications/mark-all-read
```

obteniendo:

```text
marked_as_read: 1
```

Al consultar nuevamente el contador:

```text
GET /api/notifications/unread-count
→ 0
```

También se verificó la operación `mark-read` desde el frontend.

Durante esta prueba, una petición recibió `401` debido a la expiración del access token. El frontend realizó correctamente la renovación mediante:

```text
POST /api/auth/refresh → 200
```

y posteriormente reintentó la operación:

```text
POST /api/notifications/mark-read → 200
```

Las consultas posteriores también respondieron correctamente:

```text
GET /api/notifications/ → 200
GET /api/notifications/unread-count → 200
```

---

## Resultado

WEB-16 queda **implementado y verificado funcionalmente**.

La implementación reutiliza la autenticación, el aislamiento de usuarios y el modelo de notificaciones existentes.
