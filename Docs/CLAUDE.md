# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CoreStream is a project management platform (Jira-like) for managing applications, epics, tickets, and subtasks. It consists of a **FastAPI** backend and a **Vue 3** frontend with TypeScript, orchestrated via Docker Compose with PostgreSQL, Redis, and an async task worker.

## Development Setup

1. **Prerequisites**: Python 3.8+, Node.js 18+, Docker & Docker Compose
2. **Environment**: Copy `.env.example` files from `backend/` and `frontend/` to `.env` and customize values
3. **First Run**: From root, run `docker compose up --build` to spin up all services (Postgres, Redis, backend, frontend, worker)

## Commands

### Full Stack (from root)

```bash
# Start all services (backend, frontend, postgres, redis, worker)
docker compose up --build

# Stop all services
docker compose down

# Remove volumes (resets database)
docker compose down -v

# View logs for a service
docker compose logs -f backend    # or 'frontend', 'worker', 'postgres', 'redis'
```

### Backend (from backend/)

```bash
# Local dev (requires postgres/redis running separately)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Database migrations
alembic upgrade head              # Apply all pending migrations
alembic downgrade -1              # Rollback last migration
alembic revision --autogenerate -m "description"  # Generate new migration

# Tests
pytest                            # Run all tests
pytest tests/ -v                  # Verbose output
pytest tests/test_file.py::test_function  # Single test
```

### Frontend (from frontend/)

```bash
# Dev server (hot reload at http://localhost:5173)
npm run dev

# Production build
npm run build

# Type checking only
npm run type-check

# Preview production build
npm run preview
```

## Critical Git Workflow

1. **Always sync first**: Before starting work, run `git fetch && git merge main`
2. **Test locally**: Always run `docker compose up --build` before pushing — if it fails locally, it fails in CI
3. **Search before deleting**: Before removing any file, middleware, or dependency, search the entire project for usages — silent breakages have happened

## Architecture

### Backend (`backend/app/`)

**Core Files:**
- **`main.py`** — FastAPI app with lifespan manager; initializes Alembic migrations, seeds persistent users on startup
- **`config.py`** — Pydantic v2 settings loaded from `.env` (DATABASE_URL, REDIS_URL, JWT secrets, CORS config)
- **`database.py`** — SQLAlchemy 2 async engine with asyncpg driver; connection pool: 20 + 10 overflow
- **`redis_client.py`** — Async Redis client for pub/sub (WebSocket broadcasts) and caching

**Organization by Domain:**
- **`routers/`** — One file per domain: `auth`, `auth_simple`, `users`, `applications`, `epics`, `tickets`, `subtasks`, `analytics`, `documents`, `notifications`, `websocket`, `ticket_redirection`
- **`models/`** — SQLAlchemy ORM models (User, Role, Application, Epic, Ticket, Subtask, Document, Notification, TicketEvent)
- **`schemas/`** — Pydantic v2 request/response validation models
- **`services/`** — Business logic layers: `auth_service`, `ticket_state_machine`, `notification_service`, `analytics_service`, `ticket_redirection`, `timer_service`
- **`middleware/`** — JWT authentication (`auth.py`) and role-based access control (`rbac.py`)
- **`worker/`** — ARQ async task queue: `settings.py` (worker config), `tasks.py` (job definitions)

**Database & Async:**
- All DB access is **async-only** (no sync SQLAlchemy). Use `async with db()` pattern
- Migrations via Alembic only; never modify tables directly
- Sensitive operations (notifications, timers) enqueued to Redis via ARQ worker

### Frontend (`frontend/src/`)

