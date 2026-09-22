"""add client_id multi-tenancy columns

Revision ID: 6d8fa79a2d57
Revises: i5j6k7l8m9n0
Create Date: 2026-09-22 02:31:52.336148

"""
from typing import Sequence, Union

import uuid
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql



# revision identifiers, used by Alembic.
revision: str = '6d8fa79a2d57'
down_revision: Union[str, None] = 'i5j6k7l8m9n0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


BOOTSTRAP_CLIENT_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")

TENANT_TABLES = [
    "users",
    "applications",
    "epics",
    "tickets",
    "subtasks",
    "ticket_events",
    "documents",
    "incidents",
    "meetings",
    "meeting_attendances",
    "notifications",
    "invitations",
]


def upgrade() -> None:
    # 1. Tabla clients
    op.create_table(
        "clients",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_clients_slug", "clients", ["slug"], unique=True)
    op.create_index("ix_clients_is_active", "clients", ["is_active"])

    # 2. Cliente bootstrap: todo lo que ya existe hoy queda asignado a este
    op.execute(
        sa.text(
            "INSERT INTO clients (id, name, slug, is_active) "
            "VALUES (:id, :name, :slug, true)"
        ).bindparams(id=BOOTSTRAP_CLIENT_ID, name="Alloxentric", slug="alloxentric")
    )

    # 3. client_id en cada tabla: nullable -> backfill -> NOT NULL -> índice + FK
    for table in TENANT_TABLES:
        op.add_column(table, sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=True))

        op.execute(
            sa.text(f"UPDATE {table} SET client_id = :cid WHERE client_id IS NULL")
            .bindparams(cid=BOOTSTRAP_CLIENT_ID)
        )

        op.alter_column(table, "client_id", nullable=False)
        op.create_index(f"ix_{table}_client_id", table, ["client_id"])
        op.create_foreign_key(
            f"fk_{table}_client_id_clients",
            table,
            "clients",
            ["client_id"],
            ["id"],
            ondelete="RESTRICT",
        )


def downgrade() -> None:
    for table in reversed(TENANT_TABLES):
        op.drop_constraint(f"fk_{table}_client_id_clients", table, type_="foreignkey")
        op.drop_index(f"ix_{table}_client_id", table_name=table)
        op.drop_column(table, "client_id")

    op.drop_index("ix_clients_is_active", table_name="clients")
    op.drop_index("ix_clients_slug", table_name="clients")
    op.drop_table("clients")