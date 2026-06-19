"""Drop unique constraint on workspace_invitations(workspace_id, email).

Allows multiple invitations to the same email in a workspace (e.g. after cancelling and re-inviting).

Revision ID: 005_drop_invitation_email_unique
Revises: 004_profile_fixes
Create Date: 2026-06-03
"""

from alembic import op

from app.db.migration_helpers import drop_unique_constraint_if_exists, unique_constraint_exists

revision = '005_drop_invitation_email_unique'
down_revision = '004_profile_fixes'
branch_labels = None
depends_on = None


def upgrade() -> None:
    drop_unique_constraint_if_exists('workspace_invitations', 'uq_workspace_invitation_email')


def downgrade() -> None:
    if not unique_constraint_exists('workspace_invitations', 'uq_workspace_invitation_email'):
        op.create_unique_constraint(
            'uq_workspace_invitation_email',
            'workspace_invitations',
            ['workspace_id', 'email'],
        )
