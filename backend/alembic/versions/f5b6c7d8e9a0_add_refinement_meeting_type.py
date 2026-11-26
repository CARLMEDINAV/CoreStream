"""Agrega REFINEMENT a los tipos de reunión."""
from alembic import op

revision = "f5b6c7d8e9a0"
down_revision = "e4a5b6c7d8e9"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TYPE meeting_type_enum ADD VALUE IF NOT EXISTS 'REFINEMENT'")


def downgrade():
    # PostgreSQL no permite quitar valores de un enum sin recrear el tipo.
    pass
