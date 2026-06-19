"""Transfer order approver DAO. SECURITY: All queries MUST filter by workspace_id."""
from typing import List, Optional
from sqlalchemy.orm import Session
from app.dao.base import BaseDAO
from app.models.transfer_order_approver import TransferOrderApprover
from app.schemas.transfer_order import TransferOrderApproverCreate


class TransferOrderApproverDAO(BaseDAO[TransferOrderApprover, TransferOrderApproverCreate, TransferOrderApproverCreate]):
    def get_by_order(
        self, db: Session, *, transfer_order_id: int, workspace_id: int
    ) -> List[TransferOrderApprover]:
        return (
            db.query(TransferOrderApprover)
            .filter(
                TransferOrderApprover.transfer_order_id == transfer_order_id,
                TransferOrderApprover.workspace_id == workspace_id,
            )
            .order_by(TransferOrderApprover.assigned_at)
            .all()
        )

    def get_by_order_and_user(
        self, db: Session, *, transfer_order_id: int, user_id: int, workspace_id: int
    ) -> Optional[TransferOrderApprover]:
        return (
            db.query(TransferOrderApprover)
            .filter(
                TransferOrderApprover.transfer_order_id == transfer_order_id,
                TransferOrderApprover.user_id == user_id,
                TransferOrderApprover.workspace_id == workspace_id,
            )
            .first()
        )


transfer_order_approver_dao = TransferOrderApproverDAO(TransferOrderApprover)
