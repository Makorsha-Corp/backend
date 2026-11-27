"""Attachment ledger DAO — workspace-scoped, append-only."""
from datetime import datetime

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.dao.base import BaseDAO
from app.models.attachment_ledger import AttachmentLedger
from app.schemas.attachment_ledger import AttachmentLedgerCreate, AttachmentLedgerUpdate


class AttachmentLedgerDAO(BaseDAO[AttachmentLedger, AttachmentLedgerCreate, AttachmentLedgerUpdate]):
    """DAO for attachment ledger entries."""

    def get_by_workspace(
        self,
        db: Session,
        *,
        workspace_id: int,
        attachment_id: int | None = None,
        entity_type: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        transaction_type: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[AttachmentLedger]:
        query = db.query(AttachmentLedger).filter(AttachmentLedger.workspace_id == workspace_id)
        if attachment_id is not None:
            query = query.filter(AttachmentLedger.attachment_id == attachment_id)
        if entity_type:
            query = query.filter(AttachmentLedger.entity_type == entity_type)
        if transaction_type:
            query = query.filter(AttachmentLedger.transaction_type == transaction_type)
        if start_date is not None:
            query = query.filter(AttachmentLedger.performed_at >= start_date)
        if end_date is not None:
            query = query.filter(AttachmentLedger.performed_at <= end_date)
        return (
            query.order_by(desc(AttachmentLedger.performed_at))
            .offset(skip)
            .limit(limit)
            .all()
        )


attachment_ledger_dao = AttachmentLedgerDAO(AttachmentLedger)
