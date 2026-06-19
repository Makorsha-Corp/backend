"""Add invoice lifecycle status, invoice_status_tracker, and payment void support.

invoice_status: draft | confirmed | voided on account_invoices
invoice_status_tracker: append-only log of every invoice status transition
invoice_payments: is_voided + void audit columns

Revision ID: 016_invoice_status_and_void
Revises: 015_po_optional_supplier
Create Date: 2026-06-07
"""

import sqlalchemy as sa
from alembic import op

from app.db.migration_helpers import add_column_if_not_exists, table_exists

revision = '016_invoice_status_and_void'
down_revision = '015_po_optional_supplier'
branch_labels = None
depends_on = None


def upgrade() -> None:
    add_column_if_not_exists(
        'account_invoices',
        sa.Column('invoice_status', sa.String(20), nullable=False, server_default='draft'),
    )
    add_column_if_not_exists('account_invoices', sa.Column('void_note', sa.Text(), nullable=True))

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if 'account_invoices' in inspector.get_table_names():
        indexes = {idx['name'] for idx in inspector.get_indexes('account_invoices')}
        if 'ix_account_invoices_invoice_status' not in indexes:
            op.create_index('ix_account_invoices_invoice_status', 'account_invoices', ['invoice_status'])

    if not table_exists('invoice_status_tracker'):
        op.create_table(
            'invoice_status_tracker',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('workspace_id', sa.Integer(), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
            sa.Column('invoice_id', sa.Integer(), sa.ForeignKey('account_invoices.id', ondelete='CASCADE'), nullable=False),
            sa.Column('from_status', sa.String(20), nullable=False),
            sa.Column('to_status', sa.String(20), nullable=False),
            sa.Column('changed_by', sa.Integer(), sa.ForeignKey('profiles.id'), nullable=True),
            sa.Column('changed_at', sa.DateTime(), nullable=False),
        )
        op.create_index('ix_invoice_status_tracker_invoice_id', 'invoice_status_tracker', ['invoice_id'])
        op.create_index('ix_invoice_status_tracker_workspace_id', 'invoice_status_tracker', ['workspace_id'])

    add_column_if_not_exists(
        'invoice_payments',
        sa.Column('is_voided', sa.Boolean(), nullable=False, server_default='false'),
    )
    add_column_if_not_exists('invoice_payments', sa.Column('voided_at', sa.DateTime(), nullable=True))
    add_column_if_not_exists('invoice_payments', sa.Column('voided_by', sa.Integer(), nullable=True))
    add_column_if_not_exists('invoice_payments', sa.Column('void_note', sa.Text(), nullable=True))


def downgrade() -> None:
    from app.db.migration_helpers import drop_column_if_exists

    drop_column_if_exists('invoice_payments', 'void_note')
    drop_column_if_exists('invoice_payments', 'voided_by')
    drop_column_if_exists('invoice_payments', 'voided_at')
    drop_column_if_exists('invoice_payments', 'is_voided')

    if table_exists('invoice_status_tracker'):
        op.drop_index('ix_invoice_status_tracker_workspace_id', table_name='invoice_status_tracker')
        op.drop_index('ix_invoice_status_tracker_invoice_id', table_name='invoice_status_tracker')
        op.drop_table('invoice_status_tracker')

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if 'account_invoices' in inspector.get_table_names():
        indexes = {idx['name'] for idx in inspector.get_indexes('account_invoices')}
        if 'ix_account_invoices_invoice_status' in indexes:
            op.drop_index('ix_account_invoices_invoice_status', table_name='account_invoices')
    drop_column_if_exists('account_invoices', 'void_note')
    drop_column_if_exists('account_invoices', 'invoice_status')
