"""Backfill Production Waste and Byproduct system item tags for all workspaces.

Revision ID: 134_items_waste_byproduct_tags
Revises: 133_items_unique_sku_active
"""
from alembic import op
from sqlalchemy.orm import sessionmaker

revision = "134_items_waste_byproduct_tags"
down_revision = "133_items_unique_sku_active"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.db.seed_default_tags import seed_default_tags
    from app.models.workspace import Workspace

    bind = op.get_bind()
    Session = sessionmaker(bind=bind)
    session = Session()
    try:
        workspace_ids = [row[0] for row in session.query(Workspace.id).all()]
        for workspace_id in workspace_ids:
            seed_default_tags(session, workspace_id=workspace_id)
        session.commit()
    finally:
        session.close()


def downgrade() -> None:
    pass
