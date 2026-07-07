"""Replace the fixed work_type enum with a user-managed, per-workspace
work_order_types lookup table.

Revision ID: 050_work_order_types
Revises: 049_work_order_drop_approved_status
"""

import sqlalchemy as sa
from alembic import op

from app.db.migration_helpers import (
    column_exists,
    create_unique_constraint_if_not_exists,
    table_exists,
)

revision = '050_work_order_types'
down_revision = '049_work_order_drop_approved_status'
branch_labels = None
depends_on = None

DEFAULT_TYPE_NAMES = [
    'Maintenance', 'Inspection', 'Installation', 'Repair',
    'Calibration', 'Overhaul', 'Fabrication', 'Other',
]


def upgrade() -> None:
    if not table_exists('work_order_types'):
        op.create_table(
            'work_order_types',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('workspace_id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('created_by', sa.Integer(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.Column('updated_by', sa.Integer(), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column('deleted_at', sa.DateTime(), nullable=True),
            sa.Column('deleted_by', sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['created_by'], ['profiles.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['updated_by'], ['profiles.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['deleted_by'], ['profiles.id'], ondelete='SET NULL'),
        )
        op.create_index('ix_work_order_types_workspace_id', 'work_order_types', ['workspace_id'])

    create_unique_constraint_if_not_exists(
        'work_order_types', 'uq_wo_type_workspace_name', ['workspace_id', 'name'],
    )

    # Seed the default set for every existing workspace (idempotent).
    names_values = ', '.join(f"('{name}')" for name in DEFAULT_TYPE_NAMES)
    op.execute(
        sa.text(
            f"""
            INSERT INTO work_order_types (workspace_id, name, created_at, is_active, is_deleted)
            SELECT w.id, t.name, now(), true, false
            FROM workspaces w
            CROSS JOIN (VALUES {names_values}) AS t(name)
            WHERE NOT EXISTS (
              SELECT 1 FROM work_order_types wot
              WHERE wot.workspace_id = w.id AND wot.name = t.name
            );
            """
        )
    )

    if column_exists('work_orders', 'work_type'):
        op.add_column(
            'work_orders',
            sa.Column(
                'work_order_type_id', sa.Integer(),
                sa.ForeignKey('work_order_types.id', ondelete='RESTRICT'),
                nullable=True,
            ),
        )
        # Backfill by matching the old enum value's name to the seeded row of the same name
        # in that work order's own workspace.
        op.execute(
            sa.text(
                """
                UPDATE work_orders wo
                SET work_order_type_id = wot.id
                FROM work_order_types wot
                WHERE wot.workspace_id = wo.workspace_id
                  AND upper(wot.name) = wo.work_type::text
                  AND wo.work_order_type_id IS NULL;
                """
            )
        )
        op.execute(sa.text("ALTER TABLE work_orders ALTER COLUMN work_order_type_id SET NOT NULL"))
        op.drop_column('work_orders', 'work_type')

    op.execute(sa.text('DROP TYPE IF EXISTS worktypeenum'))


def downgrade() -> None:
    if not column_exists('work_orders', 'work_type'):
        op.execute(
            sa.text(
                "CREATE TYPE worktypeenum AS ENUM "
                "('MAINTENANCE','INSPECTION','INSTALLATION','REPAIR','CALIBRATION','OVERHAUL','FABRICATION','OTHER')"
            )
        )
        op.add_column('work_orders', sa.Column('work_type', sa.Enum(name='worktypeenum'), nullable=True))
        op.execute(
            sa.text(
                """
                UPDATE work_orders wo
                SET work_type = upper(wot.name)::worktypeenum
                FROM work_order_types wot
                WHERE wot.id = wo.work_order_type_id;
                """
            )
        )
        op.execute(sa.text("ALTER TABLE work_orders ALTER COLUMN work_type SET NOT NULL"))

    if column_exists('work_orders', 'work_order_type_id'):
        op.drop_column('work_orders', 'work_order_type_id')
