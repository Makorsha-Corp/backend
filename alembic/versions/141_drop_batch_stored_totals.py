"""Drop stored batch quantity totals. They are derived from steps on read.

Revision ID: 141_drop_batch_stored_totals
Revises: 140_production_batch_events
Create Date: 2026-10-05
"""
from app.db.migration_helpers import drop_column_if_exists

revision = "141_drop_batch_stored_totals"
down_revision = "140_production_batch_events"
branch_labels = None
depends_on = None

_COLUMNS = (
    "expected_output_quantity",
    "expected_duration_minutes",
    "actual_output_quantity",
    "actual_duration_minutes",
    "output_variance_quantity",
    "output_variance_percentage",
    "efficiency_percentage",
)


def upgrade() -> None:
    for column in _COLUMNS:
        drop_column_if_exists("production_batches", column)


def downgrade() -> None:
    pass
