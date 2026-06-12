"""
Idempotent DDL for purchase_orders.stage (code-defined PO workflow).

Runs at app startup when Alembic did not apply revisions 024/025 (e.g. Railway
deploy). Schema only — no data backfill.
"""
import logging

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def _table_names(inspector) -> set[str]:
    return set(inspector.get_table_names())


def _column_names(inspector, table: str) -> set[str]:
    return {c['name'] for c in inspector.get_columns(table)}


def ensure_po_stage_schema(db: Session) -> None:
    bind = db.get_bind()
    inspector = inspect(bind)
    tables = _table_names(inspector)

    if 'purchase_orders' not in tables:
        logger.info('PO stage schema ensure skipped — purchase_orders table missing')
        return

    columns = _column_names(inspector, 'purchase_orders')

    if 'stage' not in columns:
        logger.warning('purchase_orders.stage missing — applying startup DDL')
        db.execute(
            text(
                "ALTER TABLE purchase_orders "
                "ADD COLUMN stage VARCHAR(20) NOT NULL DEFAULT 'Draft'"
            )
        )
        db.execute(
            text('ALTER TABLE purchase_orders ALTER COLUMN stage DROP DEFAULT')
        )
        db.execute(
            text(
                'CREATE INDEX IF NOT EXISTS ix_purchase_orders_stage '
                'ON purchase_orders (stage)'
            )
        )

    columns = _column_names(inspect(bind), 'purchase_orders')

    if 'current_status_id' in columns:
        logger.warning('purchase_orders.current_status_id present — dropping legacy column')
        db.execute(
            text(
                'ALTER TABLE purchase_orders '
                'DROP CONSTRAINT IF EXISTS purchase_orders_current_status_id_fkey'
            )
        )
        db.execute(text('ALTER TABLE purchase_orders DROP COLUMN current_status_id'))

    columns = _column_names(inspect(bind), 'purchase_orders')

    if 'order_workflow_id' in columns:
        logger.warning('purchase_orders.order_workflow_id present — dropping legacy column')
        db.execute(
            text(
                'ALTER TABLE purchase_orders '
                'DROP CONSTRAINT IF EXISTS purchase_orders_order_workflow_id_fkey'
            )
        )
        db.execute(text('ALTER TABLE purchase_orders DROP COLUMN order_workflow_id'))

    if 'order_workflows' in tables:
        db.execute(text("DELETE FROM order_workflows WHERE type = 'purchase'"))

    logger.info('PO stage schema ensure complete')
