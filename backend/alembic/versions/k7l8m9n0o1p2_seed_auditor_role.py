"""siembra el rol AUDITOR (TRV-07 / TRV-08)

Los dos requerimientos nombran a un "Auditor" o "equipo de cumplimiento" entre
los roles involucrados, pero el sistema solo tenía ADMIN, TEAM_LEADER y
DEVELOPER. Sin este rol, dar acceso al registro de auditoría obligaba a
conceder ADMIN — y un ADMIN puede invitar usuarios, cambiar roles y resetear
contraseñas, es decir, alterar el sistema que se le pide auditar.

Mismo criterio que a2b3c4d5e6f7: un rol es dato de referencia que el código
asume existente, así que lo crea una migración y no un script a mano.

revision: k7l8m9n0o1p2
"""
import uuid

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, insert as pg_insert

from alembic import op

revision = "k7l8m9n0o1p2"
down_revision = "j6k7l8m9n0o1"
branch_labels = None
depends_on = None

ROLES_TABLE = sa.table(
    "roles",
    sa.column("id", UUID(as_uuid=True)),
    sa.column("name", sa.String),
    sa.column("description", sa.String),
)

NOMBRE = "AUDITOR"
DESCRIPCION = "Auditor: solo lectura del registro de auditoría"


def upgrade() -> None:
    op.get_bind().execute(
        pg_insert(ROLES_TABLE)
        .values(id=uuid.uuid4(), name=NOMBRE, description=DESCRIPCION)
        .on_conflict_do_nothing(index_elements=["name"])
    )


def downgrade() -> None:
    # Solo se borra si nadie lo tiene asignado: con usuarios referenciándolo,
    # el DELETE fallaría por la FK de users.role_id (ondelete RESTRICT).
    op.execute(
        """
        DELETE FROM roles
        WHERE name = 'AUDITOR'
          AND NOT EXISTS (SELECT 1 FROM users WHERE users.role_id = roles.id)
        """
    )
