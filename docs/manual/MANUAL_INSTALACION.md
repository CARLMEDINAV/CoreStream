# CoreStream – Manual de instalación

Este manual permite instalar CoreStream en local o en un servidor, crear el primer administrador y mantenerlo. La instalación local con Docker se ha comprobado de principio a fin; el despliegue de producción y Kubernetes no.

Para el uso diario, consulta el [Manual de usuario](MANUAL_USUARIO.md).

## Contenido

1. [Arquitectura](#arquitectura)
2. [Requisitos](#requisitos)
3. [Configuración](#configuración)
4. [Instalación local](#instalación-local)
5. [Primer administrador y verificación](#primer-administrador-y-verificación)
6. [Producción](#producción)
7. [Operación](#operación)
8. [Resolución de problemas](#resolución-de-problemas)

## Arquitectura

CoreStream son tres contenedores (frontend, backend y worker) que dependen de PostgreSQL y Redis. En producción, un proxy externo reparte el tráfico.

```mermaid
flowchart TB
    Nav[Navegador<br/>Interfaz Vue 3] --> Proxy[Proxy externo<br/>HTTPS y WebSocket]
    Proxy -- resto de rutas --> FE[Frontend<br/>Nginx, puerto 8080]
    Proxy -- /api --> BE[Backend<br/>FastAPI, puerto 8010]
    BE --> PG[(PostgreSQL<br/>Datos y auditoría)]
    BE --> RD[(Redis<br/>Cola y tiempo real)]
    WK[Worker<br/>ARQ, segundo plano] --> PG
    WK --> RD
```

En desarrollo no hay proxy externo: Vite sirve la interfaz en 5173 y reenvía `/api` al backend.

## Requisitos

Con Docker solo hace falta Docker con Compose v2; lo demás se ejecuta en contenedores. En Windows, Docker Desktop necesita WSL (`wsl --install` como administrador y reiniciar).

| Componente | Versión | Desarrollo con Docker | Producción con Docker | Sin Docker |
| --- | --- | --- | --- | --- |
| Docker y Compose v2 | reciente | Sí | Sí | No |
| Git | cualquiera | Sí | Sí | Sí |
| PostgreSQL | 15 | Incluido | Externo | Instalado aparte |
| Redis | 7 | Incluido | Externo | Instalado aparte |
| Python | 3.11 | Incluido | Incluido | Sí |
| Node.js | 20 | Incluido | Incluido | Sí |

Los contenedores de producción están limitados a 2 CPU y 1 GB (backend), 1 CPU y 512 MB (worker) y 0,5 CPU y 256 MB (frontend). Elasticsearch, opcional, añade 1 CPU y 1,5 GB.

| Puerto | Servicio | Entorno |
| --- | --- | --- |
| 5173 | Frontend (Vite) | Desarrollo |
| 8000 | Backend | Desarrollo |
| 5432 y 6379 | PostgreSQL y Redis, solo en 127.0.0.1 | Desarrollo |
| 8080 | Frontend (Nginx) | Producción |
| 8010 | Backend | Producción |

El overlay de desarrollo también publica 8010 y 8080, aunque en ese modo se usan 8000 y 5173: los cuatro deben estar libres.

## Configuración

Con Docker, la configuración va en `.env` en la raíz del repositorio. `backend/.env` solo se usa sin Docker. Ninguno debe subirse a Git.

| Variable | Obligatoria en producción | Valor |
| --- | --- | --- |
| `DATABASE_URL` | Sí | `postgresql+asyncpg://usuario:clave@host:5432/corestream` |
| `REDIS_URL` | Sí | `redis://host:6379/5` |
| `SECRET_KEY` | Sí, 40 caracteres o más | Resultado de `openssl rand -hex 32` |
| `MFA_ENCRYPTION_KEY` | Sí, distinta de `SECRET_KEY` | `openssl rand -base64 32 \| tr '+/' '-_'` |
| `ENVIRONMENT` y `DEBUG` | Sí | `production` y `false` |
| `ALLOWED_ORIGINS` | Sí, sin `*` | `https://tu-dominio`, sin barra final |
| `FORWARDED_ALLOW_IPS` | Recomendada | IP o CIDR del proxy, nunca `*` |
| `BACKEND_PORT`, `FRONTEND_PORT` | No | 8010 y 8080 |
| `UVICORN_WORKERS` | No | 4; ajustar a los núcleos |
| `AUDIT_SINKS` | No | `database`; añadir `elastic` solo si hay Elasticsearch |
| `AUDIT_RETENTION_DAYS_BASICO`, `_PRO`, `_ENTERPRISE` | No | 30, 180 y 730 días (propuesta pendiente de confirmar por negocio) |
| `AZURE_TRANSLATOR_KEY`, `AZURE_TRANSLATOR_REGION` | No | Activan la traducción de documentos |
| `GOOGLE_*`, `MICROSOFT_*`, `SSO_PUBLIC_BASE_URL`, `SSO_FRONTEND_URL` | Solo con SSO | Con SSO, la URL pública del backend debe ser `https://` |
| `PLATFORM_ADMIN_IDS`, `PLATFORM_CLIENT_ID` | No | Habilitan la consola interna de planes |
| `VITE_API_BASE_URL` | No | Vacía. La CSP del frontend solo permite el mismo dominio |

En desarrollo con Docker no hace falta cambiar nada tras copiar `.env.example`. En producción, sustituye los valores de ejemplo de base de datos, Redis, dominio y claves.

## Instalación local

La vía recomendada es Docker: levanta PostgreSQL, Redis, backend, worker y frontend con un solo comando.

### Con Docker

1. Arranca Docker Desktop y clona el repositorio:

   ```bash
   git clone https://github.com/CARLMEDINAV/CoreStream.git
   cd CoreStream
   ```

2. Crea el `.env`. En PowerShell:

   ```powershell
   Copy-Item .env.example .env
   ```

   En Linux o macOS:

   ```bash
   cp .env.example .env
   ```

3. Levanta los servicios:

   ```bash
   docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build
   ```

4. Abre `http://localhost:5173`. La API está en `http://localhost:8000` y su documentación en `http://localhost:8000/api/docs`.

El backend aplica las migraciones al arrancar. Si una falla, el contenedor no arranca.

### Sin Docker

Requiere PostgreSQL 15 y Redis 7 en marcha. Los comandos son para PowerShell, desde la raíz del repositorio.

1. Crea la base de datos con `psql`, como superusuario:

   ```sql
   CREATE USER corestream WITH PASSWORD 'corestream';
   CREATE DATABASE corestream OWNER corestream;
   ```

2. Prepara el backend:

   ```powershell
   cd backend
   py -3.11 -m venv ..\.venv
   ..\.venv\Scripts\python.exe -m pip install -r requirements.txt
   Copy-Item .env.example .env
   ```

3. En `backend/.env`, cambia los hosts `postgres` y `redis` por `localhost`, y `UPLOAD_DIR` por una carpeta local con permiso de escritura.
4. Aplica las migraciones y arranca la API:

   ```powershell
   ..\.venv\Scripts\python.exe -m alembic upgrade head
   ..\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000 --reload
   ```

5. En otra terminal, dentro de `backend`, arranca el worker:

   ```powershell
   ..\.venv\Scripts\python.exe -m arq app.worker.settings.WorkerSettings
   ```

6. En una tercera terminal, dentro de `frontend`, arranca la interfaz:

   ```powershell
   npm ci
   $env:VITE_API_TARGET = 'http://localhost:8000'
   npm run dev
   ```

Sin `VITE_API_TARGET`, Vite busca el backend en `http://backend:8000`, que solo existe dentro de Docker.

## Primer administrador y verificación

No hay usuarios por defecto: el primer administrador de cada cliente se crea con un script. `--client-slug` es obligatorio, y `--client-name` también si el cliente aún no existe.

En producción:

```bash
docker compose exec backend python -m app.scripts.create_admin --email admin@empresa.com --full-name "Nombre Apellido" --client-slug empresa --client-name "Empresa"
```

En desarrollo, añade los dos ficheros de Compose (`docker compose -f docker-compose.yml -f docker-compose.dev.yml exec …`). Sin Docker, ejecuta `..\.venv\Scripts\python.exe -m app.scripts.create_admin …` desde `backend`.

Sin `--password`, el script genera una contraseña y la muestra una sola vez. No crea un segundo administrador en el mismo cliente. El resto de usuarios entra por invitación.

El correo debe tener un dominio real: el backend rechaza dominios reservados como `.local` o `.test`.

Comprueba la instalación:

- [ ] `docker compose ps` muestra los contenedores en `healthy`: 5 en desarrollo, 3 en producción
- [ ] `/api/health` responde `"status":"ok"` con base de datos y Redis correctos (puerto 8000 en desarrollo, 8010 en producción)
- [ ] La página de inicio de sesión carga y el administrador entra
- [ ] Al recargar la página la sesión se mantiene
- [ ] Se puede crear una aplicación, una épica y un ticket

## Producción

Producción usa solo `docker-compose.yml`, se conecta a PostgreSQL y Redis externos y necesita un proxy con HTTPS delante.

### Docker Compose

1. Crea un usuario y una base propios en PostgreSQL, con una clave fuerte:

   ```sql
   CREATE USER corestream WITH PASSWORD 'CLAVE-FUERTE';
   CREATE DATABASE corestream OWNER corestream;
   ```

2. Copia `.env.example` a `.env`, restringe su acceso (`chmod 600 .env`) y rellénalo según [Configuración](#configuración). Genera las claves con:

   ```bash
   openssl rand -hex 32                        # SECRET_KEY
   openssl rand -base64 32 | tr '+/' '-_'      # MFA_ENCRYPTION_KEY
   ```

3. Comprueba que `.env` contiene `MFA_ENCRYPTION_KEY` (Compose la pasa al backend y al worker) y valida la configuración:

   ```bash
   docker compose config -q
   ```

4. Levanta los servicios y comprueba su estado:

   ```bash
   docker compose up -d --build
   docker compose ps
   curl http://localhost:8010/api/health
   ```

5. Crea el primer administrador y configura el proxy.

### Proxy y HTTPS

El Nginx del contenedor frontend solo sirve la interfaz: no reenvía `/api`. El proxy externo debe enrutar ambos servicios en el mismo dominio. Las cookies de sesión son `Secure` en producción, por lo que hace falta HTTPS. Ejemplo para Nginx:

```nginx
server {
    listen 443 ssl;
    server_name tu-dominio;
    ssl_certificate     /ruta/fullchain.pem;
    ssl_certificate_key /ruta/privkey.pem;
    client_max_body_size 50m;

    location /api/ {
        proxy_pass http://127.0.0.1:8010;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 3600s;
    }
    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
    }
}
```

- No publiques `/metrics`.
- Impide el acceso externo directo a 8010 y 8080, que Compose publica en todas las interfaces.
- Fija `FORWARDED_ALLOW_IPS` a la dirección del proxy tal como la ve el contenedor; de ella dependen el límite de intentos y la IP de auditoría.

### Opciones

- **SSO:** registra en el proveedor la URL `https://tu-dominio/api/auth/sso/google/callback` (para Microsoft, `microsoft` en lugar de `google`). El SSO nunca crea cuentas. Usa el GUID de tu organización en `MICROSOFT_TENANT`.
- **Elasticsearch:** define `ELASTIC_PASSWORD`, `ELASTIC_URL=http://elasticsearch:9200` y `AUDIT_SINKS=database,elastic`, y arranca con `docker compose --profile elk up -d`.
- **Consola de planes:** obtén los UUID con `SELECT id, client_id FROM users WHERE email = '…'`, rellena `PLATFORM_CLIENT_ID` y `PLATFORM_ADMIN_IDS=["uuid"]`, y ejecuta de nuevo `docker compose up -d`.

### Kubernetes

Los manifiestos de `deploy/k8s` usan imágenes locales y un Ingress NGINX. El HPA escala el backend de 2 a 5 réplicas y requiere metrics-server. Para un clúster local con kind:

```bash
kind create cluster --config kind-config.yaml
docker build -t corestream-backend:local backend
docker build -t corestream-frontend:local frontend
kind load docker-image corestream-backend:local corestream-frontend:local
kubectl apply -f deploy/k8s/00-base.yaml
kubectl -n corestream create secret generic corestream-secrets \
  --from-literal=DATABASE_URL='postgresql+asyncpg://corestream:corestream@postgres:5432/corestream' \
  --from-literal=REDIS_URL='redis://redis:6379/0' \
  --from-literal=SECRET_KEY="$(openssl rand -hex 32)" \
  --from-literal=MFA_ENCRYPTION_KEY="$(openssl rand -base64 32 | tr '+/' '-_')"
kubectl apply -f deploy/k8s/dev-infra.yaml
kubectl -n corestream rollout status deploy/postgres
kubectl apply -f deploy/k8s/10-migrate-job.yaml
kubectl -n corestream wait --for=condition=complete job/corestream-migrate --timeout=180s
kubectl apply -f deploy/k8s/20-app.yaml
```

Instala antes ingress-nginx y metrics-server en el clúster. `dev-infra.yaml` es solo para pruebas. En un clúster real, usa un registro de imágenes, ajusta `ALLOWED_ORIGINS` y `FORWARDED_ALLOW_IPS` en el ConfigMap, añade TLS y cambia el volumen `ReadWriteOnce` si las réplicas caen en nodos distintos.

## Operación

Haz una copia antes de cada actualización y ensaya la restauración en una base limpia.

**Copia de seguridad.** Guarda la base y los archivos subidos en `./backups`, con 14 días de retención por defecto. Requiere `POSTGRES_PASSWORD`; `POSTGRES_CONTAINER` vale `db-postgre` salvo que lo cambies:

```bash
export POSTGRES_PASSWORD='…'
./backend/scripts/backup_db.sh
```

En cron, carga `POSTGRES_PASSWORD` desde un fichero protegido (ver `docs/DEPLOYMENT.md`): el script se detiene sin ella. Guarda `MFA_ENCRYPTION_KEY` aparte de las copias; si se pierde, hay que restablecer el 2FA de todos.

**Restauración.** Sobrescribe la base actual y pide escribir `RESTAURAR`. El segundo fichero, opcional, repone los archivos subidos:

```bash
./backend/scripts/restore_db.sh backups/corestream_FECHA.sql.gz backups/corestream_storage_FECHA.tar.gz
```

**Actualización.** Las migraciones se aplican al arrancar:

```bash
git pull
docker compose up -d --build
docker compose ps
```

No uses `docker compose down -v` en producción: borra los archivos subidos.

## Resolución de problemas

Empieza por `docker compose logs backend --tail 100`: los errores de configuración aparecen al arrancar.

| Síntoma | Causa | Solución |
| --- | --- | --- |
| `failed to connect to the docker API` | Docker no está en marcha | Arranca Docker Desktop |
| Docker Desktop no arranca en Windows | Falta WSL | `wsl --install` como administrador y reinicia |
| `MFA_ENCRYPTION_KEY inválida o ausente` | La clave no está en `.env` | Defínela y repite `docker compose up -d` |
| `SECRET_KEY inválida para producción` | Valor de ejemplo o menos de 40 caracteres | Genera otra con `openssl` |
| `DEBUG no puede ser True` | `DEBUG=true` en producción | Pon `DEBUG=false` |
| `No existe ningún cliente con slug` | Cliente nuevo sin nombre | Añade `--client-name` |
| `value is not a valid email address` | Dominio reservado (`.local`, `.test`) | Usa un dominio real |
| La sesión se pierde al recargar | Producción sin HTTPS | Configura TLS en el proxy |
| Error 404 o HTML en `/api` | El proxy envía `/api` al frontend | Enrútalo al puerto 8010 |
| No llegan avisos en tiempo real | El proxy no admite WebSocket | Revisa `Upgrade` y `proxy_read_timeout` |
| Error 413 al subir archivos | Límite del proxy | `client_max_body_size 50m` |
| Error al enviar auditoría a Elastic | `elastic` activo sin servicio | `AUDIT_SINKS=database` |
| Puerto ocupado | Otro proceso lo usa | Cambia `BACKEND_PORT` o `FRONTEND_PORT`; los de desarrollo son fijos |
| `/bin/sh^M` al ejecutar un script | Finales de línea CRLF de Windows | `sed -i 's/\r$//' backend/scripts/*.sh` |
