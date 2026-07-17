"""Add work_order_schedules for staged maintenance before confirm.

Revision ID: 055_work_order_schedules
Revises: 054_work_order_sheet_and_recurrence
"""

import sqlalchemy as sa
from alembic import op

revision = '055_work_order_schedules'
down_revision = '054_work_order_sheet_and_recurrence'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'work_order_schedules',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('workspace_id', sa.Integer(), nullable=False),
        sa.Column('scheduled_date', sa.Date(), nullable=False),
        sa.Column(
            'status',
            sa.Enum('STAGED', 'CONFIRMED', 'CANCELLED', name='workorderschedulestatusenum'),
            nullable=False,
            server_default='STAGED',
        ),
        sa.Column('work_order_template_id', sa.Integer(), nullable=True),
        sa.Column('machine_id', sa.Integer(), nullable=False),
        sa.Column('factory_id', sa.Integer(), nullable=False),
        sa.Column('factory_section_id', sa.Integer(), nullable=True),
        sa.Column('work_order_type_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column(
            'priority',
            sa.Enum('LOW', 'MEDIUM', 'HIGH', 'URGENT', name='workorderpriorityenum'),
            nullable=False,
            server_default='MEDIUM',
        ),
        sa.Column('assigned_to', sa.String(255), nullable=True),
        sa.Column('work_order_id', sa.Integer(), nullable=True),
        sa.Column('confirmed_at', sa.DateTime(), nullable=True),
        sa.Column('confirmed_by', sa.Integer(), nullable=True),
        sa.Column('cancelled_at', sa.DateTime(), nullable=True),
        sa.Column('cancelled_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['cancelled_by'], ['profiles.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['confirmed_by'], ['profiles.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by'], ['profiles.id']),
        sa.ForeignKeyConstraint(['factory_id'], ['factories.id']),
        sa.ForeignKeyConstraint(['factory_section_id'], ['factory_sections.id']),
        sa.ForeignKeyConstraint(['machine_id'], ['machines.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['work_order_id'], ['work_orders.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['work_order_template_id'], ['work_order_templates.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['work_order_type_id'], ['work_order_types.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_work_order_schedules_workspace_id', 'work_order_schedules', ['workspace_id'])
    op.create_index('ix_work_order_schedules_scheduled_date', 'work_order_schedules', ['scheduled_date'])
    op.create_index('ix_work_order_schedules_status', 'work_order_schedules', ['status'])
    op.create_index('ix_work_order_schedules_machine_id', 'work_order_schedules', ['machine_id'])
    op.create_index('ix_work_order_schedules_factory_id', 'work_order_schedules', ['factory_id'])
    op.create_index(
        'uq_wo_schedule_staged_machine_date_type',
        'work_order_schedules',
        ['workspace_id', 'machine_id', 'scheduled_date', 'work_order_type_id'],
        unique=True,
        postgresql_where=sa.text("status = 'STAGED'"),
    )


def downgrade() -> None:
    op.drop_index('uq_wo_schedule_staged_machine_date_type', table_name='work_order_schedules')
    op.drop_index('ix_work_order_schedules_factory_id', table_name='work_order_schedules')
    op.drop_index('ix_work_order_schedules_machine_id', table_name='work_order_schedules')
    op.drop_index('ix_work_order_schedules_status', table_name='work_order_schedules')
    op.drop_index('ix_work_order_schedules_scheduled_date', table_name='work_order_schedules')
    op.drop_index('ix_work_order_schedules_workspace_id', table_name='work_order_schedules')
    op.drop_table('work_order_schedules')
    op.execute('DROP TYPE IF EXISTS workorderschedulestatusenum')
