"""Drop deprecated machines.next_maintenance_* columns.

Revision ID: 059_drop_machine_next_maintenance
Revises: 058_work_order_planned_date
Create Date: 2026-07-24
"""

from alembic import op
import sqlalchemy as sa

revision = '059_drop_machine_next_maintenance'
down_revision = '058_work_order_planned_date'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column('machines', 'next_maintenance_note')
    op.drop_column('machines', 'next_maintenance_schedule')
    op.create_index('ix_work_orders_planned_date', 'work_orders', ['planned_date'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_work_orders_planned_date', table_name='work_orders')
    op.add_column('machines', sa.Column('next_maintenance_schedule', sa.Date(), nullable=True))
    op.add_column('machines', sa.Column('next_maintenance_note', sa.Text(), nullable=True))
