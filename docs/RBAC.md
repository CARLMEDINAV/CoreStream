# RBAC — Matriz de permisos

Este documento describe **quién puede hacer qué** en CoreStream. Es la
referencia autoritativa: cualquier cambio de autorización en el backend debe
reflejarse aquí en el mismo commit.

## Roles

Definidos en `app/models/role.py` (`UserRole`) y reflejados en la tabla
`roles` (seedeada por la migración `a2b3c4d5e6f7_seed_base_roles`):

- **ADMIN** — el único que administra usuarios (invitar, cambiar roles,
  resetear contraseñas) y la estructura completa del sistema (aplicaciones,
  épicas, tickets). No ejecuta trabajo operativo sobre tickets (no puede
  iniciar/completar/preguntar) — ver nota sobre `require_non_admin` más
  abajo.
- **TEAM_LEADER** — gestiona el trabajo de su equipo: puede hacer todo lo que
  hace un DEVELOPER sobre tickets propios, más las acciones de gestión
  (crear/editar/borrar/reasignar tickets y épicas, crear/editar/borrar
  aplicaciones, resolver preguntas bloqueantes ajenas, redirigir tickets,
  gestionar reuniones e incidentes). No puede invitar usuarios, cambiar
  roles ni resetear contraseñas — eso queda exclusivo de ADMIN.
- **DEVELOPER** — ejecuta el trabajo: solo puede actuar sobre tickets/
  subtareas/documentos que le pertenecen (asignado o autor de la carga).
- **AUDITOR** — solo lectura del registro de auditoría (TRV-07/TRV-08
  nombran «ADMIN / Auditor» y «equipo de cumplimiento/Auditor» entre los
  roles involucrados). Existe para no tener que conceder ADMIN a quien solo
  debe leer: un ADMIN puede invitar usuarios, cambiar roles y resetear
  contraseñas, así que usarlo como acceso de lectura daría al auditor poder
  sobre el sistema que audita. No aparece en ningún otro `require_role`, así
  que todo lo demás le queda denegado por omisión, y tampoco puede recibir
  tickets asignados (`assert_assignable_user` lo rechaza).

Las listas de roles válidos derivan de `UserRole` en los tres sitios que las
usan (invitaciones, cambio de rol y el sembrado de los tests). Estaban
escritas a mano y se quedaron sin AUDITOR al añadirlo — una lista
desincronizada rechaza un rol válido sin que nada lo detecte.

`middleware/rbac.py` (`RBACRole`) sirve al decorador histórico
`require_permissions` (hoy sin llamadas activas) y es **un alias de
`UserRole`**, no un enum paralelo: cuando re-declaraba los roles a mano se
desincronizó dos veces (primero `GROUP_LEADER` en vez de `TEAM_LEADER`, luego
al añadir `AUDITOR`). El mecanismo realmente en uso en los routers es
`require_role(...)` de `middleware/auth.py`, que compara contra este mismo
conjunto de roles.
`_normalize_role` en ambos módulos lanza `ValueError`/`RuntimeError` ante un
rol desconocido — un typo en un nombre de rol falla ruidosamente, no deniega
en silencio.

## Helpers de autorización sobre tickets

`app/services/ticket_permissions.py` centraliza las reglas de ownership
sobre tickets, usadas por `routers/tickets.py`, `routers/subtasks.py` y
(para el caso de documentos) `routers/documents.py`:

| Helper | Regla |
|---|---|
| `require_non_admin` | Bloquea a ADMIN de las acciones de "trabajo" (start/complete/question): admins gestionan, no ejecutan. |
| `require_admin_or_leader` | Exige ADMIN o TEAM_LEADER. |
| `assert_can_manage_ticket` | ADMIN/TEAM_LEADER siempre puede; un DEVELOPER solo si es el asignado actual. Usado en edición de campos, mover de épica, reordenar, y en las mismas operaciones de subtareas. |
| `assert_is_current_assignee` | Solo el asignado actual, sin excepción de rol (ni ADMIN ni TEAM_LEADER). Usado en completar y en levantar una pregunta. |
| `claim_or_assert_assignee` | Si el ticket no tiene asignado, quien llama lo reclama; si ya tiene uno distinto, rechaza. Usado en `/start` — antes cualquiera podía "robar" un ticket asignado a otro con solo llamar a este endpoint. |
| `is_admin_or_leader` | Predicado usado para checks de ownership-o-rol (ej. borrar un documento: el autor de la carga, o ADMIN/TEAM_LEADER). |

