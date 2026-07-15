"""Payment transactions: SSLCommerz checkout ledger + event audit trail.

Revision ID: 055_payment_transactions
Revises: 054_work_order_sheet_and_recurrence
"""

import sqlalchemy as sa
from alembic import op

from app.db.migration_helpers import table_exists

revision = '055_payment_transactions'
down_revision = '054_work_order_sheet_and_recurrence'
branch_labels = None
depends_on = None


def upgrade() -> None:
    if not table_exists('payment_transactions'):
        op.create_table(
            'payment_transactions',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('workspace_id', sa.Integer(), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
            sa.Column('tran_id', sa.String(30), nullable=False, unique=True),
            sa.Column('status', sa.String(20), nullable=False, server_default='INITIATED'),
            sa.Column('amount', sa.Numeric(15, 2), nullable=False),
            sa.Column('currency', sa.String(3), nullable=False),
            sa.Column('cus_name', sa.String(255), nullable=True),
            sa.Column('cus_email', sa.String(255), nullable=True),
            sa.Column('cus_phone', sa.String(50), nullable=True),
            sa.Column('value_a', sa.String(255), nullable=True),
            sa.Column('value_b', sa.String(255), nullable=True),
            sa.Column('value_c', sa.String(255), nullable=True),
            sa.Column('value_d', sa.String(255), nullable=True),
            sa.Column('session_key', sa.String(64), nullable=True),
            sa.Column('gateway_page_url', sa.Text(), nullable=True),
            sa.Column('val_id', sa.String(512), nullable=True),
            sa.Column('risk_level', sa.Integer(), nullable=True),
            sa.Column('risk_title', sa.String(50), nullable=True),
            sa.Column('bank_tran_id', sa.String(100), nullable=True),
            sa.Column('card_type', sa.String(50), nullable=True),
            sa.Column('verify_sign', sa.String(255), nullable=True),
            sa.Column('last_ipn_payload', sa.JSON(), nullable=True),
            sa.Column('risk_resolved_by', sa.Integer(), sa.ForeignKey('profiles.id', ondelete='SET NULL'), nullable=True),
            sa.Column('risk_resolved_at', sa.DateTime(), nullable=True),
            sa.Column('risk_resolution_note', sa.Text(), nullable=True),
            sa.Column('initiated_by', sa.Integer(), sa.ForeignKey('profiles.id', ondelete='SET NULL'), nullable=True),
            sa.Column('initiated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
            sa.Column('validated_at', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        )
        op.create_index('ix_payment_transactions_workspace_id', 'payment_transactions', ['workspace_id'])
        op.create_index('ix_payment_transactions_tran_id', 'payment_transactions', ['tran_id'], unique=True)
        op.create_index('ix_payment_transactions_status', 'payment_transactions', ['status'])
        op.create_index('ix_payment_transactions_val_id', 'payment_transactions', ['val_id'])

    if not table_exists('payment_transaction_events'):
        op.create_table(
            'payment_transaction_events',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('workspace_id', sa.Integer(), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
            sa.Column(
                'payment_transaction_id', sa.Integer(),
                sa.ForeignKey('payment_transactions.id', ondelete='CASCADE'), nullable=False,
            ),
            sa.Column('event_type', sa.String(50), nullable=False),
            sa.Column('description', sa.Text(), nullable=False),
            sa.Column('metadata_json', sa.JSON(), nullable=True),
            sa.Column('performed_by', sa.Integer(), sa.ForeignKey('profiles.id', ondelete='SET NULL'), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        )
        op.create_index('ix_payment_transaction_events_workspace_id', 'payment_transaction_events', ['workspace_id'])
        op.create_index(
            'ix_payment_transaction_events_payment_transaction_id',
            'payment_transaction_events', ['payment_transaction_id'],
        )


def downgrade() -> None:
    if table_exists('payment_transaction_events'):
        op.drop_table('payment_transaction_events')
    if table_exists('payment_transactions'):
        op.drop_table('payment_transactions')
