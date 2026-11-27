"""Agrega la duración en minutos a las reuniones."""
import sqlalchemy as sa

from alembic import op

revision = "a6b7c8d9e0f1"
down_revision = "f5b6c7d8e9a0"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "meetings",
        sa.Column("duration_minutes", sa.Integer(), nullable=False, server_default="30"),
    )


def downgrade():
    op.drop_column("meetings", "duration_minutes")
