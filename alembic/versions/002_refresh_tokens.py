"""Add refresh_tokens table for stateful refresh-token rotation flow.

Revision ID: 002_refresh_tokens
Revises: 001
Create Date: 2026-05-16
"""
from alembic import op
import sqlalchemy as sa


# Alembic identifiers
revision = "002_refresh_tokens"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "workspace_id",
            sa.Integer(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("token_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column("family_id", sa.String(length=36), nullable=False),
        sa.Column(
            "issued_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column(
            "replaced_by_id",
            sa.Integer(),
            sa.ForeignKey("refresh_tokens.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
    )

    op.create_index(
        "ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"]
    )
    op.create_index(
        "ix_refresh_tokens_workspace_id", "refresh_tokens", ["workspace_id"]
    )
    op.create_index(
        "ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"], unique=True
    )
    op.create_index(
        "ix_refresh_tokens_family_id", "refresh_tokens", ["family_id"]
    )
    op.create_index(
        "ix_refresh_tokens_expires_at", "refresh_tokens", ["expires_at"]
    )
    op.create_index(
        "ix_refresh_tokens_user_family",
        "refresh_tokens",
        ["user_id", "family_id"],
    )
    op.create_index(
        "ix_refresh_tokens_active",
        "refresh_tokens",
        ["user_id", "revoked_at", "expires_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_refresh_tokens_active", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_user_family", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_expires_at", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_family_id", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_token_hash", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_workspace_id", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_user_id", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")
