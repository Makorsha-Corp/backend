"""Drop unique constraint on workspace_invitations(workspace_id, email).

Allows multiple invitations to the same email in a workspace (e.g. after cancelling and re-inviting).

Revision ID: 005_drop_invitation_email_unique
Revises: 004_profile_fixes
Create Date: 2026-06-03
"""

from alembic import op

revision = '005_drop_invitation_email_unique'
down_revision = '004_profile_fixes'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint('uq_workspace_invitation_email', 'workspace_invitations', type_='unique')


def downgrade() -> None:
    op.create_unique_constraint(
        'uq_workspace_invitation_email',
        'workspace_invitations',
        ['workspace_id', 'email'],
    )
