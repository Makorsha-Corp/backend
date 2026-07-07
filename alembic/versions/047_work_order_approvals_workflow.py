"""Work order approvals-only workflow: simplify status enum, replace approval booleans
with a multi-approver table, add lifecycle stamps, void fields, and optional invoice linkage.

Revision ID: 047_work_order_approvals_workflow
Revises: 046_expense_order_void_fields
"""

import sqlalchemy as sa
from alembic import op

from app.db.migration_helpers import (
    add_column_if_not_exists,
    column_exists,
    create_unique_constraint_if_not_exists,
    drop_column_if_exists,
    drop_unique_constraint_if_exists,
    table_exists,
)

revision = '047_work_order_approvals_workflow'
down_revision = '046_expense_order_void_fields'
branch_labels = None
depends_on = None

_DROP_COLUMNS = [
    'order_approved', 'order_approved_by', 'order_approved_at',
    'cost_approved', 'cost_approved_by', 'cost_approved_at',
]


def upgrade() -> None:
    # Collapse the status value set: PENDING_APPROVAL -> DRAFT, CANCELLED -> VOIDED,
    # and drop the native Postgres enum type in favor of a plain varchar (matches the
    # pattern used for projects.visibility in 023_project_events_members).
    if column_exists('work_orders', 'status'):
        op.execute(
            sa.text(
                """
                DO $$ BEGIN
                  ALTER TABLE work_orders
                    ALTER COLUMN status TYPE varchar(20)
                    USING (
                      CASE status::text
                        WHEN 'PENDING_APPROVAL' THEN 'DRAFT'
                        WHEN 'CANCELLED' THEN 'VOIDED'
                        ELSE status::text
                      END
                    );
                EXCEPTION WHEN others THEN
                  NULL;
                END $$;
                """
            )
        )
    op.execute(sa.text('DROP TYPE IF EXISTS workorderstatusenum'))

    create_unique_constraint_if_not_exists(
        'work_orders', 'uq_wo_workspace_number', ['workspace_id', 'work_order_number'],
    )

    for col in _DROP_COLUMNS:
        drop_column_if_exists('work_orders', col)

    add_column_if_not_exists('work_orders', sa.Column('required_approvals', sa.Integer(), nullable=True))
    add_column_if_not_exists(
        'work_orders',
        sa.Column('approved_by', sa.Integer(), sa.ForeignKey('profiles.id', ondelete='SET NULL'), nullable=True),
    )
    add_column_if_not_exists('work_orders', sa.Column('approved_at', sa.DateTime(), nullable=True))
    add_column_if_not_exists(
        'work_orders',
        sa.Column('started_by', sa.Integer(), sa.ForeignKey('profiles.id', ondelete='SET NULL'), nullable=True),
    )
    add_column_if_not_exists('work_orders', sa.Column('started_at', sa.DateTime(), nullable=True))
    add_column_if_not_exists(
        'work_orders',
        sa.Column('completed_by', sa.Integer(), sa.ForeignKey('profiles.id', ondelete='SET NULL'), nullable=True),
    )
    add_column_if_not_exists('work_orders', sa.Column('completed_at', sa.DateTime(), nullable=True))
    add_column_if_not_exists('work_orders', sa.Column('void_note', sa.Text(), nullable=True))
    add_column_if_not_exists('work_orders', sa.Column('voided_at', sa.DateTime(), nullable=True))
    add_column_if_not_exists(
        'work_orders',
        sa.Column('voided_by', sa.Integer(), sa.ForeignKey('profiles.id', ondelete='SET NULL'), nullable=True),
    )
    add_column_if_not_exists(
        'work_orders',
        sa.Column('account_id', sa.Integer(), sa.ForeignKey('accounts.id', ondelete='RESTRICT'), nullable=True),
    )
    add_column_if_not_exists(
        'work_orders',
        sa.Column('invoice_id', sa.Integer(), sa.ForeignKey('account_invoices.id', ondelete='SET NULL'), nullable=True),
    )

    if not table_exists('work_order_approvers'):
        op.create_table(
            'work_order_approvers',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('workspace_id', sa.Integer(), nullable=False),
            sa.Column('work_order_id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('assigned_by', sa.Integer(), nullable=True),
            sa.Column('assigned_at', sa.DateTime(), nullable=False),
            sa.Column('approved', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column('approved_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['work_order_id'], ['work_orders.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['user_id'], ['profiles.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['assigned_by'], ['profiles.id'], ondelete='SET NULL'),
            sa.UniqueConstraint('work_order_id', 'user_id', name='uq_wo_approver_wo_user'),
        )
        op.create_index('ix_work_order_approvers_workspace_id', 'work_order_approvers', ['workspace_id'])
        op.create_index('ix_work_order_approvers_work_order_id', 'work_order_approvers', ['work_order_id'])
        op.create_index('ix_work_order_approvers_user_id', 'work_order_approvers', ['user_id'])

    if not table_exists('work_order_events'):
        op.create_table(
            'work_order_events',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('workspace_id', sa.Integer(), nullable=False),
            sa.Column('work_order_id', sa.Integer(), nullable=False),
            sa.Column('event_type', sa.String(50), nullable=False),
            sa.Column('description', sa.Text(), nullable=False),
            sa.Column('metadata', sa.JSON(), nullable=True),
            sa.Column('performed_by', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['work_order_id'], ['work_orders.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['performed_by'], ['profiles.id'], ondelete='SET NULL'),
        )
        op.create_index('ix_work_order_events_workspace_id', 'work_order_events', ['workspace_id'])
        op.create_index('ix_work_order_events_work_order_id', 'work_order_events', ['work_order_id'])


def downgrade() -> None:
    drop_unique_constraint_if_exists('work_orders', 'uq_wo_workspace_number')

    if table_exists('work_order_events'):
        op.drop_table('work_order_events')
    if table_exists('work_order_approvers'):
        op.drop_table('work_order_approvers')

    drop_column_if_exists('work_orders', 'invoice_id')
    drop_column_if_exists('work_orders', 'account_id')
    drop_column_if_exists('work_orders', 'voided_by')
    drop_column_if_exists('work_orders', 'voided_at')
    drop_column_if_exists('work_orders', 'void_note')
    drop_column_if_exists('work_orders', 'completed_at')
    drop_column_if_exists('work_orders', 'completed_by')
    drop_column_if_exists('work_orders', 'started_at')
    drop_column_if_exists('work_orders', 'started_by')
    drop_column_if_exists('work_orders', 'approved_at')
    drop_column_if_exists('work_orders', 'approved_by')
    drop_column_if_exists('work_orders', 'required_approvals')

    if column_exists('work_orders', 'status'):
        op.execute(
            sa.text(
                """
                DO $$ BEGIN
                  ALTER TABLE work_orders
                    ALTER COLUMN status TYPE varchar(20)
                    USING (
                      CASE status::text
                        WHEN 'VOIDED' THEN 'CANCELLED'
                        ELSE status::text
                      END
                    );
                EXCEPTION WHEN others THEN
                  NULL;
                END $$;
                """
            )
        )

    for col in _DROP_COLUMNS:
        add_column_if_not_exists(
            'work_orders',
            sa.Column(
                col,
                sa.Boolean() if col in ('order_approved', 'cost_approved') else (
                    sa.DateTime() if col.endswith('_at') else sa.Integer()
                ),
                nullable=False if col in ('order_approved', 'cost_approved') else True,
                server_default=sa.false() if col in ('order_approved', 'cost_approved') else None,
            ),
        )