## Matriz por recurso

### Aplicaciones (`/api/applications`)

| Acción | ADMIN | TEAM_LEADER | DEVELOPER |
|---|---|---|---|
| Listar / ver | ✅ | ✅ | ✅ |
| Crear / editar / borrar | ✅ | ✅ | ❌ |

Antes era ADMIN-only: obligaba al admin a crear cada proyecto nuevo en
persona, sin poder delegarlo en quien lleva el día a día del equipo. Se
extendió a TEAM_LEADER siguiendo el mismo criterio que ya aplicaba a
épicas/tickets — invitar usuarios, cambiar roles y resetear contraseñas
siguen siendo exclusivos de ADMIN (ver más abajo).

### Épicas (`/api/applications/{app_id}/epics`)

| Acción | ADMIN | TEAM_LEADER | DEVELOPER |
|---|---|---|---|
| Listar / ver | ✅ | ✅ | ✅ |
| Crear / editar / borrar / reordenar | ✅ | ✅ | ❌ |

### Tickets (`/api/tickets`)

| Acción | ADMIN | TEAM_LEADER | DEVELOPER (asignado) | DEVELOPER (ajeno) |
|---|---|---|---|---|
| Listar / ver / eventos | ✅ | ✅ | ✅ | ✅ |
| Crear | ✅ | ✅ | ❌ | ❌ |
| Editar campos / mover de épica / reordenar | ✅ | ✅ | ✅ | ❌ |
| Reasignar (`assignee_id` en el body de editar) | ✅ | ✅ | ❌ | ❌ |
| Borrar | ✅ | ✅ | ❌ | ❌ |
| Iniciar (`/start`) | ❌ (`require_non_admin`) | ✅ si no asignado o es él, ❌ si es de otro | ✅ (reclama si estaba libre) | ❌ |
| Completar (`/complete`) | ❌ | ❌ salvo que sea el asignado | ✅ | ❌ |
| Levantar pregunta bloqueante (`/question`) | ❌ | ❌ salvo que sea el asignado | ✅ | ❌ |
| Resolver pregunta bloqueante (`/resolve-question`) | ✅ | ✅ | ❌ | ❌ |
| Redirigir a otro usuario (`/redirect`) | ✅ | ✅ | ✅ si es el asignado | ❌ |

Notas:
- "Redirigir" está implementado en `routers/ticket_redirection.py`, montado
  **antes** de `routers/tickets.py` en `main.py` (comentario explícito:
  "MUST come before tickets.router"), por lo que es esa ruta la que
  atiende `POST /api/tickets/{id}/redirect`. `tickets.py` tenía un segundo
  `redirect_ticket` idéntico en path y verbo, inalcanzable — se eliminó en
  la fase de limpieza (fase 9).
- `require_non_admin` es una decisión de producto explícita: un ADMIN no
  ejecuta trabajo de ticket, solo lo gestiona.

### Subtareas (`/api/tickets/{ticket_id}/subtasks`)

Mismas reglas que la gestión de su ticket padre (`assert_can_manage_ticket`
sobre el `Ticket` referenciado por `ticket_id`):

| Acción | ADMIN | TEAM_LEADER | DEVELOPER (asignado al ticket) | DEVELOPER (ajeno) |
|---|---|---|---|---|
| Listar | ✅ | ✅ | ✅ | ✅ |
| Crear / editar / borrar / reordenar | ✅ | ✅ | ✅ | ❌ |

### Documentos (`/api/documents`)

| Acción | Quien subió el documento | ADMIN / TEAM_LEADER | Otro usuario |
|---|---|---|---|
| Listar / ver / descargar / traducir | ✅ (cualquier autenticado) | ✅ | ✅ |
| Cargar | ✅ (cualquier autenticado) | ✅ | ✅ |
| Borrar | ✅ | ✅ | ❌ |

