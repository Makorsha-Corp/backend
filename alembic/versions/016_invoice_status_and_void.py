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

revision = '016_invoice_status_and_void'
down_revision = '015_po_optional_supplier'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # account_invoices — lifecycle status + void note
    op.add_column('account_invoices', sa.Column(
        'invoice_status', sa.String(20), nullable=False, server_default='draft'
    ))
    op.add_column('account_invoices', sa.Column('void_note', sa.Text(), nullable=True))
    op.create_index('ix_account_invoices_invoice_status', 'account_invoices', ['invoice_status'])

    # invoice_status_tracker — append-only log of invoice status transitions
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

    # invoice_payments — void support
    op.add_column('invoice_payments', sa.Column(
        'is_voided', sa.Boolean(), nullable=False, server_default='false'
    ))
    op.add_column('invoice_payments', sa.Column('voided_at', sa.DateTime(), nullable=True))
    op.add_column('invoice_payments', sa.Column('voided_by', sa.Integer(), nullable=True))
    op.add_column('invoice_payments', sa.Column('void_note', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('invoice_payments', 'void_note')
    op.drop_column('invoice_payments', 'voided_by')
    op.drop_column('invoice_payments', 'voided_at')
    op.drop_column('invoice_payments', 'is_voided')

    op.drop_index('ix_invoice_status_tracker_workspace_id', table_name='invoice_status_tracker')
    op.drop_index('ix_invoice_status_tracker_invoice_id', table_name='invoice_status_tracker')
    op.drop_table('invoice_status_tracker')

    op.drop_index('ix_account_invoices_invoice_status', table_name='account_invoices')
    op.drop_column('account_invoices', 'void_note')
    op.drop_column('account_invoices', 'invoice_status')
