"""po payment due workflow stage

Revision ID: 041_po_payment_due_stage
Revises: 040_po_item_nullable_unit_price
Create Date: 2026-06-29
"""
from alembic import op

revision = '041_po_payment_due_stage'
down_revision = '040_po_item_nullable_unit_price'
branch_labels = None
depends_on = None


def upgrade():
    from sqlalchemy.orm import Session

    from app.db.seed_po_workflow import seed_po_workflow_for_all_workspaces

    session = Session(bind=op.get_bind())
    try:
        seed_po_workflow_for_all_workspaces(session)
        session.flush()
    finally:
        session.close()


def downgrade():
    pass
