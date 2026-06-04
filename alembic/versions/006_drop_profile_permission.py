"""Drop permission column from profiles table.

Role-based access control is handled entirely by workspace_members.role.
The profile-level permission field was a legacy artefact predating the
multi-workspace model.

Revision ID: 006_drop_profile_permission
Revises: 005_drop_invitation_email_unique
Create Date: 2026-06-04
"""

from alembic import op

revision = '006_drop_profile_permission'
down_revision = '005_drop_invitation_email_unique'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column('profiles', 'permission')


def downgrade() -> None:
    import sqlalchemy as sa
    from sqlalchemy.dialects import postgresql
    op.add_column(
        'profiles',
        sa.Column(
            'permission',
            postgresql.ENUM('owner', 'finance', 'ground-team', 'ground-team-manager', name='roleenum'),
            nullable=False,
            server_default='owner',
        ),
    )
