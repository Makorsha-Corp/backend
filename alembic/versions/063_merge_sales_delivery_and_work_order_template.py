"""Merge sales delivery methods and work order template recurrence branches.

Revision ID: 063_merge_sales_delivery_and_work_order_template
Revises: 058_delivery_methods_and_requires_delivery, 062_work_order_template_recurrence_range
Create Date: 2026-07-27
"""

revision = '063_merge_sales_delivery_and_work_order_template'
down_revision = ('058_delivery_methods_and_requires_delivery', '062_work_order_template_recurrence_range')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
