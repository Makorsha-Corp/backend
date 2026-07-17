"""Work order sheet workflow: approver slots, template recurrence, machine/section defaults.

Revision ID: 054_work_order_sheet_and_recurrence
Revises: 049_machine_factory_direct
"""

import sqlalchemy as sa
from alembic import op

from app.db.migration_helpers import column_exists

revision = '054_work_order_sheet_and_recurrence'
down_revision = '049_machine_factory_direct'
branch_labels = None
depends_on = None


def upgrade() -> None:
    if not column_exists('work_order_approvers', 'approver_slot'):
        op.add_column(
            'work_order_approvers',
            sa.Column('approver_slot', sa.String(32), nullable=True),
        )
    if not column_exists('work_order_template_approvers', 'approver_slot'):
        op.add_column(
            'work_order_template_approvers',
            sa.Column('approver_slot', sa.String(32), nullable=True),
        )

    for col, col_type in [
        ('is_recurring', sa.Boolean()),
        ('recurrence_type', sa.String(50)),
        ('recurrence_day', sa.Integer()),
        ('next_generation_date', sa.Date()),
        ('auto_generate', sa.Boolean()),
        ('default_factory_section_id', sa.Integer()),
        ('default_machine_id', sa.Integer()),
    ]:
        if not column_exists('work_order_templates', col):
            kwargs = {'nullable': True}
            if col == 'is_recurring':
                kwargs = {'nullable': False, 'server_default': sa.text('false')}
            elif col == 'auto_generate':
                kwargs = {'nullable': False, 'server_default': sa.text('false')}
            op.add_column('work_order_templates', sa.Column(col, col_type, **kwargs))

    if column_exists('work_order_templates', 'default_factory_section_id'):
        op.create_foreign_key(
            'fk_wo_templates_default_section',
            'work_order_templates',
            'factory_sections',
            ['default_factory_section_id'],
            ['id'],
            ondelete='SET NULL',
        )
    if column_exists('work_order_templates', 'default_machine_id'):
        op.create_foreign_key(
            'fk_wo_templates_default_machine',
            'work_order_templates',
            'machines',
            ['default_machine_id'],
            ['id'],
            ondelete='SET NULL',
        )


def downgrade() -> None:
    for fk in ('fk_wo_templates_default_machine', 'fk_wo_templates_default_section'):
        try:
            op.drop_constraint(fk, 'work_order_templates', type_='foreignkey')
        except Exception:
            pass

    for table, col in [
        ('work_order_approvers', 'approver_slot'),
        ('work_order_template_approvers', 'approver_slot'),
    ]:
        if column_exists(table, col):
            op.drop_column(table, col)

    for col in (
        'default_machine_id',
        'default_factory_section_id',
        'auto_generate',
        'next_generation_date',
        'recurrence_day',
        'recurrence_type',
        'is_recurring',
    ):
        if column_exists('work_order_templates', col):
            op.drop_column('work_order_templates', col)
