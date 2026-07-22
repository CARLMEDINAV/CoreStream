# Guía de Instalación de CoreStream

Esta guía explica cómo ejecutar el proyecto CoreStream de manera local.

## Requisitos Previos

- **Docker y Docker Compose** (Recomendado para una instalación sencilla)
- **Node.js 20+** (Si se ejecuta el frontend manualmente)
- **Python 3.11** (Si se ejecuta el backend manualmente)
- **PostgreSQL 15 y Redis 7** (Si se ejecuta el backend manualmente)

---

## 🐳 Inicio Rápido (Docker)

El repositorio incluye un `docker-compose.yml` que orquesta todo el stack (PostgreSQL, Redis, Backend, Frontend y Worker).

1. Copia las variables de entorno:
```bash
cp backend/.env.example .env
```
*(El archivo `docker-compose.yml` lee el `.env` desde el directorio raíz).*

2. Inicia los servicios:
```bash
docker-compose up -d
```

El backend ejecutará automáticamente las migraciones de la base de datos al iniciar.

**URLs de Acceso:**
- Frontend: [http://localhost:5173](http://localhost:5173)
- Docs de la API Backend: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 🔧 Instalación Manual

### 1. Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
# Edita .env para configurar DATABASE_URL y REDIS_URL

# Aplica las migraciones de base de datos
alembic upgrade head

# Inicia el servidor
uvicorn app.main:app --reload --port 8000
```

### 2. Frontend

```bash
cd frontend
npm install

cp .env.example .env.local
# Verifica VITE_API_BASE_URL y VITE_BACKEND_URL

# Inicia el servidor de desarrollo
npm run dev
```

---

## 👤 Usuarios de Prueba

Para llenar la base de datos con usuarios de prueba iniciales (Admin, Team Leader, Developer):

```bash
# Asegúrate de que el entorno del backend esté ejecutándose/activado
RUN_SEED=true python -m app.scripts.seed_persistent_users
```
