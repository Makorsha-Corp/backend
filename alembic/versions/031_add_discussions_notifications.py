"""Add discussions and notifications tables

Revision ID: 031
Revises: 030
Create Date: 2026-06-21
"""
from alembic import op
import sqlalchemy as sa

revision = '031_add_discussions_notifications'
down_revision = '030_drop_legacy_orders'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'discussions',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('workspace_id', sa.Integer(), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('entity_type', sa.String(30), nullable=False),
        sa.Column('entity_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('profiles.id', ondelete='SET NULL'), nullable=True),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('parent_id', sa.Integer(), sa.ForeignKey('discussions.id', ondelete='CASCADE'), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_discussions_workspace_id', 'discussions', ['workspace_id'])
    op.create_index('ix_discussions_entity', 'discussions', ['workspace_id', 'entity_type', 'entity_id'])
    op.create_index('ix_discussions_parent_id', 'discussions', ['parent_id'])

    op.create_table(
        'notifications',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('workspace_id', sa.Integer(), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('recipient_user_id', sa.Integer(), sa.ForeignKey('profiles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('actor_user_id', sa.Integer(), sa.ForeignKey('profiles.id', ondelete='SET NULL'), nullable=True),
        sa.Column('notification_type', sa.String(30), nullable=False),
        sa.Column('entity_type', sa.String(30), nullable=False),
        sa.Column('entity_id', sa.Integer(), nullable=False),
        sa.Column('source_type', sa.String(30), nullable=False),
        sa.Column('source_id', sa.Integer(), nullable=False),
        sa.Column('preview', sa.Text(), nullable=True),
        sa.Column('is_read', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('read_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_notifications_workspace_id', 'notifications', ['workspace_id'])
    op.create_index('ix_notifications_recipient_unread', 'notifications', ['workspace_id', 'recipient_user_id', 'is_read'])


def downgrade() -> None:
    op.drop_table('notifications')
    op.drop_table('discussions')
