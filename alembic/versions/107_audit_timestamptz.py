"""Convert key audit datetime columns to TIMESTAMPTZ (UTC semantics).

Revision ID: 107_audit_timestamptz
Revises: 106_profile_timezone
Create Date: 2026-08-11
"""
from alembic import op

revision = "107_audit_timestamptz"
down_revision = "106_profile_timezone"
branch_labels = None
depends_on = None

# Existing naive values are stored as UTC — AT TIME ZONE 'UTC' preserves instants.
_AUDIT_COLUMNS = (
    ("notifications", "created_at"),
    ("notifications", "read_at"),
    ("workspace_audit_logs", "created_at"),
    ("attachments", "uploaded_at"),
    ("attachments", "deleted_at"),
    ("discussions", "created_at"),
)


def _to_timestamptz(table: str, column: str) -> None:
    op.execute(
        f"""
        ALTER TABLE {table}
        ALTER COLUMN {column} TYPE TIMESTAMPTZ
        USING CASE
            WHEN {column} IS NULL THEN NULL
            ELSE {column} AT TIME ZONE 'UTC'
        END
        """
    )


def _to_timestamp(table: str, column: str) -> None:
    op.execute(
        f"""
        ALTER TABLE {table}
        ALTER COLUMN {column} TYPE TIMESTAMP WITHOUT TIME ZONE
        USING {column} AT TIME ZONE 'UTC'
        """
    )


def upgrade() -> None:
    for table, column in _AUDIT_COLUMNS:
        _to_timestamptz(table, column)


def downgrade() -> None:
    for table, column in reversed(_AUDIT_COLUMNS):
        _to_timestamp(table, column)
