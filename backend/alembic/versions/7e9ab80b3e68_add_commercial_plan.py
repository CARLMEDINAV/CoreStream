"""agrega el plan comercial a los clientes existentes."""
from alembic import op
import sqlalchemy as sa

revision = "7e9ab80b3e68"
down_revision = "6d8fa79a2d57"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("clients", sa.Column(
        "commercial_plan", sa.String(20), nullable=False, server_default="Basico"
    ))


def downgrade() -> None:
    op.drop_column("clients", "commercial_plan")
