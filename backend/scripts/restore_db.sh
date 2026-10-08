#!/bin/sh
# =====================================================================
# Restauración de un backup de PostgreSQL para CoreStream (plan fase 7.3).
#
# Uso:
#   POSTGRES_PASSWORD=... ./backend/scripts/restore_db.sh backups/corestream_20260101_030000.sql.gz
#
# ADVERTENCIA: esto SOBRESCRIBE la base de datos "corestream" en la
# instancia de Postgres compartida de la VM (contenedor db-postgre, no un
# contenedor propio de este proyecto). Pensado para:
#   - el ensayo de restauración (ver docs/DEPLOYMENT.md)
#   - una recuperación real ante desastre
# No lo ejecutes contra producción sin confirmar que es lo que quieres.
# =====================================================================
set -eu

POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-db-postgre}"
POSTGRES_DB="${POSTGRES_DB:-corestream}"
POSTGRES_USER="${POSTGRES_USER:-corestream}"
: "${POSTGRES_PASSWORD:?Falta POSTGRES_PASSWORD}"

DUMP_FILE="${1:?Uso: restore_db.sh <ruta-al-dump.sql.gz>}"

if [ ! -f "$DUMP_FILE" ]; then
    echo "No existe el fichero: $DUMP_FILE" >&2
    exit 1
fi

echo "Restaurando $DUMP_FILE — esto sobrescribe la base de datos actual."

# backup_db.sh genera dos dumps: el operativo lleva -N audit y el de auditoría
# -n audit. Restaurar el operativo NO toca el rastro, porque el esquema audit
# no está en el fichero y --clean solo dropea lo que el dump contiene.
case "$(basename "$DUMP_FILE")" in
    corestream_audit_*)
        echo
        echo "ATENCIÓN: este es el dump de AUDITORÍA (esquema audit)."
        echo "Restaurarlo retrocede el registro de no repudio al estado de ese"
        echo "backup: todo evento posterior se pierde. Solo tiene sentido en una"
        echo "recuperación ante desastre, nunca para arreglar datos operativos."
        ;;
    *)
        echo
        echo "Dump operativo: el esquema audit NO se toca."
        echo "Si este backup se generó antes de que la auditoría se separara, sí"
        echo "lo incluye y lo retrocedería — compruébalo con:"
        echo "  gunzip -c \"$DUMP_FILE\" | pg_restore -l | grep -i ' audit'"
        ;;
esac

echo
printf "Escribe RESTAURAR para confirmar: "
read -r CONFIRMACION
if [ "$CONFIRMACION" != "RESTAURAR" ]; then
    echo "Cancelado."
    exit 1
fi

# --clean --if-exists: dropea los objetos existentes antes de recrearlos,
# para que la restauración sea idempotente incluso si la BD no está vacía.
gunzip -c "$DUMP_FILE" | docker exec -i -e PGPASSWORD="$POSTGRES_PASSWORD" "$POSTGRES_CONTAINER" \
    pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner

echo "Restauración completa."
