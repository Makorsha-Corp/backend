"""Add voided fields to purchase_orders.

Revision ID: 037_purchase_order_void
Revises: 036_invoice_items_events
Create Date: 2026-06-25
"""
from alembic import op
import sqlalchemy as sa


revision = '037_purchase_order_void'
down_revision = '036_invoice_items_events'
branch_labels = None
depends_on = None


def add_column_if_not_exists(table, column):
    from alembic.operations import Operations
    import sqlalchemy as sa
    from sqlalchemy import inspect
    conn = op.get_bind()
    insp = sa.inspect(conn)
    cols = [c['name'] for c in insp.get_columns(table)]
    if column.name not in cols:
        op.add_column(table, column)


def upgrade():
    add_column_if_not_exists(
        'purchase_orders',
        sa.Column('voided', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    add_column_if_not_exists(
        'purchase_orders',
        sa.Column('void_note', sa.Text(), nullable=True),
    )
    add_column_if_not_exists(
        'purchase_orders',
        sa.Column('voided_at', sa.DateTime(), nullable=True),
    )
    add_column_if_not_exists(
        'purchase_orders',
        sa.Column('voided_by', sa.Integer(), sa.ForeignKey('profiles.id', ondelete='SET NULL'), nullable=True),
    )


def downgrade():
    for col in ('voided_by', 'voided_at', 'void_note', 'voided'):
        try:
            op.drop_column('purchase_orders', col)
        except Exception:
            pass
