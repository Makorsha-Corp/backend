"""Add item name_normalized column and pg_trgm index for similar-name lookup.

Revision ID: 047_item_name_normalized
Revises: 046_expense_order_void_fields
"""

import sqlalchemy as sa
from alembic import op

from app.db.migration_helpers import add_column_if_not_exists, column_exists, drop_column_if_exists

revision = "047_item_name_normalized"
down_revision = "046_expense_order_void_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))

    add_column_if_not_exists(
        "items",
        sa.Column("name_normalized", sa.String(), nullable=True),
    )

    if column_exists("items", "name_normalized"):
        from sqlalchemy.orm import Session

        from app.models.item import Item
        from app.utils.item_name_normalize import normalize_item_name

        session = Session(bind=op.get_bind())
        try:
            items = session.query(Item.id, Item.name).all()
            for item_id, item_name in items:
                session.query(Item).filter(Item.id == item_id).update(
                    {"name_normalized": normalize_item_name(item_name or "")},
                    synchronize_session=False,
                )
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

        op.alter_column("items", "name_normalized", nullable=False)

        op.execute(
            sa.text(
                "CREATE INDEX IF NOT EXISTS ix_items_name_normalized_trgm "
                "ON items USING gin (name_normalized gin_trgm_ops)"
            )
        )
        op.execute(
            sa.text(
                "CREATE INDEX IF NOT EXISTS ix_items_workspace_active "
                "ON items (workspace_id, is_active)"
            )
        )


def downgrade() -> None:
    op.execute(sa.text("DROP INDEX IF EXISTS ix_items_workspace_active"))
    op.execute(sa.text("DROP INDEX IF EXISTS ix_items_name_normalized_trgm"))
    drop_column_if_exists("items", "name_normalized")
