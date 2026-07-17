"""Payment Transaction Service — transaction boundaries around the SSLCommerz checkout flow."""
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.dao.payment_transaction import payment_transaction_dao
from app.dao.payment_transaction_event import payment_transaction_event_dao
from app.managers.payment_transaction_manager import payment_transaction_manager
from app.models.payment_transaction import PaymentTransaction
from app.models.profile import Profile
from app.schemas.payment_transaction import (
    InitiatePaymentRequest,
    InitiatePaymentResponse,
    PaymentTransactionDetailResponse,
    PaymentTransactionEventResponse,
    PaymentTransactionResponse,
)
from app.services.base_service import BaseService


def _to_response(txn: PaymentTransaction, initiated_by_name: Optional[str] = None) -> PaymentTransactionResponse:
    return PaymentTransactionResponse.model_validate(txn).model_copy(update={"initiated_by_name": initiated_by_name})


class PaymentTransactionService(BaseService):
    def __init__(self):
        super().__init__()
        self.manager = payment_transaction_manager

    def initiate_payment(
        self, db: Session, *, workspace_id: int, user: Profile, request: InitiatePaymentRequest
    ) -> InitiatePaymentResponse:
        try:
            txn = self.manager.initiate_payment(db, workspace_id=workspace_id, user=user, request=request)
            self._commit_transaction(db)
            db.refresh(txn)
            return InitiatePaymentResponse(
                tran_id=txn.tran_id, status=txn.status, gateway_page_url=txn.gateway_page_url
            )
        except Exception:
            self._rollback_transaction(db)
            raise

    def handle_gateway_callback(self, db: Session, *, tran_id: str, val_id: str, source: str) -> PaymentTransaction:
        try:
            txn = self.manager.finalize_from_gateway(db, tran_id=tran_id, val_id=val_id, source=source)
            self._commit_transaction(db)
            db.refresh(txn)
            return txn
        except Exception:
            self._rollback_transaction(db)
            raise

    def handle_terminal_without_validation(
        self, db: Session, *, tran_id: str, terminal_status: str, source: str
    ) -> PaymentTransaction:
        try:
            txn = self.manager.mark_terminal_without_validation(
                db, tran_id=tran_id, terminal_status=terminal_status, source=source
            )
            self._commit_transaction(db)
            db.refresh(txn)
            return txn
        except Exception:
            self._rollback_transaction(db)
            raise

    def resolve_risk(
        self, db: Session, *, transaction_id: int, workspace_id: int, user_id: int, approve: bool, note: str
    ) -> PaymentTransactionResponse:
        try:
            txn = self.manager.resolve_risk(
                db, transaction_id=transaction_id, workspace_id=workspace_id,
                user_id=user_id, approve=approve, note=note,
            )
            self._commit_transaction(db)
            db.refresh(txn)
            return _to_response(txn)
        except Exception:
            self._rollback_transaction(db)
            raise

    def get_transaction_by_tran_id(
        self, db: Session, *, tran_id: str, workspace_id: int
    ) -> PaymentTransactionDetailResponse:
        row = payment_transaction_dao.get_by_tran_id_and_workspace_with_initiator(
            db, tran_id=tran_id, workspace_id=workspace_id
        )
        if row is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"Payment transaction {tran_id} not found")
        txn, initiated_by_name = row
        events = payment_transaction_event_dao.get_by_payment_transaction(db, payment_transaction_id=txn.id)
        base = _to_response(txn, initiated_by_name)
        return PaymentTransactionDetailResponse(
            **base.model_dump(),
            events=[PaymentTransactionEventResponse.model_validate(e) for e in events],
        )

    def list_transactions(
        self, db: Session, *, workspace_id: int, skip: int = 0, limit: int = 100
    ) -> List[PaymentTransactionResponse]:
        rows = payment_transaction_dao.list_by_workspace_with_initiator(
            db, workspace_id=workspace_id, skip=skip, limit=limit
        )
        return [_to_response(txn, name) for txn, name in rows]


payment_transaction_service = PaymentTransactionService()
