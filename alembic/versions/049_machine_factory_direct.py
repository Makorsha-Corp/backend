"""Machines belong directly to a factory (factory_id, required); factory sections
become a purely optional organizational label, tracked in a new
machine_section_assignments table instead of a column on machines.

Revision ID: 049_machine_factory_direct
Revises: 048_production_stages
"""

import sqlalchemy as sa
from alembic import op

from app.db.migration_helpers import (
    add_column_if_not_exists,
    column_exists,
    drop_column_if_exists,
    table_exists,
)

revision = '049_machine_factory_direct'
down_revision = '048_production_stages'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add machines.factory_id (nullable for now — backfilled below).
    add_column_if_not_exists(
        'machines',
        sa.Column('factory_id', sa.Integer(), sa.ForeignKey('factories.id'), nullable=True),
    )

    # 2. Backfill from each machine's current section's factory.
    if column_exists('machines', 'factory_section_id'):
        op.execute(sa.text("""
            UPDATE machines
            SET factory_id = (
                SELECT factory_sections.factory_id FROM factory_sections
                WHERE factory_sections.id = machines.factory_section_id
            )
            WHERE factory_id IS NULL AND factory_section_id IS NOT NULL
        """))

    # 3. Now safe to enforce NOT NULL (every existing machine had a mandatory section).
    op.alter_column('machines', 'factory_id', nullable=False)
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_machines_factory_id ON machines (factory_id)"))

    # 4. New table: optional machine -> section assignment (at most one per machine).
    if not table_exists('machine_section_assignments'):
        op.create_table(
            'machine_section_assignments',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('workspace_id', sa.Integer(), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
            sa.Column('machine_id', sa.Integer(), sa.ForeignKey('machines.id', ondelete='CASCADE'), nullable=False),
            sa.Column('factory_section_id', sa.Integer(), sa.ForeignKey('factory_sections.id', ondelete='CASCADE'), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('created_by', sa.Integer(), sa.ForeignKey('profiles.id'), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.Column('updated_by', sa.Integer(), sa.ForeignKey('profiles.id'), nullable=True),
            sa.UniqueConstraint('machine_id', name='uq_machine_section_assignment_machine'),
        )
        op.create_index('ix_machine_section_assignments_workspace_id', 'machine_section_assignments', ['workspace_id'])
        op.create_index('ix_machine_section_assignments_machine_id', 'machine_section_assignments', ['machine_id'])
        op.create_index('ix_machine_section_assignments_factory_section_id', 'machine_section_assignments', ['factory_section_id'])

    # 5. Preserve every machine's current section as an assignment row.
    if column_exists('machines', 'factory_section_id'):
        op.execute(sa.text("""
            INSERT INTO machine_section_assignments (workspace_id, machine_id, factory_section_id, created_at)
            SELECT workspace_id, id, factory_section_id, now()
            FROM machines
            WHERE factory_section_id IS NOT NULL
            ON CONFLICT (machine_id) DO NOTHING
        """))

    # 6. Drop the now-unused column (and its FK/index) — Machine has zero section reference.
    op.execute(sa.text("DROP INDEX IF EXISTS ix_machines_factory_section_id"))
    drop_column_if_exists('machines', 'factory_section_id')


def downgrade() -> None:
    add_column_if_not_exists(
        'machines',
        sa.Column('factory_section_id', sa.Integer(), sa.ForeignKey('factory_sections.id'), nullable=True),
    )
    op.execute(sa.text("""
        UPDATE machines
        SET factory_section_id = (
            SELECT factory_section_id FROM machine_section_assignments
            WHERE machine_section_assignments.machine_id = machines.id
        )
    """))
    if table_exists('machine_section_assignments'):
        op.drop_table('machine_section_assignments')
    op.execute(sa.text("DROP INDEX IF EXISTS ix_machines_factory_id"))
    drop_column_if_exists('machines', 'factory_id')
