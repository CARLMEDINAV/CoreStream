"""Add webhooks.message_template (NEW-12: plantilla de mensaje)

Revision ID: d2e3f4a5b6c7
Revises: c1d2e3f4a5b6
Create Date: 2026-10-17 01:00:00.000000

Añade `webhooks.message_template`, una plantilla opcional del texto que se
envía cuando `format = SLACK`. Admite variables entre llaves ({ticket},
{estado}, …); si es NULL o vacía se usa el texto por defecto generado por
`webhook_service.build_slack_payload`.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d2e3f4a5b6c7"
down_revision: Union[str, None] = "c1d2e3f4a5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "webhooks",
        sa.Column("message_template", sa.String(length=2000), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("webhooks", "message_template")
