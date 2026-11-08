"""profile ui_language preference

Revision ID: 155_profile_ui_language
Revises: 154_purchase_order_tour_sample
Create Date: 2026-11-08

"""
from alembic import op
import sqlalchemy as sa


revision = "155_profile_ui_language"
down_revision = "154_purchase_order_tour_sample"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "profiles",
        sa.Column("ui_language", sa.String(length=2), nullable=False, server_default=sa.text("'en'")),
    )


def downgrade() -> None:
    op.drop_column("profiles", "ui_language")
