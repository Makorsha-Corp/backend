"""Strip stroke/text/stamp counts from attachment_markup_events metadata.

Revision ID: 118_strip_markup_event_stroke_metadata
Revises: 117_attachment_markup_events
Create Date: 2026-08-30
"""
from alembic import op

from app.db.migration_helpers import table_exists

revision = "118_strip_markup_event_stroke_metadata"
down_revision = "117_attachment_markup_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if not table_exists("attachment_markup_events"):
        return

    # Keep pages-only metadata to match current markup event logging.
    op.execute(
        """
        UPDATE attachment_markup_events
        SET metadata_json = json_build_object(
            'pages',
            COALESCE(metadata_json->'pages', '[]'::json)
        )
        WHERE metadata_json IS NOT NULL
        """
    )


def downgrade() -> None:
    # Historical stroke/text/stamp counts cannot be restored.
    pass
