"""panel interno de planes y banderas."""
import sqlalchemy as sa

from alembic import op

revision = "e4a5b6c7d8e9"
down_revision = "c7f3a91d2e45"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("clients", sa.Column("feature_overrides", sa.JSON(), server_default="{}", nullable=False))
    op.add_column("audit_logs", sa.Column("feature_flag", sa.String(50)), schema="audit")
    op.add_column("audit_logs", sa.Column("commercial_detail", sa.JSON()), schema="audit")
    op.create_index("ix_audit_audit_logs_feature_flag", "audit_logs", ["feature_flag"], schema="audit")


def downgrade():
    op.drop_index("ix_audit_audit_logs_feature_flag", table_name="audit_logs", schema="audit")
    op.drop_column("audit_logs", "commercial_detail", schema="audit")
    op.drop_column("audit_logs", "feature_flag", schema="audit")
    op.drop_column("clients", "feature_overrides")
