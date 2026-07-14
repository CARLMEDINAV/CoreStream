# 🚀 CoreStream v1.0

**Plataforma de gestión de proyectos y tickets** para equipos de desarrollo — combina un tablero tipo kanban (Workbench), un constructor de épicas/tickets para líderes técnicos (Builder), notificaciones en tiempo real vía WebSocket, y un módulo de analíticas de desempeño por desarrollador.

CoreStream está pensado para equipos pequeños/medianos con roles diferenciados: un **Team Leader** que arma épicas y asigna trabajo, **Developers** que ejecutan tickets desde su Workbench (con cronómetro de tiempo trabajado/bloqueado), y un flujo de **tickets de soporte** independiente para reportar y resolver bugs de producción. El sistema registra cada transición de estado como evento auditable, lo que alimenta el módulo de Analytics (eficiencia, índice de bloqueo, índice de rotación) sin necesitar integraciones externas.

Backend en **FastAPI** (async, PostgreSQL + Redis), frontend en **Vue 3** (Composition API + Pinia), desplegado en Railway y Vercel respectivamente.

---

## 📑 Tabla de Contenidos

1. [Requisitos previos](#-requisitos-previos)
2. [Estructura del repositorio](#-estructura-del-repositorio)
3. [Instalación rápida con Docker](#-instalación-rápida-con-docker)
4. [Instalación manual](#-instalación-manual-sin-docker)
5. [Configuración de variables de entorno](#-configuración-de-variables-de-entorno)
6. [Usuarios de prueba](#-usuarios-de-prueba)
7. [Comandos principales](#-comandos-principales)
8. [Documentación](#-documentación)
9. [Deployment](#-deployment)
10. [Testing](#-testing)
11. [Troubleshooting](#-troubleshooting)
12. [Contribuir](#-contribuir)

---

## ⚙️ Requisitos previos

| Software | Versión | Notas |
|---|---|---|
| **Python** | 3.11 | Fijado en `backend/Dockerfile` (`python:3.11-slim`) |
| **Node.js** | ≥ 20 | Recomendado para Vite 6 (no hay `.nvmrc`/`engines` en el repo — usar la LTS activa) |
| **PostgreSQL** | 15 | Versión usada en `docker-compose.yml` (`postgres:15`) |
| **Redis** | 7 (alpine) | Pub/Sub de notificaciones + cola de tareas ARQ |
| **Docker + Docker Compose** | opcional pero recomendado | Levanta los 4 servicios con un comando |

---

## 📁 Estructura del repositorio

```
CoreStream/
├── backend/
│   ├── app/
│   │   ├── routers/          # Endpoints REST + WebSocket (auth, tickets, epics, analytics...)
│   │   ├── models/            # Entidades SQLAlchemy (User, Ticket, Epic, TicketEvent...)
│   │   ├── schemas/           # DTOs Pydantic v2
│   │   ├── services/          # Lógica de negocio (analytics, state machine, notifications)
│   │   ├── middleware/        # Auth JWT, RBAC
│   │   ├── worker/            # Worker ARQ (notificaciones async)
│   │   ├── scripts/           # Scripts de seed/mantenimiento
│   │   ├── config.py
│   │   ├── database.py
│   │   └── main.py            # Entry point FastAPI
│   ├── alembic/                # Migraciones de base de datos
│   ├── tests/                  # pytest (analytics, RBAC, tickets, state machine...)
│   ├── scripts/                # Seed de usuarios de producción
│   ├── requirements.txt
│   ├── .env.example
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/         # Componentes por dominio (workbench, support, analytics...)
│   │   ├── views/               # Vistas por rol (dev/, admin/, shared/)
│   │   ├── stores/               # Pinia (auth, tickets, analytics, supportTickets...)
│   │   ├── composables/          # useTimer, useTicketTimer, useWebSocket, useDragDrop
│   │   ├── services/              # Cliente Axios (api.ts) + mockApi (modo prototipo)
│   │   ├── i18n/                   # es, en, de, fr, pt
│   │   └── App.vue
│   ├── cypress/                 # Tests e2e
│   ├── package.json
│   ├── vite.config.ts
│   └── .env.example
├── Docs/                        # Guías internas del equipo
├── docker-compose.yml            # postgres + redis + backend + frontend + worker
├── railway.json                   # Config de deploy en Railway
├── ARQUITECTURA.md
├── TECNOLOGIAS.md
└── README.md
```

---

## 🐳 Instalación rápida con Docker

`docker-compose.yml` orquesta **5 servicios**: `postgres` (15), `redis` (7-alpine), `backend` (FastAPI + Uvicorn con reload), `frontend` (Vite dev server) y `worker` (ARQ, procesa notificaciones).

```bash
# 1. Copiar variables de entorno (usadas por backend, frontend y worker vía env_file)
cp backend/.env.example .env

# 2. Levantar todo
docker-compose up -d

# El backend corre migraciones automáticamente (alembic upgrade head) antes de iniciar
```

**URLs resultantes:**
- Backend (API + docs): **http://localhost:8000** — Swagger UI en `/docs`
- Frontend: **http://localhost:5173**
- PostgreSQL: `localhost:5432` (`corestream`/`corestream`/`corestream`)
- Redis: `localhost:6379`

> El `frontend` en Docker corre `npm run dev -- --host 0.0.0.0` con hot-reload sobre el código montado como volumen.

---

## 🔧 Instalación manual (sin Docker)

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env            # Configurar DATABASE_URL, REDIS_URL, SECRET_KEY

alembic upgrade head            # Aplicar migraciones

uvicorn app.main:app --reload --port 8000
```

Necesitás PostgreSQL y Redis corriendo localmente (o vía `docker-compose up postgres redis`).

### Frontend

```bash
cd frontend
npm install

cp .env.example .env.local       # Configurar VITE_BACKEND_URL, etc.

npm run dev
```

Por defecto Vite sirve en el puerto **5173** y usa `/api` como proxy hacia el backend (configurable con `VITE_API_BASE_URL`).

---

## 🔐 Configuración de variables de entorno

### `backend/.env`

| Variable | Ejemplo | Descripción |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://corestream:corestream@localhost:5432/corestream` | Conexión async a PostgreSQL |
| `REDIS_URL` | `redis://localhost:6379/0` | Pub/Sub + cola ARQ |
| `SECRET_KEY` | *(generar con `openssl rand -hex 32`)* | Firma de JWT — **nunca reusar el placeholder en producción** |
| `ALGORITHM` | `HS256` | Algoritmo de firma JWT |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Expiración del access token |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Expiración del refresh token |
| `ALLOWED_ORIGINS` | `http://localhost:5173` | CORS |
| `ENVIRONMENT` | `development` \| `production` | En Railway: `production` |
| `DEBUG` | `True` \| `False` | Desactivar en producción |
| `LOG_LEVEL` | `info` | `debug`/`info`/`warning`/`error`/`critical` |

### `frontend/.env.local`

| Variable | Ejemplo | Descripción |
|---|---|---|
| `VITE_PORT` | `5173` | Puerto del dev server |
| `VITE_API_BASE_URL` | `/api` | Base de las requests HTTP (proxy en dev) |
| `VITE_BACKEND_URL` | `http://localhost:8000` | URL directa del backend en desarrollo |
| `VITE_MODO_PROTOTIPO` | `false` | Si es `true`, usa `mockApi` + `localStorage`, sin backend real |
| `VITE_ANALYTICS_ENABLED` | `true` | Habilita el módulo de Analytics en el UI |
| `VITE_LOG_LEVEL` / `VITE_DEBUG_API` | `info` / `false` | Verbosidad de logs en consola |

Ambos `.env.example` están commiteados con placeholders — cópialos, nunca edites el `.example` directamente.

---

## 👤 Usuarios de prueba

El repo incluye scripts de seed para crear usuarios con cada rol (`ADMIN`, `TEAM_LEADER`, `DEVELOPER`):

```bash
# Opción recomendada para desarrollo local: usuarios ficticios @example.com,
# solo se ejecuta si RUN_SEED=true (evita contaminar producción por accidente)
RUN_SEED=true python -m app.scripts.seed_persistent_users
```

> ⚠️ **Nota de seguridad:** existe además `backend/scripts/seed_users.py`, pensado para correr una única vez tras el primer deploy en Railway. **No reproduzco aquí sus contraseñas** porque en la auditoría de este repo se detectó que quedaron hardcodeadas en el archivo (incluyendo cuentas con dominio de producción). Si vas a usar ese script, generá contraseñas nuevas antes de ejecutarlo y rotá las que ya estén en uso en la base real.

Los roles disponibles y sus permisos están definidos en `backend/app/models/role.py` (`ADMIN`, `TEAM_LEADER`, `DEVELOPER`).

---

## 🛠️ Comandos principales

### Frontend (`cd frontend`)

| Comando | Descripción |
|---|---|
| `npm run dev` | Dev server (Vite, puerto 5173) |
| `npm run build` | Build de producción |
| `npm run preview` | Sirve el build de producción localmente |
| `npm run type-check` | Type-check con `vue-tsc --noEmit` |
| `npm run test:unit` | Tests unitarios (Vitest) |
| `npm run test:e2e` | Tests e2e headless (Cypress) |
| `npm run test:e2e:open` | Abre la UI de Cypress |

### Backend (`cd backend`)

| Comando | Descripción |
|---|---|
| `uvicorn app.main:app --reload` | Servidor de desarrollo con hot-reload |
| `alembic upgrade head` | Aplica migraciones pendientes |
| `alembic revision --autogenerate -m "mensaje"` | Genera una nueva migración |
| `pytest` | Corre la suite completa (`tests/`, config en `pytest.ini`) |
| `pytest tests/test_analytics.py -v` | Corre un archivo de tests específico |

---

## 📚 Documentación

- [ARQUITECTURA.md](./ARQUITECTURA.md) — Diagrama de flujo, patrones de diseño, flujos principales
- [TECNOLOGIAS.md](./TECNOLOGIAS.md) — Stack completo con versiones
- **API interactiva:** `http://localhost:8000/docs` (Swagger UI, autogenerado por FastAPI)
- [Docs/GUIA_RAPIDA_DEVELOPERS.md](./Docs/GUIA_RAPIDA_DEVELOPERS.md) — Guía rápida para developers

---

## ☁️ Deployment

| Componente | Servicio | Configuración |
|---|---|---|
| **Frontend** | [Vercel](https://vercel.com) | Build con Vite, deploy continuo desde la rama principal |
| **Backend** | [Railway](https://railway.app) | `railway.json` → build con `Dockerfile`, `startCommand: bash scripts/start.sh`, healthcheck en `/health` |
| **PostgreSQL / Redis** | Railway (managed) | Ver variables `DATABASE_URL` / `REDIS_URL` inyectadas por Railway |

El endpoint `GET /health` (`backend/app/main.py`) es el healthcheck que usa Railway para verificar que el deploy esté sano.

---

## 🧪 Testing

| Capa | Herramienta | Cobertura actual |
|---|---|---|
| **Backend** | `pytest` (+ `asyncio_mode = auto`) | `test_analytics.py`, `test_rbac.py`, `test_state_machine.py`, `test_support_tickets.py`, `test_tickets.py`, `test_validations.py` — DB SQLite en memoria, sin dependencias externas |
| **Frontend unitario** | `Vitest` + `@vue/test-utils` | Stores (`authStore`, `ticketsStore`) y composables (`useDragDrop`, `useTimer`) |
| **Frontend e2e** | `Cypress` | `frontend/cypress/e2e/` |

```bash
# Backend
cd backend && pytest -v

# Frontend
cd frontend && npm run test:unit
cd frontend && npm run test:e2e
```

---

## 🩹 Troubleshooting

**`docker-compose up` falla al levantar el backend**
Confirmá que copiaste `.env` en la raíz (no solo `backend/.env`) — el `docker-compose.yml` usa `env_file: .env` para `backend`, `frontend` y `worker`.

**El frontend no recibe datos del backend / CORS error**
Revisá que `ALLOWED_ORIGINS` en `backend/.env` incluya el origen exacto del frontend (`http://localhost:5173`), y que `VITE_BACKEND_URL`/`VITE_API_BASE_URL` apunten al backend correcto.

**Las notificaciones en tiempo real no llegan**
El flujo depende de Redis + el worker ARQ corriendo (`docker-compose up worker` o `python -m arq app.worker.settings.WorkerSettings`). Sin el worker, los eventos se encolan en Redis pero nunca se publican al WebSocket.

**`alembic upgrade head` falla**
Verificá que `DATABASE_URL` use el driver correcto según el contexto: `postgresql+asyncpg://` para la app (async), `postgresql://` para scripts que usan `psycopg2` (sync) — varios scripts de `backend/app/scripts/` hacen esta conversión automáticamente.

**El cronómetro de un ticket no se pausa/reanuda como esperado**
La lógica vive en `frontend/src/composables/useTicketTimer.ts`, que sincroniza con `ticket.status`. Verificá que el estado que llega sea uno de los que el composable reconoce (`IN_PROGRESS`, `BLOCKED`, `BLOCKED_QUESTION`, `COMPLETED`).

---

## 🤝 Contribuir

**Flujo de trabajo del equipo** (aprendido a la fuerza — no lo salteen):

1. **Sincronizá antes de picar código:** `git fetch` + `git merge` (o `pull`) sobre la rama de desarrollo antes de empezar. Trabajar sobre una rama desactualizada ya causó pérdida de un esquema/requerimiento porque no todos estaban sincronizados.
2. **Probá localmente antes de pushear:** corré `docker-compose up --build` antes de todo `git push`. Si no te levanta el backend a vos, no le va a levantar a nadie más — no subas cambios que rompan el arranque del servidor.
3. **Cuidado al borrar "código no usado":** antes de eliminar un archivo o requerimiento porque "parece" no usarse, hacé un *search* en todo el proyecto — puede ser una dependencia de otro router que no es obvia a simple vista.

**Convenciones:**
- Commits en español, estilo `tipo: descripción breve` (`fix:`, `feat:`, `chore:`, `docs:`) — ver `git log` para el patrón real usado en el repo.
- Ramas por feature: `feature/nombre-descriptivo`.
- Nunca commitear `.env` ni contraseñas reales en scripts de seed — usar variables de entorno.
