# Tecnologías Utilizadas en CoreStream v1.0

> Documento de referencia técnica del stack tecnológico de CoreStream.
> Última actualización: [COMPLETAR: fecha]
> Autor(es): [COMPLETAR: nombre(s) del equipo]

---

## Tabla de Contenidos

1. [Stack General](#1-stack-general)
2. [Frontend](#2-frontend)
3. [Backend](#3-backend)
4. [Base de Datos](#4-base-de-datos)
5. [Cache y Mensajería](#5-cache-y-mensajería)
6. [Autenticación y Seguridad](#6-autenticación-y-seguridad)
7. [Testing](#7-testing)
8. [Hosting y Deployment](#8-hosting-y-deployment)
9. [Control de Versiones](#9-control-de-versiones)
10. [Herramientas de Desarrollo](#10-herramientas-de-desarrollo)
11. [Tabla Resumen General](#11-tabla-resumen-general)

---

## 1. Stack General

| Capa | Tecnología principal |
|---|---|
| **Frontend** | Vue 3 + TypeScript + Vite |
| **Backend** | FastAPI (Python) |
| **Base de Datos** | PostgreSQL |
| **Cache / Colas** | Redis + ARQ |
| **Deploy** | Vercel (frontend) + Railway (backend) |

---

## 2. Frontend

### 2.1 Núcleo

| Tecnología | Versión (package.json) | Propósito |
|---|---|---|
| Vue | ^3.4.0 | Framework de UI reactivo (Composition API) |
| Vite | ^6.0.0 | Bundler y dev server |
| TypeScript | ^5.0.0 | Tipado estático |
| vue-tsc | ^3.2.7 | Type-checking de componentes `.vue` |
| Pinia | ^2.0.0 | Gestión de estado global (stores) |
| vue-router | ^4.0.0 | Enrutamiento SPA |
| Axios | ^1.6.0 | Cliente HTTP hacia el backend |

### 2.2 Librerías Adicionales

| Librería | Versión | Propósito |
|---|---|---|
| @vueuse/core | ^10.0.0 | Composables utilitarios (reactive helpers) |
| vuedraggable | next | Drag & drop (usado en el Workbench / kanban) |
| vue-i18n | ^9.0.0 | Internacionalización (i18n) |
| chart.js / vue-chartjs | ^4.0.0 / ^5.0.0 | Gráficos y analíticas |
| apexcharts / vue3-apexcharts | ^5.12.0 / ^1.11.1 | Gráficos avanzados (dashboard de analytics) |
| jspdf | ^4.2.1 | Generación de PDFs en cliente |
| lucide-vue-next | ^1.0.0 | Íconos |
| @iconify/vue | ^5.0.0 | Íconos (set adicional) |
| canvas-confetti | ^1.9.0 | Efectos visuales (celebración/gamificación) |
| Tailwind CSS | ^3.3.0 | Framework de utilidades CSS |
| PostCSS + Autoprefixer | ^8.4.0 / ^10.4.0 | Procesamiento y compatibilidad CSS |

[COMPLETAR: justificación de uso de dos librerías de gráficos (chart.js y apexcharts) — ¿es intencional o hay migración en curso?]

### 2.3 Estructura de Estado y Lógica Reutilizable

- **Stores (Pinia):** `authStore`, `ticketsStore`, `notificationsStore`, [COMPLETAR: listar stores restantes].
- **Composables:** `useWebSocket`, `useDragDrop`, `useTimer`.
- **Directivas custom:** `directives/` — [COMPLETAR: detalle de directivas implementadas].

---

## 3. Backend

### 3.1 Núcleo

| Tecnología | Versión (requirements.txt) | Propósito |
|---|---|---|
| Python | [COMPLETAR: versión] | Lenguaje base del backend |
| FastAPI | [COMPLETAR: versión] | Framework web ASGI para la API REST |
| Uvicorn | [COMPLETAR: versión] (`uvicorn[standard]`) | Servidor ASGI |
| Pydantic | [COMPLETAR: versión] (`pydantic[email]`, v2) | Validación de datos y schemas (DTOs) |
| pydantic-settings | [COMPLETAR: versión] | Gestión de configuración vía variables de entorno |
| SQLAlchemy | [COMPLETAR: versión] | ORM para acceso a PostgreSQL |
| asyncpg | [COMPLETAR: versión] | Driver async de PostgreSQL |
| psycopg2-binary | 2.9.9 | Driver sync de PostgreSQL |
| Alembic | [COMPLETAR: versión] | Migraciones de base de datos versionadas |

### 3.2 Autenticación y Seguridad

| Tecnología | Versión | Propósito |
|---|---|---|
| python-jose[cryptography] | [COMPLETAR: versión] | Generación y validación de JWT |
| passlib[bcrypt] | 1.7.4 | Hashing de contraseñas |
| bcrypt | 4.0.1 | Algoritmo de hashing subyacente |
| python-multipart | [COMPLETAR: versión] | Parsing de form-data (uploads) |

### 3.3 Comunicación en Tiempo Real y Tareas Asíncronas

| Tecnología | Versión | Propósito |
|---|---|---|
| WebSocket (FastAPI nativo) | — | Canal `/api/ws/{userId}` para notificaciones en vivo |
| redis (cliente Python) | [COMPLETAR: versión] | Cliente pub/sub y conexión a Redis |
| arq | [COMPLETAR: versión] | Cola de tareas asíncronas (worker) |

### 3.4 Utilidades Adicionales

| Librería | Versión | Propósito |
|---|---|---|
| httpx | [COMPLETAR: versión] | Cliente HTTP async (usado por `translation_service` hacia Azure Translator) |
| PyPDF2 | [COMPLETAR: versión] | Extracción de texto de PDFs |
| python-docx | [COMPLETAR: versión] | Extracción de texto de documentos Word (traducción de documentos) |

[COMPLETAR: confirmar si el uso async es completo (asyncpg + SQLAlchemy async) o mixto con psycopg2 sync en algunos módulos]

---

## 4. Base de Datos — PostgreSQL

### 4.1 Características

- Motor: PostgreSQL [COMPLETAR: versión].
- Acceso vía SQLAlchemy ORM + driver `asyncpg`/`psycopg2-binary`.
- Migraciones versionadas con Alembic (`backend/alembic/`, `backend/migrations/`).
- [COMPLETAR: hosting de la instancia — ¿Railway managed Postgres, RDS, Supabase?]

### 4.2 Tablas / Entidades Principales

| Tabla | Descripción |
|---|---|
| `users` | Usuarios del sistema |
| `roles` | Roles de RBAC (`ADMIN`, `TEAM_LEADER`, `DEVELOPER`) |
| `tickets` | Tickets de trabajo |
| `ticket_events` | Historial/auditoría de cambios de estado de tickets |
| `epics` | Épicas que agrupan tickets |
| `subtasks` | Subtareas asociadas a tickets |
| `applications` | Aplicaciones/proyectos gestionados |
| `documents` | Documentos adjuntos/traducidos |
| `notifications` | Notificaciones persistidas por usuario |

[COMPLETAR: diagrama entidad-relación (ERD), claves foráneas e índices relevantes]

---

## 5. Cache y Mensajería — Redis

### 5.1 Usos

| Uso | Detalle |
|---|---|
| **Pub/Sub** | Canal `user:{id}:notifications`, publicado por el worker ARQ y consumido por `routers/websocket.py` |
| **Cola de tareas (ARQ)** | Backend de la cola para tareas asíncronas (`worker/tasks.py`) |
| **Cache** | [COMPLETAR: qué datos se cachean, TTLs configurados] |

### 5.2 Eventos de Notificación Publicados

- `TICKET_ASSIGNED`
- `TICKET_REDIRECTED`
- `QUESTION_RAISED`
- `TICKET_COMPLETED`
- `STATUS_CHANGED`

[COMPLETAR: versión de Redis, configuración de persistencia (RDB/AOF), si se usa Redis gestionado o self-hosted]

---

## 6. Autenticación y Seguridad

| Mecanismo | Tecnología | Detalle |
|---|---|---|
| Tokens de sesión | JWT (`python-jose[cryptography]`) | Firmado y validado en middleware backend |
| Hashing de contraseñas | bcrypt (vía `passlib`) | Nunca se almacenan contraseñas en texto plano |
| Autorización | RBAC (`models/role.py`) | Roles: `ADMIN`, `TEAM_LEADER`, `DEVELOPER` |
| CORS | Middleware FastAPI | [COMPLETAR: orígenes permitidos en producción] |

[COMPLETAR: algoritmo de firma JWT (HS256/RS256), tiempo de expiración de tokens, manejo de refresh tokens]

---

## 7. Testing

### 7.1 Frontend

| Herramienta | Versión | Propósito |
|---|---|---|
| Vitest | ^3.2.6 | Testing unitario (stores, composables) |
| @vitest/coverage-v8 | ^3.2.6 | Reporte de cobertura de código |
| @vue/test-utils | ^2.4.11 | Utilidades para testear componentes Vue |
| jsdom | ^26.1.0 | Entorno DOM simulado para tests |
| Cypress | ^10.11.0 | Testing end-to-end (e2e) |

Archivos de prueba identificados: `authStore.spec.ts`, `ticketsStore.spec.ts`, `useDragDrop.spec.ts`, `useTimer.spec.ts`.

### 7.2 Backend

| Herramienta | Versión | Propósito |
|---|---|---|
| pytest | [COMPLETAR: versión] | Framework de testing (`pytest.ini`, `testpaths = tests`) |
| pytest-asyncio (asyncio_mode = auto) | [COMPLETAR: versión] | Soporte para tests async |

[COMPLETAR: cobertura de tests actual (%), pipeline de CI que ejecuta los tests automáticamente]

---

## 8. Hosting y Deployment

| Servicio | Componente | Detalle |
|---|---|---|
| **Vercel** | Frontend (Vue SPA) | Build con Vite, despliegue continuo desde GitHub (`vercel.json`) |
| **Railway** | Backend (FastAPI) | Despliegue vía Docker (`Dockerfile`, `railway.json`) |
| **PostgreSQL / Redis** | Base de datos y cache | [COMPLETAR: gestionados en Railway o servicio externo] |

[COMPLETAR: dominios de producción, variables de entorno configuradas por entorno, estrategia de rollback]

---

## 9. Control de Versiones

| Herramienta | Uso |
|---|---|
| Git | Control de versiones local |
| GitHub | Repositorio remoto, Pull Requests, revisión de código, [COMPLETAR: GitHub Actions/CI-CD] |

[COMPLETAR: convención de nombres de ramas y commits utilizada por el equipo, estrategia de branching (GitFlow, trunk-based, etc.)]

---

## 10. Herramientas de Desarrollo

| Categoría | Herramienta | Notas |
|---|---|---|
| IDE recomendado | [COMPLETAR: ej. Visual Studio Code] | [COMPLETAR: extensiones recomendadas — Volar, Python, ESLint, etc.] |
| Linter (Frontend) | [COMPLETAR: no se detectó configuración de ESLint en el repo — definir si se adoptará] | — |
| Formatter (Frontend) | [COMPLETAR: no se detectó configuración de Prettier en el repo — definir si se adoptará] | — |
| Type-checking (Frontend) | vue-tsc (`npm run type-check`) | Verificación de tipos TypeScript en componentes `.vue` |
| Linter/Formatter (Backend) | [COMPLETAR: ej. ruff, flake8, black, isort — no se detectó configuración en el repo] | — |
| Contenerización | Docker + Docker Compose (`docker-compose.yml`, `Dockerfile`) | Entorno de desarrollo local |
| Gestor de paquetes (Frontend) | npm (`package-lock.json`) | — |
| Gestor de paquetes (Backend) | pip (`requirements.txt`, `requirements-dev.txt`) | — |

[COMPLETAR: definir e implementar linters/formatters estándar del equipo si aún no existen — recomendado: ESLint + Prettier en frontend, ruff/black en backend]

---

## 11. Tabla Resumen General

| Componente | Tecnología | Versión | Propósito |
|---|---|---|---|
| Frontend Framework | Vue | ^3.4.0 | UI reactiva basada en componentes |
| Build Tool | Vite | ^6.0.0 | Bundling y dev server |
| Lenguaje Frontend | TypeScript | ^5.0.0 | Tipado estático |
| Estado Global | Pinia | ^2.0.0 | Manejo de estado reactivo |
| Ruteo Frontend | vue-router | ^4.0.0 | Navegación SPA |
| Cliente HTTP | Axios | ^1.6.0 | Comunicación con la API REST |
| CSS Framework | Tailwind CSS | ^3.3.0 | Estilos utilitarios |
| Testing Unitario FE | Vitest | ^3.2.6 | Tests de stores/composables |
| Testing E2E | Cypress | ^10.11.0 | Tests end-to-end |
| Backend Framework | FastAPI | [COMPLETAR: versión] | API REST asíncrona |
| Lenguaje Backend | Python | [COMPLETAR: versión] | Lenguaje del backend |
| Servidor ASGI | Uvicorn | [COMPLETAR: versión] | Servidor de aplicación |
| Validación de Datos | Pydantic | [COMPLETAR: versión] (v2) | Schemas y validación de payloads |
| ORM | SQLAlchemy | [COMPLETAR: versión] | Mapeo objeto-relacional |
| Migraciones DB | Alembic | [COMPLETAR: versión] | Versionado de esquema de base de datos |
| Base de Datos | PostgreSQL | [COMPLETAR: versión] | Persistencia relacional |
| Cache / Pub-Sub | Redis | [COMPLETAR: versión] | Cache, pub/sub y backend de cola |
| Cola de Tareas | ARQ | [COMPLETAR: versión] | Procesamiento asíncrono de jobs |
| Autenticación | python-jose (JWT) | [COMPLETAR: versión] | Tokens de sesión |
| Hashing Contraseñas | bcrypt / passlib | 4.0.1 / 1.7.4 | Seguridad de credenciales |
| Testing Backend | pytest | [COMPLETAR: versión] | Tests unitarios/integración |
| Hosting Frontend | Vercel | — | Despliegue continuo del SPA |
| Hosting Backend | Railway | — | Despliegue continuo de la API |
| Control de Versiones | Git + GitHub | — | Versionado y colaboración |
| Contenerización | Docker | [COMPLETAR: versión] | Entorno reproducible local/deploy |

---

*Documento generado como referencia del stack tecnológico de CoreStream v1.0. Completar los campos de versión exacta antes de presentar a stakeholders externos.*
