"""Drop sales_orders.quotation_sent_date — field removed entirely from the sales flow.

Revision ID: 104_drop_so_quotation_sent
Revises: 103_waitlist_signup_fields
Create Date: 2026-08-08
"""
from app.db.migration_helpers import drop_column_if_exists

revision = "104_drop_so_quotation_sent"
down_revision = "103_waitlist_signup_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    drop_column_if_exists("sales_orders", "quotation_sent_date")


def downgrade() -> None:
    import sqlalchemy as sa
    from alembic import op

    op.add_column("sales_orders", sa.Column("quotation_sent_date", sa.Date(), nullable=True))
