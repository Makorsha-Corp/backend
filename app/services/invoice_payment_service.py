"""Invoice Payment Service for orchestrating payment workflows"""
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.dao.invoice_payment import invoice_payment_dao
from app.managers.invoice_payment_manager import invoice_payment_manager
from app.models.invoice_payment import InvoicePayment
from app.schemas.invoice_payment import (
    InvoicePaymentCreate,
    InvoicePaymentInDB,
    InvoicePaymentResponse,
    InvoicePaymentUpdate,
)
from app.services.base_service import BaseService


def to_payment_response(
    payment: InvoicePayment,
    created_by_name: Optional[str] = None,
) -> InvoicePaymentResponse:
    base = InvoicePaymentInDB.model_validate(payment)
    return InvoicePaymentResponse(**base.model_dump(), created_by_name=created_by_name)


class InvoicePaymentService(BaseService):
    """
    Service for Invoice Payment workflows.

    Handles:
    - Transaction boundaries (commit/rollback)
    - Payment CRUD operations with invoice status updates
    - Error handling and exception translation
    """

    def __init__(self):
        super().__init__()
        self.invoice_payment_manager = invoice_payment_manager

    def _payment_response(
        self,
        db: Session,
        payment: InvoicePayment,
        workspace_id: int,
    ) -> InvoicePaymentResponse:
        row = invoice_payment_dao.get_by_id_and_workspace_with_creator(
            db, id=payment.id, workspace_id=workspace_id
        )
        if row is None:
            return to_payment_response(payment, None)
        _, created_by_name = row
        return to_payment_response(payment, created_by_name)

    def create_payment(
        self,
        db: Session,
        payment_in: InvoicePaymentCreate,
        workspace_id: int,
        user_id: int,
    ) -> InvoicePaymentResponse:
        try:
            payment = self.invoice_payment_manager.create_payment(
                session=db,
                payment_data=payment_in,
                workspace_id=workspace_id,
                user_id=user_id,
            )
            self._commit_transaction(db)
            db.refresh(payment)
            return self._payment_response(db, payment, workspace_id)
        except Exception:
            self._rollback_transaction(db)
            raise

    def get_payment(
        self,
        db: Session,
        payment_id: int,
        workspace_id: int,
    ) -> InvoicePaymentResponse:
        row = invoice_payment_dao.get_by_id_and_workspace_with_creator(
            db, id=payment_id, workspace_id=workspace_id
        )
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Payment with ID {payment_id} not found",
            )
        payment, created_by_name = row
        return to_payment_response(payment, created_by_name)

    def list_payments_by_invoice(
        self,
        db: Session,
        invoice_id: int,
        workspace_id: int,
        skip: int = 0,
        limit: int = 100,
    ) -> List[InvoicePaymentResponse]:
        rows = self.invoice_payment_manager.list_payments_by_invoice(
            session=db,
            invoice_id=invoice_id,
            workspace_id=workspace_id,
            skip=skip,
            limit=limit,
        )
        return [to_payment_response(payment, created_by_name) for payment, created_by_name in rows]

    def update_payment(
        self,
        db: Session,
        payment_id: int,
        payment_in: InvoicePaymentUpdate,
        workspace_id: int,
    ) -> InvoicePaymentResponse:
        try:
            payment = self.invoice_payment_manager.update_payment(
                session=db,
                payment_id=payment_id,
                payment_data=payment_in,
                workspace_id=workspace_id,
            )
            self._commit_transaction(db)
            db.refresh(payment)
            return self._payment_response(db, payment, workspace_id)
        except Exception:
            self._rollback_transaction(db)
            raise

    def delete_payment(
        self,
        db: Session,
        payment_id: int,
        workspace_id: int,
        user_id: int,
    ) -> InvoicePaymentResponse:
        try:
            row = invoice_payment_dao.get_by_id_and_workspace_with_creator(
                db, id=payment_id, workspace_id=workspace_id
            )
            if row is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Payment with ID {payment_id} not found",
                )
            payment_before, created_by_name = row
            self.invoice_payment_manager.delete_payment(
                session=db,
                payment_id=payment_id,
                workspace_id=workspace_id,
                user_id=user_id,
            )
            self._commit_transaction(db)
            return to_payment_response(payment_before, created_by_name)
        except Exception:
            self._rollback_transaction(db)
            raise

    def void_payment(
        self,
        db: Session,
        payment_id: int,
        workspace_id: int,
        user_id: int,
        void_note: str,
    ) -> InvoicePaymentResponse:
        try:
            payment = self.invoice_payment_manager.void_payment(
                session=db,
                payment_id=payment_id,
                workspace_id=workspace_id,
                user_id=user_id,
                void_note=void_note,
            )
            self._commit_transaction(db)
            db.refresh(payment)
            return self._payment_response(db, payment, workspace_id)
        except Exception:
            self._rollback_transaction(db)
            raise


# Singleton instance
invoice_payment_service = InvoicePaymentService()
