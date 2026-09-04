"""Add profiles.saved_stamp for per-user stamp overlay assets."""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

from app.db.migration_helpers import add_column_if_not_exists, drop_column_if_exists

revision = "116_profile_saved_stamp"
down_revision = "115_platform_admin"
branch_labels = None
depends_on = None


def upgrade() -> None:
    add_column_if_not_exists(
        "profiles",
        sa.Column("saved_stamp", JSONB, nullable=True),
    )


def downgrade() -> None:
    drop_column_if_exists("profiles", "saved_stamp")
