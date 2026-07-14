# Arquitectura de CoreStream v1.0

> Documento de referencia técnica de la arquitectura del sistema CoreStream.
> Última actualización: [COMPLETAR: fecha]
> Autor(es): [COMPLETAR: nombre(s) del equipo]

---

## Tabla de Contenidos

1. [Resumen General](#1-resumen-general)
2. [Diagrama de Arquitectura](#2-diagrama-de-arquitectura)
3. [Componentes Principales](#3-componentes-principales)
4. [Estructura de Carpetas](#4-estructura-de-carpetas)
5. [Patrones de Diseño](#5-patrones-de-diseño)
6. [Flujos Principales](#6-flujos-principales)
7. [Integraciones Externas](#7-integraciones-externas)
8. [Seguridad](#8-seguridad)
9. [Performance y Escalabilidad](#9-performance-y-escalabilidad)
10. [Deployment](#10-deployment)
11. [Anexos](#11-anexos)

---

## 1. Resumen General

CoreStream es una plataforma de gestión de tickets/épicas orientada a equipos de desarrollo, con soporte de notificaciones en tiempo real, control de acceso basado en roles y un flujo de trabajo tipo kanban (workbench).

**Stack tecnológico principal:**

| Capa | Tecnología |
|---|---|
| Frontend | Vue 3 + TypeScript + Vite + Pinia + Tailwind CSS |
| Backend | FastAPI (Python) |
| Base de Datos | PostgreSQL |
| Cache / Cola de mensajes | Redis + ARQ (async task queue) |
| Comunicación en tiempo real | WebSockets |
| ORM / Migraciones | SQLAlchemy + Alembic |

[COMPLETAR: versión exacta de CoreStream, fecha de release v1.0, objetivos de negocio del sistema]

---

## 2. Diagrama de Arquitectura

### 2.1 Vista General del Flujo Frontend → Backend → BD

```
                              ┌───────────────────────────────────────────┐
                              │              CLIENTE (Browser)             │
                              │                                             │
                              │   ┌─────────────────────────────────────┐   │
                              │   │           Vue 3 SPA (Vite)            │   │
                              │   │  ┌───────────┐  ┌──────────────────┐ │   │
                              │   │  │  Views /  │  │  Pinia Stores    │ │   │
                              │   │  │ Components│◄─┤ (auth, tickets,  │ │   │
                              │   │  │           │  │  notifications)  │ │   │
                              │   │  └─────┬─────┘  └────────┬─────────┘ │   │
                              │   │        │                 │           │   │
                              │   │  ┌─────▼─────┐    ┌──────▼───────┐   │   │
                              │   │  │  Router   │    │  Composables │   │   │
                              │   │  │ (Vue Rtr) │    │ (useWebSocket│   │   │
                              │   │  └───────────┘    │  useDragDrop)│   │   │
                              │   │                   └──────┬───────┘   │   │
                              │   │  ┌────────────────────────▼───────┐  │   │
                              │   │  │   services/ (Axios HTTP client) │  │   │
                              │   │  └────────────────┬────────────────┘  │   │
                              │   └────────────────────┼───────────────────┘   │
                              └────────────────────────┼───────────────────────┘
                                          │  HTTPS (REST)      │  WSS (WebSocket)
                                          ▼                    ▼
                              ┌─────────────────────────────────────────────┐
                              │                 BACKEND (FastAPI)             │
                              │                                                │
                              │  ┌──────────────┐   ┌────────────────────┐   │
                              │  │  Middleware  │   │   Routers (API)     │   │
                              │  │  (Auth/JWT,  │──►│  auth, tickets,     │   │
                              │  │   CORS, etc.)│   │  epics, users,      │   │
                              │  └──────────────┘   │  notifications,     │   │
                              │                      │  websocket, uploads │   │
                              │                      └─────────┬───────────┘   │
                              │                                │               │
                              │                      ┌─────────▼───────────┐   │
                              │                      │      Services        │   │
                              │                      │  (lógica de negocio, │   │
                              │                      │  notification_service│   │
                              │                      └─────────┬───────────┘   │
                              │                                │               │
                              │            ┌───────────────────┼──────────────┐│
                              │            ▼                   ▼              ││
                              │  ┌───────────────────┐  ┌──────────────────┐  ││
                              │  │  SQLAlchemy Models │  │  Redis Client     │  ││
                              │  │  (schemas + ORM)   │  │  (pub/sub)        │  ││
                              │  └─────────┬──────────┘  └─────────┬─────────┘  ││
                              │            │                        │            ││
                              │            │              ┌─────────▼─────────┐  ││
                              │            │              │  ARQ Worker        │  ││
                              │            │              │  (async tasks /    │  ││
                              │            │              │   background jobs) │  ││
                              │            │              └─────────┬─────────┘  ││
                              └────────────┼────────────────────────┼────────────┘│
                                           ▼                        ▼
                              ┌─────────────────────┐   ┌───────────────────────┐
                              │     PostgreSQL       │   │        Redis          │
                              │  (datos persistentes)│   │ (pub/sub + cache +    │
                              │                      │   │  cola de tareas ARQ)  │
                              └─────────────────────┘   └───────────────────────┘
```

### 2.2 Flujo de Notificaciones en Tiempo Real (detalle)

```
HTTP Router (ej: tickets.py)
   │
   ▼
notify_*() en notification_service.py
   │
   ▼
db.commit()  ─────────────────────► PostgreSQL (persistencia)
   │
   ▼
flush_pending()  ──► encola job en Redis (ARQ)
   │
   ▼
ARQ Worker (worker/tasks.py)
   │
   ▼
redis.publish("user:{id}:notifications", payload JSON)
   │
   ▼
routers/websocket.py  (pubsub.get_message() en loop)
   │
   ▼
websocket.send_json({"type": "notification", ...})
   │
   ▼
useWebSocket.ts (frontend) → handleMessage()
   │
   ├──► notificationsStore.addNotification()  → Toast (NotificationContainer.vue)
   └──► ticketsStore.fetchMyWorkbench()        → Refresco automático de tickets
```

[COMPLETAR: diagrama de despliegue de infraestructura (VPC, regiones, balanceadores) si aplica]

---

## 3. Componentes Principales

### 3.1 Frontend — Vue 3

- **Framework:** Vue 3 (Composition API) + TypeScript + Vite como bundler.
- **Estado global:** Pinia (`stores/`) — ej. `authStore`, `ticketsStore`, `notificationsStore`.
- **Ruteo:** Vue Router (`router/`).
- **Estilos:** Tailwind CSS.
- **Composables reutilizables:** `useWebSocket`, `useDragDrop`, `useTimer` (lógica encapsulada y testeada con Vitest).
- **Comunicación HTTP:** Axios (`services/`), cliente centralizado con interceptores [COMPLETAR: detalle de interceptores de auth/refresh token].
- **Comunicación en tiempo real:** WebSocket nativo gestionado por `useWebSocket.ts`.
- **Internacionalización:** `i18n/` (soporte multi-idioma).
- **Testing:** Vitest (unit) + Cypress (e2e).

[COMPLETAR: librerías de UI adicionales, versión exacta de Vue/Vite, estrategia de code-splitting]

### 3.2 Backend — FastAPI

- **Framework:** FastAPI (Python), servidor ASGI [COMPLETAR: uvicorn/gunicorn, nº de workers].
- **Routers (`app/routers/`):** separación por dominio — `auth`, `tickets`, `epics`, `subtasks`, `users`, `applications`, `documents`, `uploads`, `notifications`, `websocket`, `analytics`, `ticket_redirection`.
- **Middleware (`app/middleware/`):** autenticación JWT, CORS, [COMPLETAR: rate limiting, logging].
- **Servicios (`app/services/`):** lógica de negocio desacoplada de los routers (ej. `notification_service.py`).
- **Modelos (`app/models/`):** entidades SQLAlchemy — `user`, `role`, `ticket`, `ticket_event`, `epic`, `subtask`, `application`, `document`, `notification`.
- **Schemas (`app/schemas/`):** contratos Pydantic para validación de entrada/salida (request/response DTOs).
- **Worker (`app/worker/`):** tareas asíncronas ejecutadas por ARQ (ej. publicación de eventos a Redis).
- **Migraciones:** Alembic (`alembic/`, `migrations/`).
- **Validación:** Pydantic v2.

[COMPLETAR: versión de Python, versión de FastAPI]

### 3.3 Base de Datos — PostgreSQL

- Motor relacional principal, acceso vía SQLAlchemy ORM (async/sync — [COMPLETAR]).
- Migraciones versionadas con Alembic.
- Entidades principales: `users`, `roles`, `tickets`, `ticket_events`, `epics`, `subtasks`, `applications`, `documents`, `notifications`.

[COMPLETAR: diagrama entidad-relación completo, índices críticos, particionamiento si existe]

### 3.4 Redis

- **Pub/Sub:** canal `user:{id}:notifications` para eventos en tiempo real.
- **Cola de tareas:** ARQ usa Redis como backend para encolar y ejecutar jobs asíncronos (ej. publicar notificaciones, envíos diferidos).
- **Cache:** [COMPLETAR: qué datos se cachean, TTLs]

---

## 4. Estructura de Carpetas del Proyecto

```
CoreStream/
├── backend/
│   ├── app/
│   │   ├── main.py                 # Punto de entrada FastAPI
│   │   ├── config.py               # Configuración (env vars, settings)
│   │   ├── database.py             # Conexión SQLAlchemy / sesión DB
│   │   ├── redis_client.py         # Cliente Redis (pub/sub)
│   │   ├── middleware/             # Auth, CORS, etc.
│   │   ├── models/                 # Entidades SQLAlchemy (ORM)
│   │   ├── schemas/                # DTOs Pydantic
│   │   ├── routers/                # Endpoints REST + WebSocket
│   │   ├── services/               # Lógica de negocio
│   │   ├── worker/                 # Tareas asíncronas (ARQ)
│   │   └── scripts/                # Scripts de utilidad/seed
│   ├── alembic/ , migrations/       # Migraciones de base de datos
│   ├── tests/                      # Tests backend (pytest)
│   ├── requirements.txt            # Dependencias Python
│   └── Dockerfile
│
├── frontend/
│   ├── src/
│   │   ├── main.ts                 # Punto de entrada Vue
│   │   ├── App.vue                 # Componente raíz
│   │   ├── components/             # Componentes reutilizables
│   │   ├── views/                  # Vistas/páginas (rutas)
│   │   ├── layouts/                # Layouts de página
│   │   ├── router/                 # Configuración de Vue Router
│   │   ├── stores/                 # Pinia stores (estado global)
│   │   ├── composables/            # Lógica reutilizable (useWebSocket, etc.)
│   │   ├── services/                # Clientes HTTP (Axios)
│   │   ├── directives/             # Directivas Vue custom
│   │   ├── i18n/                   # Traducciones
│   │   ├── types/                  # Tipos TypeScript
│   │   └── assets/                 # Recursos estáticos
│   ├── cypress/                    # Tests e2e
│   ├── package.json
│   └── vite.config.ts
│
├── docker-compose.yml               # Orquestación local (backend + frontend + DB + Redis)
├── Dockerfile                       # [COMPLETAR: para qué servicio]
├── railway.json                     # Configuración de despliegue backend (Railway)
├── vercel.json.bak                  # Configuración de despliegue frontend (Vercel)
└── sprints.md                       # Tracking de sprints del proyecto
```

[COMPLETAR: confirmar si `docker-compose.yml` orquesta también Redis/Postgres localmente; detallar carpeta `Dock/`]

---

## 5. Patrones de Diseño Utilizados

| Patrón | Dónde se aplica | Propósito |
|---|---|---|
| **Layered Architecture** (Router → Service → Model) | Backend (`routers/` → `services/` → `models/`) | Separar transporte HTTP, lógica de negocio y acceso a datos |
| **Repository/ORM implícito** | `models/` + SQLAlchemy | Abstracción del acceso a base de datos |
| **DTO / Schema Validation** | `schemas/` (Pydantic) | Contratos explícitos de entrada/salida, validación automática |
| **Pub/Sub** | Redis + `redis_client.py` + `worker/tasks.py` | Desacoplar la generación de eventos de su consumo (notificaciones) |
| **Worker Queue / Background Jobs** | ARQ (`worker/`) | Procesar tareas asíncronas sin bloquear el request-response HTTP |
| **Composable Pattern** | Frontend `composables/` (`useWebSocket`, `useDragDrop`, `useTimer`) | Encapsular y reutilizar lógica con estado reactivo |
| **Store Pattern (Flux-like)** | Pinia (`stores/`) | Estado global centralizado y predecible en el frontend |
| **Middleware Pattern** | `backend/app/middleware/` | Interceptar requests para auth, CORS, logging de forma transversal |
| **RBAC (Role-Based Access Control)** | `models/role.py` (`ADMIN`, `TEAM_LEADER`, `DEVELOPER`) | Control de autorización por rol |
| **Event Sourcing parcial** | `ticket_event.py` | Registro histórico de cambios de estado de tickets |

[COMPLETAR: patrones adicionales identificados por el equipo, ej. Factory, Strategy, Observer explícitos si existen]

---

## 6. Flujos Principales

### 6.1 Autenticación

```
1. Usuario envía credenciales (email/password) → POST /api/auth/login
2. Backend valida contra `users` (password hasheado con bcrypt vía passlib)
3. Backend genera JWT (python-jose) con claims (user_id, role, exp)
4. Frontend almacena el token [COMPLETAR: localStorage / cookie httpOnly / memoria]
5. authStore (Pinia) guarda estado de sesión y dispara conexión WebSocket
6. Requests subsecuentes envían el JWT en header Authorization: Bearer <token>
7. Middleware de backend valida el token y adjunta el usuario autenticado al request
```

[COMPLETAR: manejo de refresh tokens, expiración, logout, endpoints exactos de `auth.py` vs `auth_simple.py`]

### 6.2 Creación de Ticket

```
1. Usuario completa formulario en frontend (view de creación de ticket)
2. ticketsStore.createTicket() → POST /api/tickets vía Axios
3. Router `tickets.py` valida payload contra schema Pydantic
4. Se crea el registro en `tickets` (SQLAlchemy) + `ticket_events` (evento de creación)
5. Se ejecuta notify_*() → notification_service.py
6. db.commit() persiste ticket + notificación
7. flush_pending() encola evento en Redis vía ARQ
8. Worker publica en canal Redis → WebSocket → frontend actualiza Workbench en tiempo real
9. Respuesta HTTP 201 retorna el ticket creado al cliente
```

[COMPLETAR: validaciones de negocio específicas, campos obligatorios, relación con epics/subtasks]

### 6.3 Cambio de Estado de Ticket

```
1. Usuario arrastra ticket entre columnas (useDragDrop.ts) o cambia estado manualmente
2. ticketsStore.updateStatus(ticketId, newStatus) → PATCH /api/tickets/{id}/status
3. Router valida transición de estado permitida [COMPLETAR: máquina de estados / reglas]
4. Se registra un nuevo `ticket_event` (auditoría del cambio)
5. notify_*() dispara evento STATUS_CHANGED
6. Flujo de notificación en tiempo real (ver sección 2.2) notifica a los usuarios relevantes
7. ticketsStore.fetchMyWorkbench() refresca la vista de todos los clientes conectados afectados
```

[COMPLETAR: diagrama de máquina de estados de un ticket — estados válidos y transiciones permitidas]

---

## 7. Integraciones Externas

| Servicio | Uso |
|---|---|
| **Vercel** | Hosting y despliegue continuo del frontend (Vue SPA) |
| **Railway** | Hosting y despliegue continuo del backend (FastAPI) + posiblemente PostgreSQL/Redis gestionados |
| **GitHub** | Control de versiones, Pull Requests, CI/CD (workflows), revisión de código |

[COMPLETAR: 
- ¿Se usa GitHub Actions para CI/CD? ¿Qué pipelines existen (tests, lint, build, deploy)?
- ¿Railway hostea también las instancias de PostgreSQL y Redis, o son servicios externos (ej. Upstash, Supabase)?
- ¿Existen integraciones con terceros para email, storage de archivos (`uploads.py`/`documents.py`), Slack, etc.?
]

---

## 8. Consideraciones de Seguridad

### 8.1 Autenticación — JWT

- Tokens JWT generados con `python-jose[cryptography]`.
- El middleware de autenticación valida firma y expiración en cada request protegido.
- [COMPLETAR: algoritmo de firma (HS256/RS256), tiempo de expiración, manejo de refresh tokens]

### 8.2 Autorización — RBAC

- Roles definidos en `models/role.py`: `ADMIN`, `TEAM_LEADER`, `DEVELOPER`.
- Cada endpoint restringe acciones según el rol del usuario autenticado.
- [COMPLETAR: matriz de permisos por rol y por recurso/endpoint]

### 8.3 Hashing de Contraseñas — bcrypt

- Contraseñas almacenadas con `bcrypt` (vía `passlib`), nunca en texto plano.
- [COMPLETAR: factor de costo configurado, política de complejidad de contraseñas]

### 8.4 Otras Consideraciones

- **CORS:** configurado en middleware backend. [COMPLETAR: orígenes permitidos en producción]
- **Validación de entrada:** Pydantic v2 en todos los schemas de request.
- **WebSocket:** autenticación del canal `/api/ws/{userId}` — [COMPLETAR: cómo se valida que el userId corresponde al usuario autenticado]
- **Manejo de archivos (`uploads.py`):** [COMPLETAR: validación de tipo/tamaño de archivo, escaneo de malware, almacenamiento seguro]
- **Variables de entorno / secretos:** [COMPLETAR: gestión de secretos en Railway/Vercel, uso de `.env`]
- **HTTPS/WSS:** [COMPLETAR: forzado en producción vía Vercel/Railway]

[COMPLETAR: resultados de auditorías de seguridad previas, dependencias con vulnerabilidades conocidas, política de rotación de secretos]

### 8.5 Hallazgos pendientes de auditoría (a resolver antes de producción real)

> ⚠️ Los valores concretos (contraseñas, hashes) **no se documentan aquí a propósito** — quedaron registrados solo como issue interno / conversación con el equipo, no en texto plano en el repo. Quien tome estos puntos debe generar credenciales nuevas, no reutilizar las que ya circularon.

- **Alta prioridad — Password temporal fija sin cambio forzado:** el flujo de alta de nuevos miembros de equipo (`team.addMember` en `frontend/src/services/api.ts`, que llama a `POST /auth/register`) crea la cuenta con una contraseña temporal **hardcodeada como string literal**, igual para todos los usuarios nuevos. No existe ningún campo en el modelo `User` (`must_change_password`, `is_temporary`, expiración, etc.) ni lógica en el backend que obligue a cambiarla en el primer login. Mientras no se corrija, cualquier cuenta recién creada es accesible por cualquiera que conozca ese valor fijo.
  **Fix propuesto:** generar una contraseña aleatoria por usuario (ej. `secrets.token_urlsafe()`) en el backend al registrar, agregar un flag `must_change_password: bool` en `User`, y bloquear el acceso a rutas protegidas hasta que la cambie.

- **Alta prioridad — Credenciales de producción hardcodeadas en scripts de seed:** `backend/scripts/seed_users.py` y `backend/app/scripts/fix_leader_password.py` tienen contraseñas en texto plano pensadas para correr contra la base de datos real (ver docstrings de ambos archivos). Deben rotarse en la base real y reescribirse para tomar el valor desde variable de entorno, nunca hardcodeado en el archivo versionado.

- **Media prioridad:** `backend/app/scripts/init_demo_users.py` imprime contraseñas en texto plano a stdout (quedarían en logs de CI/Railway); `create_users.sql` documenta en un comentario la contraseña en texto plano detrás de un hash bcrypt commiteado. Ambos deben limpiarse antes de reutilizar esos scripts.

[COMPLETAR: asignar responsable y fecha límite para cada punto antes de considerar el sistema listo para uso con datos reales]

---

## 9. Performance y Escalabilidad

### 9.1 Estado Actual

- **Backend asíncrono:** FastAPI + ARQ permiten procesar notificaciones sin bloquear el hilo principal de requests.
- **WebSocket por usuario:** conexión persistente `user:{id}:notifications`, evita polling constante.
- **Frontend reactivo:** Pinia + Vue 3 minimizan renders innecesarios; Vite optimiza el bundle (tree-shaking, code-splitting).

### 9.2 Puntos de Atención / Mejoras Futuras

[COMPLETAR:
- Estrategia de escalado horizontal del backend (¿múltiples instancias en Railway? ¿balanceo de carga?)
- Manejo de WebSockets con múltiples instancias de backend (¿sticky sessions? ¿Redis como broker compartido entre instancias?)
- Índices de base de datos y queries N+1 conocidas
- Estrategia de cache (qué se cachea en Redis además de pub/sub)
- Límites de rate limiting / throttling
- Monitoreo y observabilidad (logs, métricas, APM) — herramienta usada
- Pruebas de carga realizadas y resultados
]

---

## 10. Deployment

### 10.1 Frontend — Vercel

- Build con Vite (`npm run build`) → assets estáticos servidos por Vercel.
- Despliegue continuo desde rama [COMPLETAR: main/producción] en GitHub.
- [COMPLETAR: variables de entorno configuradas en Vercel, dominio, configuración de `vercel.json`]

### 10.2 Backend — Railway

- Despliegue del backend FastAPI (contenedor Docker, ver `Dockerfile` / `backend/Dockerfile`).
- Configuración en `railway.json`.
- [COMPLETAR: servicios adicionales en Railway (PostgreSQL, Redis), variables de entorno, health checks]

### 10.3 Entornos

| Entorno | Frontend | Backend | Base de Datos |
|---|---|---|---|
| Desarrollo local | Vite dev server | Uvicorn local / `docker-compose.yml` | PostgreSQL local (Docker) |
| Producción | Vercel | Railway | [COMPLETAR] |
| [COMPLETAR: Staging/QA] | [COMPLETAR] | [COMPLETAR] | [COMPLETAR] |

### 10.4 CI/CD

[COMPLETAR: pipeline de GitHub Actions (si existe) — pasos de lint, test, build, deploy automático a Vercel/Railway]

---

## 11. Anexos

- [COMPLETAR: diagrama entidad-relación (ERD) completo]
- [COMPLETAR: colección de Postman/Insomnia o link a documentación OpenAPI (`/docs` de FastAPI)]
- [COMPLETAR: glosario de términos del dominio (Épica, Ticket, Subtask, Workbench, Application, etc.)]
- [COMPLETAR: historial de decisiones arquitectónicas (ADRs) relevantes]

---

*Documento generado como base de arquitectura para CoreStream v1.0. Completar las secciones marcadas antes de presentar a stakeholders externos.*
