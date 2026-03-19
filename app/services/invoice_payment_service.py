"""Invoice Payment Service for orchestrating payment workflows"""
from typing import List
from sqlalchemy.orm import Session

from app.services.base_service import BaseService
from app.managers.invoice_payment_manager import invoice_payment_manager
from app.models.invoice_payment import InvoicePayment
from app.schemas.invoice_payment import InvoicePaymentCreate, InvoicePaymentUpdate


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

    def create_payment(
        self,
        db: Session,
        payment_in: InvoicePaymentCreate,
        workspace_id: int,
        user_id: int
    ) -> InvoicePayment:
        """
        Create a new payment and update invoice status.

        Args:
            db: Database session
            payment_in: Payment creation data
            workspace_id: Workspace ID
            user_id: User creating the payment

        Returns:
            Created payment

        Raises:
            HTTPException: If invoice not found or validation fails
        """
        try:
            # Create payment using manager (also updates invoice)
            payment = self.invoice_payment_manager.create_payment(
                session=db,
                payment_data=payment_in,
                workspace_id=workspace_id,
                user_id=user_id
            )

            # Commit transaction
            self._commit_transaction(db)
            db.refresh(payment)

            return payment

        except Exception as e:
            self._rollback_transaction(db)
            raise

    def get_payment(
        self,
        db: Session,
        payment_id: int,
        workspace_id: int
    ) -> InvoicePayment:
        """
        Get payment by ID.

        Args:
            db: Database session
            payment_id: Payment ID
            workspace_id: Workspace ID

        Returns:
            Payment

        Raises:
            HTTPException: If payment not found
        """
        return self.invoice_payment_manager.get_payment(db, payment_id, workspace_id)

    def list_payments_by_invoice(
        self,
        db: Session,
        invoice_id: int,
        workspace_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[InvoicePayment]:
        """
        List payments for an invoice.

        Args:
            db: Database session
            invoice_id: Invoice ID
            workspace_id: Workspace ID
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of payments
        """
        return self.invoice_payment_manager.list_payments_by_invoice(
            session=db,
            invoice_id=invoice_id,
            workspace_id=workspace_id,
            skip=skip,
            limit=limit
        )

    def update_payment(
        self,
        db: Session,
        payment_id: int,
        payment_in: InvoicePaymentUpdate,
        workspace_id: int
    ) -> InvoicePayment:
        """
        Update payment.

        Note: Cannot change payment amount. Delete and re-create instead.

        Args:
            db: Database session
            payment_id: Payment ID
            payment_in: Update data
            workspace_id: Workspace ID

        Returns:
            Updated payment

        Raises:
            HTTPException: If payment not found or trying to change amount
        """
        try:
            # Update payment using manager
            payment = self.invoice_payment_manager.update_payment(
                session=db,
                payment_id=payment_id,
                payment_data=payment_in,
                workspace_id=workspace_id
            )

            # Commit transaction
            self._commit_transaction(db)
            db.refresh(payment)

            return payment

        except Exception as e:
            self._rollback_transaction(db)
            raise

    def delete_payment(
        self,
        db: Session,
        payment_id: int,
        workspace_id: int
    ) -> InvoicePayment:
        """
        Delete payment and recalculate invoice totals.

        Args:
            db: Database session
            payment_id: Payment ID
            workspace_id: Workspace ID

        Returns:
            Deleted payment

        Raises:
            HTTPException: If payment not found
        """
        try:
            # Delete payment using manager (also recalculates invoice)
            payment = self.invoice_payment_manager.delete_payment(
                session=db,
                payment_id=payment_id,
                workspace_id=workspace_id
            )

            # Commit transaction
            self._commit_transaction(db)

            return payment

        except Exception as e:
            self._rollback_transaction(db)
            raise


# Singleton instance
invoice_payment_service = InvoicePaymentService()
