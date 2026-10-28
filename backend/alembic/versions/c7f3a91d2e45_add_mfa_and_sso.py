"""NEW-08: 2FA (TOTP), códigos de recuperación, identidades SSO y política por cliente

Revision ID: c7f3a91d2e45
Revises: d2e3f4a5b6c7
Create Date: 2026-10-24 12:00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "c7f3a91d2e45"
# >>> ACCIÓN MANUAL: poner aquí el id que devuelva `alembic heads` (ver guía). <<<
down_revision: Union[str, None] = "d2e3f4a5b6c7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- users: columnas TOTP -------------------------------------------
    op.add_column("users", sa.Column("totp_secret_encrypted", sa.Text(), nullable=True))
    op.add_column(
        "users",
        sa.Column("totp_enabled", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column(
        "users", sa.Column("totp_enabled_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("users", sa.Column("totp_last_used_step", sa.BigInteger(), nullable=True))

    # --- clients: política de 2FA obligatorio ---------------------------
    op.add_column(
        "clients",
        sa.Column("require_2fa", sa.Boolean(), server_default=sa.false(), nullable=False),
    )

    # --- user_recovery_codes --------------------------------------------
    op.create_table(
        "user_recovery_codes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "client_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("clients.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("code_hash", sa.String(64), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("user_id", "code_hash", name="uq_recovery_user_hash"),
    )
    op.create_index("ix_user_recovery_codes_created_at", "user_recovery_codes", ["created_at"])
    op.create_index("ix_user_recovery_codes_client_id", "user_recovery_codes", ["client_id"])
    op.create_index("ix_user_recovery_codes_user_id", "user_recovery_codes", ["user_id"])

    # --- user_identities ------------------------------------------------
    op.create_table(
        "user_identities",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "client_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("clients.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("provider", "subject", name="uq_identity_provider_subject"),
        sa.UniqueConstraint("user_id", "provider", name="uq_identity_user_provider"),
    )
    op.create_index("ix_user_identities_created_at", "user_identities", ["created_at"])
    op.create_index("ix_user_identities_client_id", "user_identities", ["client_id"])
    op.create_index("ix_user_identities_user_id", "user_identities", ["user_id"])


def downgrade() -> None:
    op.drop_table("user_identities")
    op.drop_table("user_recovery_codes")
    op.drop_column("clients", "require_2fa")
    op.drop_column("users", "totp_last_used_step")
    op.drop_column("users", "totp_enabled_at")
    op.drop_column("users", "totp_enabled")
    op.drop_column("users", "totp_secret_encrypted")
