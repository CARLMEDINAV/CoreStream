"""Add outgoing webhooks (NEW-12)

Revision ID: b7c8d9e0f1a2
Revises: k7l8m9n0o1p2
Create Date: 2026-10-17 00:00:00.000000

Crea las tablas `webhooks` y `webhook_deliveries`. Ambas llevan `client_id`
(TRV-01) con ON DELETE RESTRICT, igual que el resto de tablas de negocio.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b7c8d9e0f1a2"
down_revision: Union[str, None] = "k7l8m9n0o1p2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

delivery_status_enum = postgresql.ENUM(
    "PENDING", "SUCCESS", "FAILED", name="webhook_delivery_status_enum"
)


def upgrade() -> None:
    op.create_table(
        "webhooks",
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("url", sa.String(length=1024), nullable=False),
        sa.Column("secret", sa.String(length=255), nullable=True),
        sa.Column("event_types", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("last_status", sa.String(length=20), nullable=True),
        sa.Column("last_triggered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_count", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=True),
        sa.Column("created_by_id", sa.UUID(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("client_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["applications.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_webhooks_client_id"), "webhooks", ["client_id"], unique=False)
    op.create_index(op.f("ix_webhooks_created_at"), "webhooks", ["created_at"], unique=False)
    op.create_index(op.f("ix_webhooks_is_active"), "webhooks", ["is_active"], unique=False)
    op.create_index(op.f("ix_webhooks_project_id"), "webhooks", ["project_id"], unique=False)

    op.create_table(
        "webhook_deliveries",
        sa.Column("webhook_id", sa.UUID(), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", delivery_status_enum, nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("client_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["webhook_id"], ["webhooks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_webhook_deliveries_client_id"), "webhook_deliveries", ["client_id"], unique=False)
    op.create_index(op.f("ix_webhook_deliveries_created_at"), "webhook_deliveries", ["created_at"], unique=False)
    op.create_index(op.f("ix_webhook_deliveries_event_type"), "webhook_deliveries", ["event_type"], unique=False)
    op.create_index(op.f("ix_webhook_deliveries_status"), "webhook_deliveries", ["status"], unique=False)
    op.create_index(op.f("ix_webhook_deliveries_webhook_id"), "webhook_deliveries", ["webhook_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_webhook_deliveries_webhook_id"), table_name="webhook_deliveries")
    op.drop_index(op.f("ix_webhook_deliveries_status"), table_name="webhook_deliveries")
    op.drop_index(op.f("ix_webhook_deliveries_event_type"), table_name="webhook_deliveries")
    op.drop_index(op.f("ix_webhook_deliveries_created_at"), table_name="webhook_deliveries")
    op.drop_index(op.f("ix_webhook_deliveries_client_id"), table_name="webhook_deliveries")
    op.drop_table("webhook_deliveries")

    op.drop_index(op.f("ix_webhooks_project_id"), table_name="webhooks")
    op.drop_index(op.f("ix_webhooks_is_active"), table_name="webhooks")
    op.drop_index(op.f("ix_webhooks_created_at"), table_name="webhooks")
    op.drop_index(op.f("ix_webhooks_client_id"), table_name="webhooks")
    op.drop_table("webhooks")

    delivery_status_enum.drop(op.get_bind(), checkfirst=True)
