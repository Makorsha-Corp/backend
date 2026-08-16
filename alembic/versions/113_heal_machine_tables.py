"""Heal machine schema skipped by squash-adopt stamp.

Revision ID: 113_heal_machine_tables
Revises: 112_merge_heads
Create Date: 2026-08-16

Railway (2026-08-16) confirmed:
- UndefinedTable: machine_section_assignments
- UndefinedColumn: machines.factory_id

Pre-squash machines used factory_section_id only. Squash dump (and current
models) use machines.factory_id plus machine_section_assignments. Stamp to
100 did not apply that reshape.

Idempotent: no-op when column/tables already exist (fresh install / local dump).
"""
import sqlalchemy as sa
from alembic import op

from app.db.migration_helpers import (
    column_exists,
    foreign_key_constraint_exists,
    table_exists,
)

revision = "113_heal_machine_tables"
down_revision = "112_merge_heads"
branch_labels = None
depends_on = None


def _index_exists(table: str, name: str) -> bool:
    return name in {ix["name"] for ix in sa.inspect(op.get_bind()).get_indexes(table)}


def _heal_machines_factory_id() -> None:
    if not table_exists("machines") or not table_exists("factories"):
        return

    if not column_exists("machines", "factory_id"):
        op.add_column("machines", sa.Column("factory_id", sa.Integer(), nullable=True))

    if column_exists("machines", "factory_section_id") and table_exists("factory_sections"):
        op.execute(
            sa.text(
                """
                UPDATE machines AS m
                SET factory_id = fs.factory_id
                FROM factory_sections AS fs
                WHERE m.factory_id IS NULL
                  AND m.factory_section_id = fs.id
                """
            )
        )

    op.execute(
        sa.text(
            """
            UPDATE machines AS m
            SET factory_id = (
                SELECT f.id
                FROM factories AS f
                WHERE f.workspace_id = m.workspace_id
                ORDER BY f.id
                LIMIT 1
            )
            WHERE m.factory_id IS NULL
            """
        )
    )

    orphans = op.get_bind().execute(
        sa.text("SELECT COUNT(*) FROM machines WHERE factory_id IS NULL")
    ).scalar()
    if orphans:
        raise RuntimeError(
            f"{orphans} machine(s) have no factory_id and no factory in the "
            "workspace — create a factory or assign factory_section_id, then retry."
        )

    op.alter_column("machines", "factory_id", existing_type=sa.Integer(), nullable=False)

    if not foreign_key_constraint_exists("machines", "machines_factory_id_fkey"):
        op.create_foreign_key(
            "machines_factory_id_fkey",
            "machines",
            "factories",
            ["factory_id"],
            ["id"],
        )

    if not _index_exists("machines", "ix_machines_factory_id"):
        op.create_index("ix_machines_factory_id", "machines", ["factory_id"])


def _create_machine_section_assignments() -> None:
    if table_exists("machine_section_assignments"):
        return

    op.create_table(
        "machine_section_assignments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("machine_id", sa.Integer(), nullable=False),
        sa.Column("factory_section_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["machine_id"], ["machines.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["factory_section_id"], ["factory_sections.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["created_by"], ["profiles.id"]),
        sa.ForeignKeyConstraint(["updated_by"], ["profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("machine_id", name="uq_machine_section_assignment_machine"),
    )
    op.create_index(
        "ix_machine_section_assignments_workspace_id",
        "machine_section_assignments",
        ["workspace_id"],
    )
    op.create_index(
        "ix_machine_section_assignments_machine_id",
        "machine_section_assignments",
        ["machine_id"],
    )
    op.create_index(
        "ix_machine_section_assignments_factory_section_id",
        "machine_section_assignments",
        ["factory_section_id"],
    )

    if column_exists("machines", "factory_section_id"):
        op.execute(
            sa.text(
                """
                INSERT INTO machine_section_assignments
                    (workspace_id, machine_id, factory_section_id, created_at)
                SELECT m.workspace_id, m.id, m.factory_section_id, now()
                FROM machines m
                WHERE m.factory_section_id IS NOT NULL
                  AND NOT EXISTS (
                      SELECT 1
                      FROM machine_section_assignments a
                      WHERE a.machine_id = m.id
                  )
                """
            )
        )


def _create_machine_activity_events() -> None:
    if table_exists("machine_activity_events"):
        return

    op.create_table(
        "machine_activity_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("machine_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("performed_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["machine_id"], ["machines.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["performed_by"], ["profiles.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_machine_activity_events_workspace_id",
        "machine_activity_events",
        ["workspace_id"],
    )
    op.create_index(
        "ix_machine_activity_events_machine_id",
        "machine_activity_events",
        ["machine_id"],
    )
    op.create_index(
        "ix_machine_activity_events_id",
        "machine_activity_events",
        ["id"],
    )


def upgrade() -> None:
    _heal_machines_factory_id()
    _create_machine_section_assignments()
    _create_machine_activity_events()


def downgrade() -> None:
    if table_exists("machine_activity_events"):
        op.drop_index(
            "ix_machine_activity_events_id", table_name="machine_activity_events"
        )
        op.drop_index(
            "ix_machine_activity_events_machine_id",
            table_name="machine_activity_events",
        )
        op.drop_index(
            "ix_machine_activity_events_workspace_id",
            table_name="machine_activity_events",
        )
        op.drop_table("machine_activity_events")

    if table_exists("machine_section_assignments"):
        op.drop_index(
            "ix_machine_section_assignments_factory_section_id",
            table_name="machine_section_assignments",
        )
        op.drop_index(
            "ix_machine_section_assignments_machine_id",
            table_name="machine_section_assignments",
        )
        op.drop_index(
            "ix_machine_section_assignments_workspace_id",
            table_name="machine_section_assignments",
        )
        op.drop_table("machine_section_assignments")
