"""
Invoice Payment Manager

Business logic for invoice payment operations with auto-status updates.
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from decimal import Decimal

from app.managers.base_manager import BaseManager
from app.models.invoice_payment import InvoicePayment
from app.schemas.invoice_payment import InvoicePaymentCreate, InvoicePaymentUpdate
from app.dao.invoice_payment import invoice_payment_dao
from app.dao.account_invoice import account_invoice_dao
from app.utils.audit_logger import log_financial_audit, create_change_dict, extract_relevant_fields


class InvoicePaymentManager(BaseManager[InvoicePayment]):
    """
    Manager for invoice payment business logic.

    Handles payment creation with automatic invoice status updates.
    """

    def __init__(self):
        super().__init__(InvoicePayment)
        self.invoice_payment_dao = invoice_payment_dao
        self.account_invoice_dao = account_invoice_dao

    def create_payment(
        self,
        session: Session,
        payment_data: InvoicePaymentCreate,
        workspace_id: int,
        user_id: int
    ) -> InvoicePayment:
        """
        Create new payment and update invoice status.

        Args:
            session: Database session
            payment_data: Payment creation data
            workspace_id: Workspace ID
            user_id: User creating the payment

        Returns:
            Created payment

        Raises:
            HTTPException: If invoice not found or validation fails
        """
        # Validate invoice exists in workspace
        invoice = self.account_invoice_dao.get_by_id_and_workspace(
            session, id=payment_data.invoice_id, workspace_id=workspace_id
        )
        if not invoice:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Invoice with ID {payment_data.invoice_id} not found"
            )

        # Validate payment amount doesn't exceed outstanding balance
        outstanding_amount = invoice.invoice_amount - invoice.paid_amount
        if payment_data.payment_amount > outstanding_amount:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Payment amount ({payment_data.payment_amount}) exceeds outstanding amount ({outstanding_amount})"
            )

        # Create payment with audit fields
        payment_dict = payment_data.model_dump()
        payment_dict['workspace_id'] = workspace_id
        payment_dict['created_by'] = user_id

        # Capture invoice status before payment
        old_status = invoice.payment_status

        payment = self.invoice_payment_dao.create(session, obj_in=payment_dict)

        # Update invoice paid_amount and payment_status (uses flush, not commit)
        updated_invoice = self.account_invoice_dao.update_paid_amount(
            session,
            invoice_id=invoice.id,
            workspace_id=workspace_id,
            additional_payment=payment_data.payment_amount
        )

        # Capture invoice status after payment
        new_status = updated_invoice.payment_status

        # Audit log with invoice status change
        changes = {
            'after': extract_relevant_fields(payment, ['payment_amount', 'payment_date', 'payment_method']),
        }
        if old_status != new_status:
            changes['invoice_status_changed'] = {'before': old_status, 'after': new_status}

        log_financial_audit(
            session=session,
            workspace_id=workspace_id,
            entity_type='payment',
            entity_id=payment.id,
            action_type='created',
            performed_by=user_id,
            related_entity_type='invoice',
            related_entity_id=invoice.id,
            changes=changes,
            description=f"Payment of ${payment_data.payment_amount} recorded for invoice ID {invoice.id}"
                        + (f", status changed to {new_status}" if old_status != new_status else "")
        )

        return payment

    def update_payment(
        self,
        session: Session,
        payment_id: int,
        payment_data: InvoicePaymentUpdate,
        workspace_id: int
    ) -> InvoicePayment:
        """
        Update payment.

        Note: Updating payment amount requires recalculating invoice totals.
        Consider deleting and re-creating payment instead for simplicity.

        Args:
            session: Database session
            payment_id: Payment ID
            payment_data: Update data
            workspace_id: Workspace ID

        Returns:
            Updated payment

        Raises:
            HTTPException: If payment not found
        """
        # Get payment
        payment = self.invoice_payment_dao.get_by_id_and_workspace(
            session, id=payment_id, workspace_id=workspace_id
        )
        if not payment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Payment with ID {payment_id} not found"
            )

        # If payment amount is being changed, we need to recalculate invoice totals
        if payment_data.payment_amount and payment_data.payment_amount != payment.payment_amount:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot change payment amount. Delete and re-create payment instead."
            )

        # Update payment (non-amount fields only)
        update_dict = payment_data.model_dump(exclude_unset=True)
        updated_payment = self.invoice_payment_dao.update(session, db_obj=payment, obj_in=update_dict)
        return updated_payment

    def get_payment(
        self,
        session: Session,
        payment_id: int,
        workspace_id: int
    ) -> InvoicePayment:
        """
        Get payment by ID.

        Args:
            session: Database session
            payment_id: Payment ID
            workspace_id: Workspace ID

        Returns:
            Payment

        Raises:
            HTTPException: If payment not found
        """
        payment = self.invoice_payment_dao.get_by_id_and_workspace(
            session, id=payment_id, workspace_id=workspace_id
        )

        if not payment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Payment with ID {payment_id} not found"
            )

        return payment

    def list_payments_by_invoice(
        self,
        session: Session,
        invoice_id: int,
        workspace_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[InvoicePayment]:
        """
        List all payments for an invoice.

        Args:
            session: Database session
            invoice_id: Invoice ID
            workspace_id: Workspace ID
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of payments
        """
        # Validate invoice exists
        invoice = self.account_invoice_dao.get_by_id_and_workspace(
            session, id=invoice_id, workspace_id=workspace_id
        )
        if not invoice:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Invoice with ID {invoice_id} not found"
            )

        return self.invoice_payment_dao.get_by_invoice(
            session, invoice_id=invoice_id, workspace_id=workspace_id, skip=skip, limit=limit
        )

    def delete_payment(
        self,
        session: Session,
        payment_id: int,
        workspace_id: int
    ) -> InvoicePayment:
        """
        Delete payment and recalculate invoice totals.

        Args:
            session: Database session
            payment_id: Payment ID
            workspace_id: Workspace ID

        Returns:
            Deleted payment

        Raises:
            HTTPException: If payment not found
        """
        payment = self.invoice_payment_dao.get_by_id_and_workspace(
            session, id=payment_id, workspace_id=workspace_id
        )

        if not payment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Payment with ID {payment_id} not found"
            )

        # Get invoice to update
        invoice = self.account_invoice_dao.get_by_id_and_workspace(
            session, id=payment.invoice_id, workspace_id=workspace_id
        )
        if not invoice:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Invoice with ID {payment.invoice_id} not found"
            )

        # Capture invoice status before deletion
        old_status = invoice.payment_status

        # Audit log before deletion
        log_financial_audit(
            session=session,
            workspace_id=workspace_id,
            entity_type='payment',
            entity_id=payment.id,
            action_type='deleted',
            performed_by=0,  # No user_id passed to delete method currently
            related_entity_type='invoice',
            related_entity_id=invoice.id,
            changes=create_change_dict(before=extract_relevant_fields(
                payment, ['payment_amount', 'payment_date', 'payment_method']
            )),
            description=f"Payment of ${payment.payment_amount} deleted from invoice ID {invoice.id}"
        )

        # Delete payment
        self.invoice_payment_dao.remove(session, id=payment_id)

        # Recalculate invoice totals
        total_paid = self.invoice_payment_dao.get_total_paid_for_invoice(
            session, invoice_id=invoice.id, workspace_id=workspace_id
        )

        # Update invoice
        invoice.paid_amount = total_paid
        if total_paid >= invoice.invoice_amount:
            invoice.payment_status = 'paid'
        elif total_paid > 0:
            invoice.payment_status = 'partial'
        else:
            invoice.payment_status = 'unpaid'

        session.flush()

        # Capture invoice status after deletion
        new_status = invoice.payment_status

        # Log invoice status change if it happened
        if old_status != new_status:
            log_financial_audit(
                session=session,
                workspace_id=workspace_id,
                entity_type='invoice',
                entity_id=invoice.id,
                action_type='status_changed',
                performed_by=0,  # No user_id passed
                changes={'status': {'before': old_status, 'after': new_status}},
                description=f"Invoice status changed from {old_status} to {new_status} after payment deletion"
            )

        return payment


# Singleton instance
invoice_payment_manager = InvoicePaymentManager()
