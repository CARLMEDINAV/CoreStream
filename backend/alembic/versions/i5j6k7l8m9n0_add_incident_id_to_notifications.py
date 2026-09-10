"""add incident_id and enum types to notifications

Revision ID: i5j6k7l8m9n0
Revises: a2b3c4d5e6f7
Create Date: 2026-09-08 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'i5j6k7l8m9n0'
down_revision = 'a2b3c4d5e6f7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Agregar valores al enum de PostgreSQL
    op.execute("ALTER TYPE notification_type_enum ADD VALUE IF NOT EXISTS 'INCIDENT_REPORTED'")
    op.execute("ALTER TYPE notification_type_enum ADD VALUE IF NOT EXISTS 'INCIDENT_ASSIGNED'")

    # 2. Agregar columna incident_id
    op.add_column(
        'notifications',
        sa.Column('incident_id', postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.create_index(
        op.f('ix_notifications_incident_id'),
        'notifications',
        ['incident_id'],
        unique=False
    )
    op.create_foreign_key(
        'fk_notifications_incident_id_incidents',
        'notifications',
        'incidents',
        ['incident_id'],
        ['id'],
        ondelete='SET NULL'
    )


def downgrade() -> None:
    op.drop_constraint('fk_notifications_incident_id_incidents', 'notifications', type_='foreignkey')
    op.drop_index(op.f('ix_notifications_incident_id'), table_name='notifications')
    op.drop_column('notifications', 'incident_id')