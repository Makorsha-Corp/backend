"""Work order items gain inventory-source/consumption tracking and decimal quantities;
add project_component_activity_events for completion-log parity with machines.

Revision ID: 048_work_order_item_inventory_and_component_logs
Revises: 047_work_order_approvals_workflow
"""

import sqlalchemy as sa
from alembic import op

from app.db.migration_helpers import add_column_if_not_exists, column_exists, table_exists

revision = '048_work_order_item_inventory_and_component_logs'
down_revision = '047_work_order_approvals_workflow'
branch_labels = None
depends_on = None


def upgrade() -> None:
    if column_exists('work_order_items', 'quantity'):
        op.execute(
            sa.text(
                """
                ALTER TABLE work_order_items
                  ALTER COLUMN quantity TYPE numeric(15, 2)
                  USING quantity::numeric(15, 2);
                """
            )
        )

    add_column_if_not_exists(
        'work_order_items', sa.Column('uses_inventory', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    add_column_if_not_exists('work_order_items', sa.Column('source_location_type', sa.String(20), nullable=True))
    add_column_if_not_exists('work_order_items', sa.Column('source_location_id', sa.Integer(), nullable=True))
    add_column_if_not_exists('work_order_items', sa.Column('consumed_at', sa.DateTime(), nullable=True))
    add_column_if_not_exists(
        'work_order_items',
        sa.Column('consumed_by', sa.Integer(), sa.ForeignKey('profiles.id', ondelete='SET NULL'), nullable=True),
    )
    add_column_if_not_exists('work_order_items', sa.Column('unit_cost', sa.Numeric(15, 2), nullable=True))
    add_column_if_not_exists('work_order_items', sa.Column('total_cost', sa.Numeric(15, 2), nullable=True))
    add_column_if_not_exists('work_order_items', sa.Column('updated_at', sa.DateTime(), nullable=True))
    add_column_if_not_exists(
        'work_order_items',
        sa.Column('updated_by', sa.Integer(), sa.ForeignKey('profiles.id', ondelete='SET NULL'), nullable=True),
    )

    if not table_exists('project_component_activity_events'):
        op.create_table(
            'project_component_activity_events',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('workspace_id', sa.Integer(), nullable=False),
            sa.Column('project_component_id', sa.Integer(), nullable=False),
            sa.Column('event_type', sa.String(50), nullable=False),
            sa.Column('description', sa.Text(), nullable=False),
            sa.Column('metadata', sa.JSON(), nullable=True),
            sa.Column('performed_by', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['project_component_id'], ['project_components.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['performed_by'], ['profiles.id'], ondelete='SET NULL'),
        )
        op.create_index(
            'ix_project_component_activity_events_workspace_id',
            'project_component_activity_events', ['workspace_id'],
        )
        op.create_index(
            'ix_project_component_activity_events_project_component_id',
            'project_component_activity_events', ['project_component_id'],
        )


def downgrade() -> None:
    if table_exists('project_component_activity_events'):
        op.drop_table('project_component_activity_events')

    for col in (
        'updated_by', 'updated_at', 'total_cost', 'unit_cost', 'consumed_by',
        'consumed_at', 'source_location_id', 'source_location_type', 'uses_inventory',
    ):
        if column_exists('work_order_items', col):
            op.drop_column('work_order_items', col)

    if column_exists('work_order_items', 'quantity'):
        op.execute(
            sa.text(
                """
                ALTER TABLE work_order_items
                  ALTER COLUMN quantity TYPE integer
                  USING trunc(quantity)::integer;
                """
            )
        )
