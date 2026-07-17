"""Payment transaction DAO operations"""
from datetime import datetime
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from app.dao.base import BaseDAO
from app.models.payment_transaction import PaymentTransaction
from app.models.profile import Profile
from app.schemas.payment_transaction import InitiatePaymentRequest


class PaymentTransactionDAO(BaseDAO[PaymentTransaction, InitiatePaymentRequest, dict]):
    """DAO operations for PaymentTransaction model.

    Note: the public gateway-callback endpoints (success/fail/cancel/ipn) have no
    X-Workspace-ID header — SSLCommerz never sends one — so several lookups here
    are deliberately *not* workspace-scoped. They resolve the workspace from the
    tran_id itself, which is what the caller then uses for authorization checks.
    """

    def get_by_tran_id(self, db: Session, *, tran_id: str) -> Optional[PaymentTransaction]:
        return db.query(PaymentTransaction).filter(PaymentTransaction.tran_id == tran_id).first()

    def get_by_tran_id_for_update(self, db: Session, *, tran_id: str) -> Optional[PaymentTransaction]:
        """Row-locks the transaction for the idempotency wall. Caller must be
        inside a transaction; lock is released on commit/rollback."""
        return (
            db.query(PaymentTransaction)
            .filter(PaymentTransaction.tran_id == tran_id)
            .with_for_update()
            .one_or_none()
        )

    def get_by_id_and_workspace_with_initiator(
        self, db: Session, *, id: int, workspace_id: int
    ) -> Optional[Tuple[PaymentTransaction, Optional[str]]]:
        row = (
            db.query(PaymentTransaction, Profile.name.label("initiated_by_name"))
            .outerjoin(Profile, PaymentTransaction.initiated_by == Profile.id)
            .filter(PaymentTransaction.id == id, PaymentTransaction.workspace_id == workspace_id)
            .first()
        )
        if row is None:
            return None
        return row

    def get_by_tran_id_and_workspace_with_initiator(
        self, db: Session, *, tran_id: str, workspace_id: int
    ) -> Optional[Tuple[PaymentTransaction, Optional[str]]]:
        row = (
            db.query(PaymentTransaction, Profile.name.label("initiated_by_name"))
            .outerjoin(Profile, PaymentTransaction.initiated_by == Profile.id)
            .filter(PaymentTransaction.tran_id == tran_id, PaymentTransaction.workspace_id == workspace_id)
            .first()
        )
        if row is None:
            return None
        return row

    def list_by_workspace_with_initiator(
        self, db: Session, *, workspace_id: int, skip: int = 0, limit: int = 100
    ) -> List[Tuple[PaymentTransaction, Optional[str]]]:
        rows = (
            db.query(PaymentTransaction, Profile.name.label("initiated_by_name"))
            .outerjoin(Profile, PaymentTransaction.initiated_by == Profile.id)
            .filter(PaymentTransaction.workspace_id == workspace_id)
            .order_by(PaymentTransaction.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return [(txn, name) for txn, name in rows]

    def get_stuck_initiated(self, db: Session, *, older_than: datetime, limit: int = 200) -> List[PaymentTransaction]:
        """For the reconciliation sweep — INITIATED rows past the timeout window,
        across all workspaces."""
        return (
            db.query(PaymentTransaction)
            .filter(PaymentTransaction.status == "INITIATED", PaymentTransaction.initiated_at < older_than)
            .order_by(PaymentTransaction.initiated_at.asc())
            .limit(limit)
            .all()
        )


payment_transaction_dao = PaymentTransactionDAO(PaymentTransaction)