La carga de documentos queda abierta a cualquier autenticado (no es un
recurso "propiedad de" nadie hasta que existe); el borrado sí requiere ser
el autor de la carga o tener rol de gestión.

### Notificaciones y adjuntos (`/api/notifications`, `/api/uploads`)

No usan `require_role`: cada consulta y cada archivo se filtra por
`current_user.id` en la propia query — un usuario solo puede ver o
manipular sus propias notificaciones y sus propios adjuntos, sin
distinción de rol.

### Usuarios e invitaciones (`/api/users`, `/api/invitations`)

| Acción | ADMIN | TEAM_LEADER | DEVELOPER |
|---|---|---|---|
| Crear usuario directamente | ✅ | ❌ | ❌ |
| Listar usuarios activos | ✅ | ✅ | ❌ |
| Listar incluyendo desactivados (`?include_inactive=true`) | ✅ | ❌ | ❌ |
| Ver perfil propio (`/me`) | ✅ | ✅ | ✅ |
| Editar / borrar / cambiar rol / resetear contraseña de otro usuario | ✅ | ❌ | ❌ |
| Desactivar (`DELETE /{id}`) / reactivar (`POST /{id}/activate`) | ✅ | ❌ | ❌ |
| Crear invitación | ✅ | ❌ | ❌ |
| Aceptar invitación / consultar token | público (sin autenticar) | | |

### Reuniones (`/api/meetings`)

| Acción | ADMIN | TEAM_LEADER | DEVELOPER |
|---|---|---|---|
| Listar / ver | ✅ | ✅ | ✅ |
| Crear / editar / registrar asistencia | ✅ | ✅ | ❌ |

### Incidentes (`/api/incidents`)

| Acción | ADMIN | TEAM_LEADER | DEVELOPER |
|---|---|---|---|
| Crear / listar / ver | ✅ | ✅ | ✅ |
| Editar (`PATCH /{id}`) | ✅ | ✅ | ❌ |
| Cambiar estado (`PATCH /{id}/status`) | ✅ (cualquier autenticado; sin ownership) | ✅ | ✅ |

### Tickets de soporte (`/api/support-tickets`)

| Acción | ADMIN | TEAM_LEADER | DEVELOPER |
|---|---|---|---|
| Crear / listar / ver / investigar / resolver | ✅ | ✅ | ✅ |
| Asignar (`/assign`) | ❌ | ✅ | ❌ |

### Registro de auditoría (`/api/audit-logs`)

| Acción | ADMIN | AUDITOR | TEAM_LEADER | DEVELOPER |
|---|---|---|---|---|
| Consultar (`GET /`) | ✅ | ✅ | ❌ | ❌ |
| Exportar (`GET /export`) | ✅ con plan Enterprise | ✅ con plan Enterprise | ❌ | ❌ |

El registro contiene la actividad de todos los usuarios del cliente, así que su
consulta queda en ADMIN y AUDITOR: un TEAM_LEADER gestiona el trabajo de su
equipo, no audita a sus miembros. Ambos endpoints están además acotados al
`client_id` del usuario y a la profundidad que concede su plan — ver la sección
de auditoría más abajo.

## Verificación

Los casos negativos de esta matriz están cubiertos por
`backend/tests/integration/test_rbac.py` y `test_tickets.py`. Los tres casos
concretos detectados en la auditoría original quedan verificados:

- `DELETE /api/tickets/{id}` sobre un ticket ajeno → **403** (antes: 204,
  borrado permanente).
- `POST /api/tickets/{id}/start` sobre un ticket ajeno ya asignado → **403**
  (antes: 200, reasignaba el ticket a quien llamaba).
- `POST /api/epics/` como DEVELOPER → **403** (antes: 201).


## Control comercial (TRV-02)

Los permisos anteriores también requieren que el plan del cliente incluya la
función solicitada. ADMIN no tiene una excepción comercial. El backend consulta
`clients.commercial_plan` usando el `client_id` del usuario autenticado en cada
solicitud protegida y devuelve 403 con `detail.code = FEATURE_NOT_INCLUDED`
cuando la función no está disponible.

