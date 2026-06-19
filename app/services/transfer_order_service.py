"""Transfer Order Service - transaction orchestration"""
from typing import List, Optional
from sqlalchemy.orm import Session

from app.services.base_service import BaseService
from app.managers.transfer_order_manager import transfer_order_manager
from app.models.transfer_order import TransferOrder
from app.models.transfer_order_item import TransferOrderItem
from app.schemas.transfer_order import (
    TransferOrderCreate, TransferOrderUpdate,
    TransferOrderItemCreate, TransferOrderItemUpdate,
)


class TransferOrderService(BaseService):
    """Service for transfer order workflows. Handles commit/rollback."""

    def __init__(self):
        super().__init__()
        self.manager = transfer_order_manager

    def create_transfer_order(
        self, db: Session, to_in: TransferOrderCreate,
        workspace_id: int, user_id: int
    ) -> TransferOrder:
        try:
            record = self.manager.create_transfer_order(db, data=to_in, workspace_id=workspace_id, user_id=user_id)
            self._commit_transaction(db)
            db.refresh(record)
            return record
        except Exception:
            self._rollback_transaction(db)
            raise

    def update_transfer_order(
        self, db: Session, to_id: int, to_in: TransferOrderUpdate,
        workspace_id: int, user_id: int
    ) -> TransferOrder:
        try:
            record = self.manager.update_transfer_order(db, to_id=to_id, data=to_in, workspace_id=workspace_id, user_id=user_id)
            self._commit_transaction(db)
            db.refresh(record)
            return record
        except Exception:
            self._rollback_transaction(db)
            raise

    def get_transfer_order(self, db: Session, to_id: int, workspace_id: int) -> TransferOrder:
        return self.manager.get_transfer_order(db, to_id, workspace_id)

    def list_transfer_orders(
        self, db: Session, workspace_id: int,
        skip: int = 0, limit: int = 100
    ) -> List[TransferOrder]:
        return self.manager.list_transfer_orders(
            db, workspace_id=workspace_id,
            skip=skip, limit=limit
        )

    def delete_transfer_order(self, db: Session, to_id: int, workspace_id: int) -> None:
        try:
            self.manager.delete_transfer_order(db, to_id=to_id, workspace_id=workspace_id)
            self._commit_transaction(db)
        except Exception:
            self._rollback_transaction(db)
            raise

    def mark_order_complete(
        self, db: Session, to_id: int, workspace_id: int, user_id: int
    ) -> TransferOrder:
        try:
            record = self.manager.mark_order_complete(
                db, to_id=to_id, workspace_id=workspace_id, user_id=user_id
            )
            self._commit_transaction(db)
            db.refresh(record)
            return record
        except Exception:
            self._rollback_transaction(db)
            raise

    # ─── Items ─────────────────────────────────────────────────
    def add_item(
        self, db: Session, to_id: int, item_in: TransferOrderItemCreate,
        workspace_id: int, user_id: int,
    ) -> TransferOrderItem:
        try:
            record = self.manager.add_item(
                db, to_id=to_id, data=item_in, workspace_id=workspace_id, user_id=user_id
            )
            self._commit_transaction(db)
            db.refresh(record)
            return record
        except Exception:
            self._rollback_transaction(db)
            raise

    def update_item(
        self, db: Session, item_id: int, item_in: TransferOrderItemUpdate,
        workspace_id: int, user_id: int
    ) -> TransferOrderItem:
        try:
            record = self.manager.update_item(db, item_id=item_id, data=item_in, workspace_id=workspace_id, user_id=user_id)
            self._commit_transaction(db)
            db.refresh(record)
            return record
        except Exception:
            self._rollback_transaction(db)
            raise

    def remove_item(self, db: Session, item_id: int, workspace_id: int, user_id: int) -> TransferOrderItem:
        try:
            record = self.manager.remove_item(db, item_id=item_id, workspace_id=workspace_id, user_id=user_id)
            self._commit_transaction(db)
            return record
        except Exception:
            self._rollback_transaction(db)
            raise

    def get_items(self, db: Session, to_id: int, workspace_id: int) -> List[TransferOrderItem]:
        return self.manager.get_items(db, to_id, workspace_id)

    # ─── Events ────────────────────────────────────────────────
    def list_events(self, db: Session, to_id: int, workspace_id: int):
        return self.manager.list_events(db, to_id=to_id, workspace_id=workspace_id)

    # ─── Approvers ─────────────────────────────────────────────
    def list_approvers(self, db: Session, to_id: int, workspace_id: int):
        return self.manager.list_approvers(db, to_id=to_id, workspace_id=workspace_id)

    def approval_summary_for(self, db: Session, to_id: int, workspace_id: int):
        to = self.manager.get_transfer_order(db, to_id=to_id, workspace_id=workspace_id)
        return self.manager.approval_summary(db, to)

    def add_approver(self, db: Session, to_id: int, user_id: int, workspace_id: int, assigned_by: int):
        try:
            record = self.manager.add_approver(
                db, to_id=to_id, user_id=user_id, workspace_id=workspace_id, assigned_by=assigned_by
            )
            self._commit_transaction(db)
            db.refresh(record)
            return record
        except Exception:
            self._rollback_transaction(db)
            raise

    def remove_approver(
        self, db: Session, to_id: int, user_id: int, workspace_id: int, performed_by: Optional[int] = None
    ) -> None:
        try:
            self.manager.remove_approver(
                db, to_id=to_id, user_id=user_id, workspace_id=workspace_id, performed_by=performed_by
            )
            self._commit_transaction(db)
        except Exception:
            self._rollback_transaction(db)
            raise

    def set_approval(self, db: Session, to_id: int, user_id: int, workspace_id: int, approved: bool):
        try:
            record = self.manager.set_approval(
                db, to_id=to_id, user_id=user_id, workspace_id=workspace_id, approved=approved
            )
            self._commit_transaction(db)
            db.refresh(record)
            return record
        except Exception:
            self._rollback_transaction(db)
            raise


transfer_order_service = TransferOrderService()
