"""Make hashed_password NOT NULL on profiles.

Revision ID: 004_profile_fixes
Revises: 003_ws_member_inv_fixes
Create Date: 2026-06-03
"""
from alembic import op
import sqlalchemy as sa

revision = "004_profile_fixes"
down_revision = "003_ws_member_inv_fixes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Set any existing NULL passwords to an unusable sentinel so NOT NULL can be applied.
    # Rows with this value will fail bcrypt.checkpw, so they cannot log in without a reset.
    op.execute(
        "UPDATE profiles SET hashed_password = 'INVALID-NO-PASSWORD' WHERE hashed_password IS NULL"
    )
    op.alter_column("profiles", "hashed_password", nullable=False)


def downgrade() -> None:
    op.alter_column("profiles", "hashed_password", nullable=True)
