"""Merge sales delivery/work order template branch and work order item soft-delete branch.

Revision ID: 064_merge_sales_delivery_and_work_order_item_soft_delete
Revises: 063_merge_sales_delivery_and_work_order_template, 063_work_order_item_soft_delete
Create Date: 2026-07-28
"""

revision = '064_merge_sales_delivery_and_work_order_item_soft_delete'
down_revision = ('063_merge_sales_delivery_and_work_order_template', '063_work_order_item_soft_delete')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
