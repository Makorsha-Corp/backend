"""Add project_events, project_members, and projects.visibility.

Revision ID: 023_project_events_members
Revises: 022_po_stage_workflow
"""

import sqlalchemy as sa
from alembic import op

revision = '023_project_events_members'
down_revision = '022_po_stage_workflow'
branch_labels = None
depends_on = None


def _table_names(inspector: sa.Inspector) -> set[str]:
    return set(inspector.get_table_names())


def _column_names(inspector: sa.Inspector, table: str) -> set[str]:
    return {c['name'] for c in inspector.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = _table_names(inspector)
    project_columns = _column_names(inspector, 'projects') if 'projects' in tables else set()

    if 'visibility' not in project_columns:
        # Orphan enum type only when no column references it yet.
        op.execute(sa.text('DROP TYPE IF EXISTS projectvisibilityenum'))
        op.add_column(
            'projects',
            sa.Column(
                'visibility',
                sa.String(20),
                nullable=False,
                server_default='workspace',
            ),
        )
    else:
        # Normalize legacy enum column to varchar if present, then drop enum type.
        op.execute(
            sa.text(
                """
                DO $$ BEGIN
                  ALTER TABLE projects
                    ALTER COLUMN visibility TYPE varchar(20)
                    USING visibility::text;
                EXCEPTION WHEN others THEN
                  NULL;
                END $$;
                """
            )
        )
        op.execute(sa.text('DROP TYPE IF EXISTS projectvisibilityenum'))

    if 'project_members' not in tables:
        op.create_table(
            'project_members',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('workspace_id', sa.Integer(), nullable=False),
            sa.Column('project_id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('assigned_by', sa.Integer(), nullable=True),
            sa.Column('assigned_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['user_id'], ['profiles.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['assigned_by'], ['profiles.id'], ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('project_id', 'user_id', name='uq_project_member_project_user'),
        )
        op.create_index('ix_project_members_workspace_id', 'project_members', ['workspace_id'])
        op.create_index('ix_project_members_project_id', 'project_members', ['project_id'])
        op.create_index('ix_project_members_user_id', 'project_members', ['user_id'])

    if 'project_events' not in tables:
        op.create_table(
            'project_events',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('workspace_id', sa.Integer(), nullable=False),
            sa.Column('project_id', sa.Integer(), nullable=False),
            sa.Column('event_type', sa.String(50), nullable=False),
            sa.Column('description', sa.Text(), nullable=False),
            sa.Column('metadata', sa.JSON(), nullable=True),
            sa.Column('performed_by', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['performed_by'], ['profiles.id'], ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_project_events_workspace_id', 'project_events', ['workspace_id'])
        op.create_index('ix_project_events_project_id', 'project_events', ['project_id'])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = _table_names(inspector)

    if 'project_events' in tables:
        op.drop_index('ix_project_events_project_id', table_name='project_events')
        op.drop_index('ix_project_events_workspace_id', table_name='project_events')
        op.drop_table('project_events')

    if 'project_members' in tables:
        op.drop_index('ix_project_members_user_id', table_name='project_members')
        op.drop_index('ix_project_members_project_id', table_name='project_members')
        op.drop_index('ix_project_members_workspace_id', table_name='project_members')
        op.drop_table('project_members')

    project_columns = _column_names(inspector, 'projects') if 'projects' in tables else set()
    if 'visibility' in project_columns:
        op.drop_column('projects', 'visibility')