- **`main.ts`** — App entry; registers Vue Router, Pinia (stores), vue-i18n (i18n)
- **`router/`** — Vue Router 4 with navigation guards, lazy-loaded routes, role-based redirects
- **`stores/`** — Pinia stores (auth, tickets, epics, applications, team, analytics, notifications, theme)
- **`views/`** — Page-level components (mounted by router): Dashboard, Constructor, Workbench, Analytics, etc.
- **`components/`** — Reusable UI components; `builder/` has Kanban board (EpicSwimlane, TicketCard, etc.)
- **`composables/`** — Composition functions: `useWebSocket.ts` (real-time), `useTimer.ts`, `useDragDrop.ts`, `useDragDropEpics.ts`
- **`services/`** — `api.ts` (Axios client with JWT interceptor, auto-refresh on 401), `exportService.ts` (PDF exports)
- **`types/`** — TypeScript interfaces (User, Ticket, Epic, Analytics, etc.) mirroring backend schemas
- **`i18n/`** — Translations: Spanish (`es`), English (`en`), plus German, French, Portuguese stubs

### Real-time Communication

**WebSocket + Redis Pub/Sub:**
- Endpoint: `WS /api/ws/notifications/{user_id}`
- Backend: Redis pub/sub broadcasts events (ticket assignments, status changes, redirections) to channels
- Frontend: `useWebSocket.ts` composable manages connection, auto-reconnect, message dispatch to Pinia stores

**Async Task Queue (ARQ Worker):**
- Notification persistence, timer operations, and long-running tasks are enqueued to Redis
- ARQ worker (`docker compose` service) consumes jobs from queue and executes `app.worker.tasks`
- Example: timer completion triggers worker job → persists to DB → publishes to Redis pub/sub → WebSocket broadcasts to clients

### REST API

- All routes prefixed with `/api`
- Vite dev server (port 5173) proxies `/api` → `http://localhost:8000/api`
- In production, configure reverse proxy (nginx, etc.) to route `/api` to backend container

### Role-Based Access Control (RBAC)

Three roles enforced in `middleware/rbac.py`:
- **`ADMIN`** — Full access to all operations
- **`GROUP_LEADER`** — Team management, ticket assignment, epic creation
- **`DEVELOPER`** — Assigned work only (view own tickets, update status, edit subtasks)

## Common Patterns

### Adding a New API Endpoint

1. Define Pydantic schemas in `backend/app/schemas/{domain}.py`
2. Create ORM model in `backend/app/models/{domain}.py` (if new table)
3. Write business logic in `backend/app/services/{domain}_service.py`
4. Add routes in `backend/app/routers/{domain}.py`
5. Generate migration: `alembic revision --autogenerate -m "description"`
6. Add TypeScript types in `frontend/src/types/index.ts` matching schemas
7. Implement Pinia store in `frontend/src/stores/{domain}.ts` for state management
8. Create Vue components in `frontend/src/components/` and wire to store

### Working with Async Database

All database operations are async. Pattern:

```python
from backend.app.database import get_db

async def some_endpoint(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).filter(User.id == 1))
    user = result.scalar_one_or_none()
```

### WebSocket & Real-time Events

Backend publishes to Redis channel, worker picks up, frontend listens:

```python
# Backend: enqueue notification job
await arq_queue.enqueue_job('send_notification', user_id, message)

# Worker (tasks.py): execute async job
async def send_notification(ctx, user_id, message):
    await db.add(Notification(...))
    await redis.publish(f'user:{user_id}', json.dumps({...}))

# Frontend (useWebSocket.ts): receive and dispatch to store
socket.on('message', (data) => {
  notificationStore.addNotification(data)
})
```

### Database Migrations

```bash
# After changing models, generate migration
cd backend && alembic revision --autogenerate -m "add_field_to_ticket"

# Review generated migration in backend/alembic/versions/
# Apply when ready
alembic upgrade head
```

## Important Notes

- **TypeScript Everywhere**: Frontend is fully typed; use `npm run type-check` before pushing
- **No Sync DB Access**: Never use sync SQLAlchemy — all access must be async (asyncpg)
- **Search Before Deleting**: Hidden dependencies across routers/services are common — grep the entire project
- **Docker Compose is Canonical**: Local `uvicorn` dev is faster but `docker compose up` is the true test environment
- **Alembic Only**: Never alter DB schema directly; always use migrations
- **Real-time Latency**: WebSocket broadcasts are near-instant; timer operations go through worker queue (slight delay expected)