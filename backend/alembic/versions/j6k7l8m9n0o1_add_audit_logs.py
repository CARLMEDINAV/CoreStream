"""crea el almacén de auditoría de no repudio (TRV-07).

El registro vive en su propio esquema `audit`, no en `public`: es lo que hace
literal el criterio "no se almacenan en las tablas operativas" sin depender de
ningún servicio externo. El esquema se puede otorgar y revocar por separado del
resto de la base.

Dos triggers lo protegen, y la diferencia entre ellos es deliberada:

  - UPDATE: prohibido siempre. Un registro de auditoría no se reescribe nunca.
  - DELETE: permitido solo si la sesión declara `corestream.audit_purge = on`,
    que fija únicamente la purga de retención de TRV-08. Así, caducar bajo una
    política publicada sigue siendo posible, pero un `DELETE FROM` suelto —
    desde psql o desde cualquier ruta inesperada de la aplicación, que comparte
    credenciales — queda bloqueado por la propia base de datos.

revision: j6k7l8m9n0o1
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "j6k7l8m9n0o1"
down_revision = "7e9ab80b3e68"
branch_labels = None
depends_on = None

SCHEMA = "audit"
TABLE = "audit_logs"
QUALIFIED = f"{SCHEMA}.{TABLE}"


def upgrade() -> None:
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")

    op.create_table(
        TABLE,
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        # Sin ForeignKey a clients: registro histórico, no dato relacional. Un
        # RESTRICT impediría borrar un cliente por tener auditoría; un CASCADE
        # borraría justo la prueba que no debe desaparecer.
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "occurred_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column("request_id", sa.String(64), nullable=True),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("actor_email", sa.String(255), nullable=True),
        sa.Column("actor_role", sa.String(50), nullable=True),
        sa.Column("method", sa.String(10), nullable=False),
        sa.Column("path", sa.String(512), nullable=False),
        sa.Column("route_template", sa.String(512), nullable=True),
        sa.Column("resource_type", sa.String(50), nullable=True),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status_code", sa.SmallInteger(), nullable=False),
        sa.Column("outcome", sa.String(20), nullable=False),
        sa.Column("ip", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(512), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        schema=SCHEMA,
    )

    for column in (
        "client_id", "occurred_at", "request_id", "actor_user_id",
        "actor_email", "route_template", "resource_type", "outcome",
    ):
        op.create_index(
            f"ix_{TABLE}_{column}", TABLE, [column], schema=SCHEMA
        )

    # El visor filtra por cliente y ordena por fecha descendente; la purga
    # filtra por cliente y fecha de corte. Mismo índice para los dos.
    op.create_index(
        f"ix_{TABLE}_client_occurred",
        TABLE,
        ["client_id", sa.text("occurred_at DESC")],
        schema=SCHEMA,
    )

    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION {SCHEMA}.no_update()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION '{QUALIFIED} es inmutable: UPDATE no permitido';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        f"""
        CREATE TRIGGER {TABLE}_immutable
        BEFORE UPDATE ON {QUALIFIED}
        FOR EACH ROW EXECUTE FUNCTION {SCHEMA}.no_update();
        """
    )

    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION {SCHEMA}.guard_delete()
        RETURNS trigger AS $$
        BEGIN
            IF current_setting('corestream.audit_purge', true) IS DISTINCT FROM 'on' THEN
                RAISE EXCEPTION
                    '{QUALIFIED}: DELETE permitido solo a la purga de retencion';
            END IF;
            RETURN OLD;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        f"""
        CREATE TRIGGER {TABLE}_guard_delete
        BEFORE DELETE ON {QUALIFIED}
        FOR EACH ROW EXECUTE FUNCTION {SCHEMA}.guard_delete();
        """
    )


def downgrade() -> None:
    op.execute(f"DROP TRIGGER IF EXISTS {TABLE}_guard_delete ON {QUALIFIED};")
    op.execute(f"DROP TRIGGER IF EXISTS {TABLE}_immutable ON {QUALIFIED};")
    op.execute(f"DROP FUNCTION IF EXISTS {SCHEMA}.guard_delete();")
    op.execute(f"DROP FUNCTION IF EXISTS {SCHEMA}.no_update();")
    op.drop_table(TABLE, schema=SCHEMA)
    op.execute(f"DROP SCHEMA IF EXISTS {SCHEMA}")
