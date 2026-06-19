"""Move position from profiles to workspace_members and workspace_invitations.

position is now per-workspace on the member record. invitation.position lets
inviters pre-fill the position for the invitee.

Revision ID: 007_position_to_workspace_member
Revises: 006_drop_profile_permission
Create Date: 2026-06-04
"""

import sqlalchemy as sa
from alembic import op

from app.db.migration_helpers import add_column_if_not_exists, column_exists, drop_column_if_exists

revision = '007_position_to_workspace_member'
down_revision = '006_drop_profile_permission'
branch_labels = None
depends_on = None


def upgrade() -> None:
    drop_column_if_exists('profiles', 'position')
    add_column_if_not_exists(
        'workspace_members',
        sa.Column('position', sa.String(255), nullable=True),
    )
    add_column_if_not_exists(
        'workspace_invitations',
        sa.Column('position', sa.String(255), nullable=True),
    )


def downgrade() -> None:
    drop_column_if_exists('workspace_invitations', 'position')
    drop_column_if_exists('workspace_members', 'position')
    if not column_exists('profiles', 'position'):
        op.add_column(
            'profiles',
            sa.Column('position', sa.String(), nullable=False, server_default='User'),
        )
