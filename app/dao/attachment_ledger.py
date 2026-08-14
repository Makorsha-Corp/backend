"""Attachment ledger DAO — workspace-scoped, append-only."""
from datetime import datetime
from typing import List, Optional

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
        attachment_id: Optional[int] = None,
        entity_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        transaction_type: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[AttachmentLedger]:
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
