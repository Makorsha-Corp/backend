"""Per-step planned_start_at on batch stage logs.

Revision ID: 145_stage_log_planned_start_at
Revises: 144_production_batch_stage_log_items
Create Date: 2026-10-25
"""
from datetime import timedelta

import sqlalchemy as sa
from alembic import op
from sqlalchemy.orm import Session

revision = "145_stage_log_planned_start_at"
down_revision = "144_production_batch_stage_log_items"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "production_batch_stage_logs",
        sa.Column("planned_start_at", sa.DateTime(), nullable=True),
    )

    bind = op.get_bind()
    session = Session(bind=bind)
    try:
        from app.models.production_batch import ProductionBatch
        from app.models.production_batch_stage_log import ProductionBatchStageLog

        batches = (
            session.query(ProductionBatch)
            .filter(ProductionBatch.planned_start_at.isnot(None))
            .all()
        )
        for batch in batches:
            logs = (
                session.query(ProductionBatchStageLog)
                .filter(
                    ProductionBatchStageLog.batch_id == batch.id,
                    ProductionBatchStageLog.workspace_id == batch.workspace_id,
                )
                .order_by(
                    ProductionBatchStageLog.stage_order.asc(),
                    ProductionBatchStageLog.id.asc(),
                )
                .all()
            )
            cursor = batch.planned_start_at
            if cursor is None:
                continue
            for log in logs:
                log.planned_start_at = cursor
                cursor = cursor + timedelta(minutes=log.expected_duration_minutes or 0)
        session.commit()
    finally:
        session.close()


def downgrade() -> None:
    op.drop_column("production_batch_stage_logs", "planned_start_at")
