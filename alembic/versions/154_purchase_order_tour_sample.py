"""Flag one hidden purchase-order tour sample per workspace."""
import sqlalchemy as sa
from alembic import op

from app.db.migration_helpers import add_column_if_not_exists, column_exists, drop_column_if_exists

revision = "154_purchase_order_tour_sample"
down_revision = "153_profile_help_guides_seen"
branch_labels = None
depends_on = None

INDEX_NAME = "uq_purchase_orders_tour_sample_workspace"


def upgrade() -> None:
    add_column_if_not_exists(
        "purchase_orders",
        sa.Column("is_tour_sample", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {idx["name"] for idx in inspector.get_indexes("purchase_orders")}
    if INDEX_NAME not in existing:
        op.create_index(
            INDEX_NAME,
            "purchase_orders",
            ["workspace_id"],
            unique=True,
            postgresql_where=sa.text("is_tour_sample IS TRUE"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {idx["name"] for idx in inspector.get_indexes("purchase_orders")}
    if INDEX_NAME in existing:
        op.drop_index(INDEX_NAME, table_name="purchase_orders")
    if column_exists("purchase_orders", "is_tour_sample"):
        drop_column_if_exists("purchase_orders", "is_tour_sample")
