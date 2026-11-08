"""Add profiles.help_guides_seen for first-visit tour state."""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

from app.db.migration_helpers import add_column_if_not_exists, drop_column_if_exists

revision = "153_profile_help_guides_seen"
down_revision = "152_work_order_soft_timing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    add_column_if_not_exists(
        "profiles",
        sa.Column("help_guides_seen", JSONB, nullable=True),
    )


def downgrade() -> None:
    drop_column_if_exists("profiles", "help_guides_seen")
