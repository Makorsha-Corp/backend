"""Add left_at to workspace_members and accepted_by_user_id to workspace_invitations.

Revision ID: 003_ws_member_inv_fixes
Revises: 002_refresh_tokens
Create Date: 2026-06-03
"""
from alembic import op
import sqlalchemy as sa

revision = "003_ws_member_inv_fixes"
down_revision = "002_refresh_tokens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    existing_member_cols = [c["name"] for c in inspector.get_columns("workspace_members")]
    if "left_at" not in existing_member_cols:
        op.add_column(
            "workspace_members",
            sa.Column("left_at", sa.DateTime(), nullable=True),
        )

    existing_inv_cols = [c["name"] for c in inspector.get_columns("workspace_invitations")]
    if "accepted_by_user_id" not in existing_inv_cols:
        op.add_column(
            "workspace_invitations",
            sa.Column(
                "accepted_by_user_id",
                sa.Integer(),
                sa.ForeignKey("profiles.id", ondelete="SET NULL"),
                nullable=True,
            ),
        )


def downgrade() -> None:
    op.drop_column("workspace_invitations", "accepted_by_user_id")
    op.drop_column("workspace_members", "left_at")
