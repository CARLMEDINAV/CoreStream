#!/bin/sh
# =====================================================================
# Backup de PostgreSQL para CoreStream (plan fase 7.3).
#
# Uso en la VM (Postgres es el compartido de la máquina, no hace falta
# tener el compose de CoreStream levantado para esta parte del backup):
#   POSTGRES_PASSWORD=... ./backend/scripts/backup_db.sh
#
# Variables de entorno:
#   POSTGRES_PASSWORD  Obligatoria — la del usuario "corestream" creado en
#                      la instancia compartida (ver docs/DEPLOYMENT.md).
#   POSTGRES_CONTAINER Nombre del contenedor de Postgres (default: db-postgre)
#   POSTGRES_DB        (default: corestream)
#   POSTGRES_USER      (default: corestream)
#   BACKUP_DIR         Directorio destino (default: ./backups)
#   RETENTION_DAYS     Días que se conservan los backups operativos (default: 14)
#   AUDIT_RETENTION_DAYS  Días que se conservan los de auditoría (default: 730,
#                      la retención del plan Enterprise)
#
# Genera DOS dumps de SQL: el operativo (sin el esquema `audit`) y el de
# auditoría (solo ese esquema). Ver el comentario junto a pg_dump.
#
# Pensado para un cron diario en la VM, por ejemplo:
#   0 3 * * * cd /ruta/a/Corestream && ./backend/scripts/backup_db.sh >> /var/log/corestream-backup.log 2>&1
# =====================================================================
set -eu

BACKUP_DIR="${BACKUP_DIR:-./backups}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
AUDIT_RETENTION_DAYS="${AUDIT_RETENTION_DAYS:-730}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
FILENAME="corestream_${TIMESTAMP}.sql.gz"
AUDIT_FILENAME="corestream_audit_${TIMESTAMP}.sql.gz"

mkdir -p "$BACKUP_DIR"

echo "CoreStream — backup de PostgreSQL ($TIMESTAMP)"

# Postgres no es un contenedor propio de CoreStream (plan de despliegue):
# corre compartido en esta VM como "db-postgre", así que pg_dump se ejecuta
# ahí directo con `docker exec`, no `docker compose exec` (ese contenedor
# no es parte de este proyecto de compose). POSTGRES_CONTAINER/DB/USER se
# leen del entorno para no hardcodear nombres que puedan cambiar.
POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-db-postgre}"
POSTGRES_DB="${POSTGRES_DB:-corestream}"
POSTGRES_USER="${POSTGRES_USER:-corestream}"

: "${POSTGRES_PASSWORD:?Falta POSTGRES_PASSWORD}"

# Dos dumps separados, no uno (TRV-07). El esquema `audit` se excluye del
# volcado operativo con -N: si los dos vinieran en el mismo fichero, restaurar
# un backup para arreglar un problema de datos retrocedería también la
# auditoría al estado de ese backup — exactamente lo que el criterio de no
# repudio quiere evitar. Separados, se puede restaurar lo operativo sin tocar
# el rastro, que solo avanza.
docker exec -e PGPASSWORD="$POSTGRES_PASSWORD" "$POSTGRES_CONTAINER" \
    pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom -N audit \
    | gzip > "$BACKUP_DIR/$FILENAME"

SIZE=$(du -h "$BACKUP_DIR/$FILENAME" | cut -f1)
echo "Backup operativo guardado: $BACKUP_DIR/$FILENAME ($SIZE) — sin el esquema audit"

docker exec -e PGPASSWORD="$POSTGRES_PASSWORD" "$POSTGRES_CONTAINER" \
    pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom -n audit \
    | gzip > "$BACKUP_DIR/$AUDIT_FILENAME"

AUDIT_SIZE=$(du -h "$BACKUP_DIR/$AUDIT_FILENAME" | cut -f1)
echo "Backup de auditoría guardado: $BACKUP_DIR/$AUDIT_FILENAME ($AUDIT_SIZE)"

# Además del volumen de Postgres, los documentos/adjuntos subidos viven en
# el volumen storage-data — se respaldan aparte porque no son SQL.
DOCS_FILENAME="corestream_storage_${TIMESTAMP}.tar.gz"
docker run --rm \
    -v corestream_storage-data:/data:ro \
    -v "$(cd "$BACKUP_DIR" && pwd)":/backup \
    alpine tar czf "/backup/$DOCS_FILENAME" -C /data .
echo "Backup de storage guardado: $BACKUP_DIR/$DOCS_FILENAME"

# Rotación: borra backups (BD y storage) más viejos que RETENTION_DAYS.
# El patrón excluye los de auditoría con ! -name, porque esos tienen su propia
# retención: 14 días de backups operativos es razonable, pero tirar el backup
# de auditoría antes de que caduque la retención del plan más largo (730 días
# en Enterprise) dejaría el rastro sin copia durante su periodo de validez.
find "$BACKUP_DIR" -name 'corestream_*.sql.gz' ! -name 'corestream_audit_*.sql.gz' \
    -mtime "+${RETENTION_DAYS}" -delete
find "$BACKUP_DIR" -name 'corestream_storage_*.tar.gz' -mtime "+${RETENTION_DAYS}" -delete
find "$BACKUP_DIR" -name 'corestream_audit_*.sql.gz' \
    -mtime "+${AUDIT_RETENTION_DAYS}" -delete

echo "Retención: ${RETENTION_DAYS} días (operativo y storage), ${AUDIT_RETENTION_DAYS} días (auditoría)."
