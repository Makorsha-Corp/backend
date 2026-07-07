"""Add work_order_templates / work_order_template_items / work_order_template_approvers
— reusable presets for "things that happen all the time" maintenance, and
work_orders.work_order_template_id for traceability back to the template that
generated an order.

Revision ID: 053_work_order_templates
Revises: 052_work_order_item_action_type
"""

import sqlalchemy as sa
from alembic import op

from app.db.migration_helpers import column_exists, table_exists

revision = '053_work_order_templates'
down_revision = '052_work_order_item_action_type'
branch_labels = None
depends_on = None


def upgrade() -> None:
    if not table_exists('work_order_templates'):
        op.create_table(
            'work_order_templates',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('workspace_id', sa.Integer(), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
            sa.Column('template_name', sa.String(255), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('work_order_type_id', sa.Integer(), sa.ForeignKey('work_order_types.id', ondelete='RESTRICT'), nullable=False),
            sa.Column('priority', sa.String(20), nullable=False, server_default='MEDIUM'),
            sa.Column('assigned_to', sa.String(255), nullable=True),
            sa.Column('uses_inventory', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column('account_id', sa.Integer(), sa.ForeignKey('accounts.id', ondelete='RESTRICT'), nullable=True),
            sa.Column('cost', sa.Numeric(15, 2), nullable=True),
            sa.Column('requires_approval', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('created_by', sa.Integer(), sa.ForeignKey('profiles.id', ondelete='SET NULL'), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_by', sa.Integer(), sa.ForeignKey('profiles.id', ondelete='SET NULL'), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
        )
        op.create_index('ix_work_order_templates_workspace_id', 'work_order_templates', ['workspace_id'])
        op.create_index('ix_work_order_templates_work_order_type_id', 'work_order_templates', ['work_order_type_id'])
        op.create_index('ix_work_order_templates_account_id', 'work_order_templates', ['account_id'])

    if not table_exists('work_order_template_items'):
        op.create_table(
            'work_order_template_items',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('workspace_id', sa.Integer(), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
            sa.Column('work_order_template_id', sa.Integer(), sa.ForeignKey('work_order_templates.id', ondelete='CASCADE'), nullable=False),
            sa.Column('item_id', sa.Integer(), sa.ForeignKey('items.id'), nullable=False),
            sa.Column('quantity', sa.Numeric(15, 2), nullable=False, server_default='1'),
            sa.Column('action_type', sa.String(20), nullable=False, server_default='CONSUME'),
            sa.Column('replaced_item_id', sa.Integer(), sa.ForeignKey('items.id'), nullable=True),
            sa.Column('notes', sa.Text(), nullable=True),
        )
        op.create_index('ix_work_order_template_items_workspace_id', 'work_order_template_items', ['workspace_id'])
        op.create_index('ix_work_order_template_items_work_order_template_id', 'work_order_template_items', ['work_order_template_id'])
        op.create_index('ix_work_order_template_items_item_id', 'work_order_template_items', ['item_id'])
        op.create_index('ix_work_order_template_items_replaced_item_id', 'work_order_template_items', ['replaced_item_id'])

    if not table_exists('work_order_template_approvers'):
        op.create_table(
            'work_order_template_approvers',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('workspace_id', sa.Integer(), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
            sa.Column('work_order_template_id', sa.Integer(), sa.ForeignKey('work_order_templates.id', ondelete='CASCADE'), nullable=False),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('profiles.id', ondelete='CASCADE'), nullable=False),
            sa.UniqueConstraint('work_order_template_id', 'user_id', name='uq_wo_template_approver'),
        )
        op.create_index('ix_work_order_template_approvers_workspace_id', 'work_order_template_approvers', ['workspace_id'])
        op.create_index('ix_work_order_template_approvers_work_order_template_id', 'work_order_template_approvers', ['work_order_template_id'])
        op.create_index('ix_work_order_template_approvers_user_id', 'work_order_template_approvers', ['user_id'])

    if not column_exists('work_orders', 'work_order_template_id'):
        op.add_column(
            'work_orders',
            sa.Column('work_order_template_id', sa.Integer(), sa.ForeignKey('work_order_templates.id', ondelete='SET NULL'), nullable=True),
        )
        op.create_index('ix_work_orders_work_order_template_id', 'work_orders', ['work_order_template_id'])


def downgrade() -> None:
    if column_exists('work_orders', 'work_order_template_id'):
        op.drop_index('ix_work_orders_work_order_template_id', table_name='work_orders')
        op.drop_column('work_orders', 'work_order_template_id')
    if table_exists('work_order_template_approvers'):
        op.drop_table('work_order_template_approvers')
    if table_exists('work_order_template_items'):
        op.drop_table('work_order_template_items')
    if table_exists('work_order_templates'):
        op.drop_table('work_order_templates')
