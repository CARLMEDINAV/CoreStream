"""Add webhooks.format (NEW-12: soporte Slack)

Revision ID: c1d2e3f4a5b6
Revises: b7c8d9e0f1a2
Create Date: 2026-10-17 00:30:00.000000

Añade `webhooks.format` con `JSON` por defecto. Permite que un webhook envíe
el cuerpo en formato Slack (`{"text": ...}`, compatible con Incoming Webhooks)
además del JSON propio de CoreStream.

Se guarda como texto (no como tipo ENUM de PostgreSQL) para poder añadir
formatos nuevos sin una migración de tipo, igual que `webhooks.last_status`.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c1d2e3f4a5b6"
down_revision: Union[str, None] = "b7c8d9e0f1a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "webhooks",
        sa.Column(
            "format",
            sa.String(length=20),
            nullable=False,
            server_default="JSON",
        ),
    )


def downgrade() -> None:
    op.drop_column("webhooks", "format")