Basico incluye proyectos, tickets, documentos, equipo, incidencias, reuniones,
soporte, notificaciones y consulta de auditoría. Pro añade Analítica y traducción
de documentos. Enterprise añade la exportación del registro de auditoría.
`GET /api/auth/commercial-profile` devuelve el plan, estado del cliente, banderas
y días de retención para la interfaz. Es de solo lectura; ningún rol de cliente
puede cambiar su plan por esta API. El plan no concede permisos adicionales de rol
ni de pertenencia.

Ver [TRV-02](./TRV-02.md) para la matriz de banderas, migración y pruebas.

## Auditoría de logs (TRV-07 / TRV-08)

Hay **dos** registros distintos, y conviene no confundirlos:

| | `public.ticket_events` | `audit.audit_logs` |
|---|---|---|
| Qué registra | Historial de negocio de un ticket | Actos de los usuarios sobre la API |
| Para quién | La UI, visible a cualquiera que vea el ticket | ADMIN / auditor |
| Lo escribe | Los servicios de dominio | `middleware/audit.py`, por petición |
| Caduca | No | Sí, según el plan (TRV-08) |
| Se puede modificar | Sí (es dato operativo) | No: trigger `BEFORE UPDATE` aborta |
| Se puede borrar | Sí | Solo la purga de retención |

`audit.audit_logs` registra, por cada petición auditable: actor (id, email y rol
desnormalizados), verbo y ruta, plantilla de ruta, tipo e id del recurso, código
de estado, resultado, IP, User-Agent, duración y `request_id` para correlacionar
con los logs de aplicación.

**El recurso afectado.** `resource_id` se extrae de los parámetros de ruta, lo
que cubre editar, borrar y las acciones sobre un objeto concreto. En una
**creación** no hay parámetro de ruta del que sacarlo, así que cada handler de
creación declara el suyo con `set_audit_resource("<tipo>", creado.id)` — si no,
el registro diría qué colección se tocó pero no qué objeto nació. Están
cubiertos los doce endpoints de creación (aplicación, épica, ticket, subtarea,
documento, incidente, reunión, asistencia, ticket de soporte, invitación,
usuario y alta por invitación).

**Dónde vive.** En su propio esquema `audit`, no en `public`. Eso es lo que hace
literal el criterio «no se almacenan en las tablas operativas»: es otro
namespace, con permisos otorgables y revocables por separado, al que ningún
servicio de dominio escribe. La migración `j6k7l8m9n0o1` lo crea.

**Los destinos del evento.** La derivación es una abstracción
(`services/audit_sinks.py`), no una lista de llamadas en el middleware: el
middleware depende de `AuditSink` y no sabe cuántos destinos hay ni cuáles son.
Los activos los nombra `AUDIT_SINKS`, y `CompositeSink` los aísla entre sí — si
la base de datos no está disponible, la línea de log es la única constancia que
queda del acto, y al revés.

| Destino | Qué aporta |
|---|---|
| `DatabaseSink` | La fila en `audit.audit_logs`: el almacén consultable, exportable y purgable. **Obligatorio** — el arranque falla sin él |
| `LogStreamSink` | Una línea JSON por el logger `corestream.audit.event` (clave `audit` del payload, ver `logging_config.py`). Es lo que recoge el driver de logs de Docker |
| `ElasticSink` | Envío directo a Elasticsearch, índice con sufijo de fecha (`corestream-audit-2026.10.03`) para que el ILM de Elastic aplique su propio archivado |

Un nombre desconocido en `AUDIT_SINKS` aborta el arranque: creer que los eventos
van a un motor que nadie construyó es peor que no tenerlo.

### Cómo cumplir «se derivan a un motor especializado (ELK/CloudWatch)»

El criterio nombra dos motores y hay un camino para cada uno. Ninguno requiere
cambiar código de la aplicación:

| Motor | Cómo | Coste |
|---|---|---|
| **ELK**, en la VM | `docker compose --profile elk up -d` + `AUDIT_SINKS=…,elastic` | 1 contenedor, ~1,2 GB de RAM |
| **ELK**, gestionado | `ELASTIC_URL` + `ELASTIC_API_KEY` de Elastic Cloud | Nada que operar; cuota |
| **ELK**, por el driver | Dejar `logstream` y apuntar el driver de Docker a un Logstash/Fluent Bit | Sin latencia en la petición |
| **CloudWatch** | `logging.driver: awslogs` en el servicio `backend` de `docker-compose.yml` | Cero contenedores; requiere AWS e IAM |
| **Cloud Logging** | `logging.driver: gcplogs` | Cero contenedores; requiere GCP |

