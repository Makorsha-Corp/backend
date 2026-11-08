"""Unique SKU per workspace among active catalog items (case-insensitive).

Revision ID: 133_items_unique_sku_active
Revises: 132_route_first_cleanup
"""
from alembic import op

revision = "133_items_unique_sku_active"
down_revision = "132_route_first_cleanup"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_items_workspace_sku_active
        ON items (workspace_id, lower(btrim(sku)))
        WHERE sku IS NOT NULL AND btrim(sku) <> '' AND is_active IS TRUE
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_items_workspace_sku_active")
