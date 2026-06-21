"""Drop legacy order system and add order_type polymorphic columns

Revision ID: 030
Revises: 029
Create Date: 2026-06-21
"""
from alembic import op
import sqlalchemy as sa

from app.db.migration_helpers import (
    table_exists,
    column_exists,
    add_column_if_not_exists,
    drop_foreign_key_if_exists,
)

revision = '030_drop_legacy_orders'
down_revision = '029_drop_expense_order_item_account_id'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. Drop FK constraints on order_id (safe: IF EXISTS) ─────────────────
    if table_exists('account_invoices'):
        drop_foreign_key_if_exists('account_invoices', 'account_invoices_order_id_fkey')
    if table_exists('machine_item_ledger'):
        drop_foreign_key_if_exists('machine_item_ledger', 'machine_item_ledger_order_id_fkey')
    if table_exists('project_component_item_ledger'):
        drop_foreign_key_if_exists(
            'project_component_item_ledger',
            'project_component_item_ledger_order_id_fkey',
        )

    # ── 2. Add order_type companion columns (idempotent) ─────────────────────
    add_column_if_not_exists(
        'account_invoices',
        sa.Column('order_type', sa.String(30), nullable=True),
    )
    add_column_if_not_exists(
        'machine_item_ledger',
        sa.Column('order_type', sa.String(30), nullable=True),
    )
    add_column_if_not_exists(
        'project_component_item_ledger',
        sa.Column('order_type', sa.String(30), nullable=True),
    )

    # ── 3. Drop legacy order tables (CASCADE handles any residual FKs) ─────────
    for tbl in (
        'order_attachments',
        'order_part_logs',
        'order_parts_logs',
        'order_items',
        'orders',
    ):
        op.execute(sa.text(f'DROP TABLE IF EXISTS {tbl} CASCADE'))


def downgrade() -> None:
    op.create_table(
        'orders',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('workspace_id', sa.Integer(), nullable=False),
    )

    op.drop_column('account_invoices', 'order_type')
    op.drop_column('machine_item_ledger', 'order_type')
    op.drop_column('project_component_item_ledger', 'order_type')

    op.create_foreign_key(
        'account_invoices_order_id_fkey', 'account_invoices', 'orders',
        ['order_id'], ['id'], ondelete='SET NULL',
    )
    op.create_foreign_key(
        'machine_item_ledger_order_id_fkey', 'machine_item_ledger', 'orders',
        ['order_id'], ['id'], ondelete='SET NULL',
    )
    op.create_foreign_key(
        'project_component_item_ledger_order_id_fkey',
        'project_component_item_ledger', 'orders',
        ['order_id'], ['id'], ondelete='SET NULL',
    )