El perfil `elk` del repositorio levanta Elasticsearch **opcional** (`profiles:
["elk"]`), así que `docker compose up -d` sigue levantando solo backend,
frontend y worker. Decisiones de ese servicio, y por qué:

- **No publica puerto.** Solo lo alcanzan los contenedores de este compose por
  nombre (`http://elasticsearch:9200`). Es el control de seguridad principal:
  los otros proyectos de la VM no llegan.
- **`xpack.security.enabled=true`** con `ELASTIC_PASSWORD`: aunque el alcance
  ya sea la red interna, el registro de auditoría es justo lo que no debe
  quedar legible para un contenedor vecino. TLS deshabilitado a propósito —
  el tráfico no sale de esa red y los certificados autofirmados no aportarían.
- **Heap 512 MB fijo**, límite de contenedor 1,5 GB, sin ML ni Watcher. El
  límite está medido, no estimado: con ese heap el contenedor usa ~1,15 GiB en
  total, porque Lucene, las pilas de hilos y el metaespacio viven fuera del
  heap — con 1 GB el kernel lo mata por OOM. En disco son ~0,8 KB por evento.
- **Plantilla de índice** con 0 réplicas (un solo nodo), 1 shard y
  `dynamic: false`. Todos los campos son `keyword` salvo fechas y enteros.
  Esto no es solo ahorro: el mapeo dinámico indexa un UUID como texto
  analizado y lo parte por los guiones, así que una consulta exacta sobre
  `client_id` **no coincide con nada** y la purga borraba cero en silencio.
- **Retención propia.** Un índice diario mezcla tenants, así que soltarlo
  entero solo sería posible pasada la retención más larga — y eso conservaría
  los eventos de un cliente Basico los 730 días del plan Enterprise. El cron
  borra por consulta, con los mismos grupos y cortes que la tabla
  (`ElasticSink.purge`).

Si Elasticsearch se cae, se para o se queda sin disco, se pierde capacidad de
búsqueda, **no la prueba**: el registro oficial sigue siendo
`audit.audit_logs`. Por eso puede vivir sin réplicas y como servicio opcional.

`ElasticSink` envía dentro de la petición, así que su timeout es corto
(`ELASTIC_TIMEOUT_SECONDS`, 2 s) y un Elasticsearch caído queda aislado por
`CompositeSink`. Para tráfico alto, la ruta sin latencia en petición es el
driver de Docker sobre la salida de `LogStreamSink`.

Añadir un motor nuevo es escribir una clase con `emit` y registrar su fábrica en
`SINK_FACTORIES`. Ningún otro módulo cambia: ni el middleware, ni el servicio,
ni el router.

Un fallo de auditoría **no** tumba la petición: se registra con nivel
`exception` y la respuesta sigue su curso. Dejar la API fuera de servicio
porque el registro no está disponible no es un comportamiento que TRV-07 exija.

**El worker también escribe.** La purga de retención se audita a sí misma, así
que `corestream-worker` recibe las mismas variables de `AUDIT_SINKS`. No recibe
`FORWARDED_ALLOW_IPS`: no sirve HTTP, y validarla allí hacía abortar su
contenedor por una variable que para él no significa nada (`validate_http_runtime`
en `config.py` es la que solo ejecuta la API).

**Qué se registra y qué no.** Con `AUDIT_READS=true` (el valor por defecto) se
registra **toda** petición que llegue a un handler: es la lectura estricta de
«todo evento de la plataforma» que pide la descripción, así que queda constancia
de quién consultó qué y no solo de quién modificó.

Con `AUDIT_READS=false` se registran solo las mutaciones
(`POST`/`PUT`/`PATCH`/`DELETE`), cualquier respuesta 401/403/429 sea cual sea el
verbo, y todo `/api/auth/*`. Es la vía de escape si el volumen aprieta.

