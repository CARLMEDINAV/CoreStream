"""completa el flujo de incidencias y valida los enlaces de notificaciones."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "k7l8m9n0o1p2"
down_revision = "j6k7l8m9n0o1"
branch_labels = None
depends_on = None

condicion = (
    "(type IN ('INCIDENT_REPORTED', 'INCIDENT_ASSIGNED') AND incident_id IS NOT NULL AND ticket_id IS NULL) OR "
    "(type IN ('TICKET_ASSIGNED', 'STATUS_CHANGED', 'TICKET_REDIRECTED', 'TICKET_COMPLETED', 'QUESTION_RAISED') "
    "AND ticket_id IS NOT NULL AND incident_id IS NULL) OR "
    "(type = 'SYSTEM' AND (ticket_id IS NULL OR incident_id IS NULL))"
)


def cambiar_borrado(accion):
    for clave in sa.inspect(op.get_bind()).get_foreign_keys("notifications"):
        if clave["constrained_columns"] in (["ticket_id"], ["incident_id"]):
            op.drop_constraint(clave["name"], "notifications", type_="foreignkey")
            op.create_foreign_key(
                clave["name"], "notifications", clave["referred_table"],
                clave["constrained_columns"], clave["referred_columns"], ondelete=accion,
            )


def upgrade():
    with op.get_context().autocommit_block():
        for estado in ("ASSIGNED", "IN_REVIEW", "CLOSED", "REOPENED"):
            op.execute(f"ALTER TYPE incident_status_enum ADD VALUE IF NOT EXISTS '{estado}'")
    op.add_column("incidents", sa.Column("categoria", sa.String(50), server_default="general", nullable=False))
    op.create_table(
        "eventos_incidencia",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clients.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("autor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("autor_nombre", sa.String(255), nullable=False),
        sa.Column("tipo", sa.String(30), nullable=False),
        sa.Column("estado_anterior", sa.String(30)),
        sa.Column("estado_nuevo", sa.String(30)),
        sa.Column("comentario", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_eventos_incidencia_client_id", "eventos_incidencia", ["client_id"])
    op.create_index("ix_eventos_incidencia_incident_id", "eventos_incidencia", ["incident_id"])
    # conserva el estado previo sin inventar un historial que no existia.
    op.execute("""
        INSERT INTO eventos_incidencia
            (id, client_id, incident_id, autor_nombre, tipo, estado_nuevo, comentario)
        SELECT gen_random_uuid(), client_id, id, 'sistema', 'importacion', status::text,
            'Estado existente al habilitar el historial'
        FROM incidents
    """)
    # conserva el texto de avisos antiguos cuyo recurso ya no existe o no coincide.
    op.execute("""
        UPDATE notifications SET
            ticket_id = CASE WHEN type IN ('INCIDENT_REPORTED', 'INCIDENT_ASSIGNED') THEN NULL ELSE ticket_id END,
            incident_id = CASE WHEN type IN ('INCIDENT_REPORTED', 'INCIDENT_ASSIGNED') THEN incident_id ELSE NULL END
        WHERE ticket_id IS NOT NULL AND incident_id IS NOT NULL
    """)
    op.execute(f"UPDATE notifications SET type = 'SYSTEM' WHERE NOT ({condicion})")
    cambiar_borrado("CASCADE")
    op.create_check_constraint("ck_notificacion_recurso", "notifications", condicion)


def downgrade():
    op.drop_constraint("ck_notificacion_recurso", "notifications", type_="check")
    cambiar_borrado("SET NULL")
    op.drop_table("eventos_incidencia")
    op.drop_column("incidents", "categoria")
    op.execute("""
        UPDATE incidents SET status = CASE
            WHEN status = 'CLOSED' THEN 'RESOLVED'::incident_status_enum
            WHEN status = 'IN_REVIEW' THEN 'INVESTIGATING'::incident_status_enum
            ELSE 'REPORTED'::incident_status_enum END
        WHERE status IN ('ASSIGNED', 'IN_REVIEW', 'CLOSED', 'REOPENED')
    """)
    # los valores del enum se conservan para no recrear el tipo de postgres.