Las sondas `/health`, `/api/health` y `/metrics` quedan excluidas en ambos casos:
las consulta el orquestador en bucle y no son actos de ningún usuario. Una
lectura concreta puede forzar su registro con `mark_auditable()` — lo hace la
exportación del propio registro, que debe quedar auditada incluso con
`AUDIT_READS=false`.

**Coste de auditar lecturas, medido.** La entrada se escribe dentro de la
petición, así que cada GET añade una ida y vuelta a Postgres. El `INSERT +
COMMIT` en sí son ~3,4 ms; el resto es la latencia de red hacia la base (en un
entorno con la base en otra máquina eso puede dominar: medido sobre Docker en
Windows, un `SELECT 1` pelado costaba 88 ms). Con el destino `elastic` activo se
suma un envío HTTP por petición — para tráfico alto, la ruta sin latencia en
petición es el driver de logs de Docker en vez del sink.

**Lo que no depende del rol.** El filtrado por `client_id` y por retención se
aplica en la propia consulta, no por rol: un ADMIN no puede ver la auditoría de
otro cliente ni historial más profundo del que su plan concede, aunque la fila
todavía exista porque el cron de purga no ha pasado.

**Operaciones que se auditan a sí mismas.** La exportación (`resource_type =
audit_export`) y la purga diaria del worker (`resource_type =
audit_retention`). Sin eso, las dos únicas operaciones que extraen o eliminan el
registro serían las únicas que no dejan rastro.

**Inmutabilidad y caducidad.** Dos triggers, con una diferencia deliberada:

- `audit_logs_immutable` (`BEFORE UPDATE`) aborta **siempre**. Un registro de
  auditoría no se reescribe nunca.
- `audit_logs_guard_delete` (`BEFORE DELETE`) aborta salvo que la sesión declare
  `corestream.audit_purge = 'on'`, que fija únicamente `purge_expired()` con un
  `SET LOCAL` — válido solo durante esa transacción, así que la autorización no
  se le queda pegada a la conexión al volver al pool.

El motivo de la segunda es que la aplicación y cualquier sesión de `psql`
comparten credenciales: sin el guardia, un `DELETE FROM` suelto borraría la
prueba y la inmutabilidad dependería de que nadie se equivoque. Con él, caducar
bajo una política publicada sigue siendo posible y borrar a mano, no.

La purga es por fila y por cliente, porque la retención depende del plan — un
borrado por rango de fechas global, o un particionado por fecha, no podrían
expresarlo: solo se podría soltar una partición cuando hubiera caducado el
cliente de mayor retención.

**Requisito de despliegue (obligatorio).** La columna `ip` solo sirve como
prueba si `FORWARDED_ALLOW_IPS` apunta al proxy concreto. Con el comodín `*`,
uvicorn acepta `X-Forwarded-For` de cualquier origen y es el propio cliente
quien decide qué IP queda registrada — y por el mismo motivo el límite por IP
de `/auth/login` se podría saltar rotando la cabecera.

Por eso **`config.py` aborta el arranque** con `ENVIRONMENT=production` si el
valor es `*` o está vacío, igual que ya hacía con `SECRET_KEY` y con
`ALLOWED_ORIGINS=*`. En desarrollo el comodín sigue permitido (no hay proxy
delante) y el arranque solo avisa. Ver [`DEPLOYMENT.md`](./DEPLOYMENT.md).

## Dónde vive cada cosa

| Módulo | Responsabilidad |
|---|---|
| `app/plans.py` | Catálogo de planes, banderas y retención. Puro: ni FastAPI ni base de datos, para poder ser la dependencia común del middleware y de los servicios |
| `app/middleware/commercial.py` | Aplica el plan por petición (`require_feature`) |
| `app/middleware/audit.py` | Decide si la petición es auditable y construye la entrada |
| `app/services/audit_records.py` | Forma de la entrada: resultado y conversión a primitivos |
| `app/services/audit_sinks.py` | Destinos de la derivación |
| `app/services/audit_service.py` | Lo que habla con la base de datos: registrar, purgar, consultar |
| `app/services/audit_export.py` | Formatos de exportación, uno por `ExportFormat` |
| `app/routers/audit_logs.py` | HTTP: consulta y exportación |
