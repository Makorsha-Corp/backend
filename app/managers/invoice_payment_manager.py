"""
Invoice Payment Manager

Business logic for invoice payment operations with auto-status updates.
"""
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from decimal import Decimal

from datetime import datetime
from app.managers.base_manager import BaseManager
from app.models.invoice_payment import InvoicePayment
from app.models.account_invoice import AccountInvoice
from app.schemas.invoice_payment import InvoicePaymentCreate, InvoicePaymentUpdate, VoidPaymentRequest
from app.dao.invoice_payment import invoice_payment_dao
from app.dao.account_invoice import account_invoice_dao
from app.managers.account_invoice_manager import account_invoice_manager
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
        # Lock the invoice row for the duration of this transaction to prevent
        # concurrent payments from both passing the outstanding balance check.
        invoice = (
            session.query(AccountInvoice)
            .filter(
                AccountInvoice.id == payment_data.invoice_id,
                AccountInvoice.workspace_id == workspace_id,
            )
            .with_for_update()
            .one_or_none()
        )
        if not invoice:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Invoice with ID {payment_data.invoice_id} not found"
            )

        # Only confirmed invoices accept payments
        if invoice.invoice_status not in ('confirmed',):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Payments can only be recorded against confirmed invoices (current status: '{invoice.invoice_status}')."
            )

        # Enforce admin payment lock
        if not invoice.allow_payments:
            reason = invoice.payment_locked_reason or "Payments are locked for this invoice"
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=reason
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

        account_invoice_manager._log_event(
            session,
            updated_invoice,
            "payment_recorded",
            "Payment recorded",
            performed_by=user_id,
            metadata={
                "payment_id": payment.id,
                "payment_amount": str(payment_data.payment_amount),
                "payment_method": payment_data.payment_method,
                "payment_status_before": old_status,
                "payment_status_after": new_status,
            },
        )

        self._sync_linked_po_stage(session, updated_invoice, user_id)

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
        update_dict = payment_data.model_dump(exclude_unset=True, exclude_none=True)
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
    ) -> List[Tuple[InvoicePayment, Optional[str]]]:
        """
        List all payments for an invoice.

        Args:
            session: Database session
            invoice_id: Invoice ID
            workspace_id: Workspace ID
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of (payment, created_by_name) tuples
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
        workspace_id: int,
        user_id: int
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

        # Capture before state while payment object is still valid
        old_invoice_payment_status = invoice.payment_status
        payment_snapshot = extract_relevant_fields(payment, ['payment_amount', 'payment_date', 'payment_method'])
        payment_amount_str = payment.payment_amount

        # Delete payment then flush so the recalculation query sees the deletion
        self.invoice_payment_dao.remove(session, id=payment_id)
        session.flush()

        # Recalculate invoice totals from remaining payments
        total_paid = self.invoice_payment_dao.get_total_paid_for_invoice(
            session, invoice_id=invoice.id, workspace_id=workspace_id
        )
        invoice.paid_amount = total_paid
        if total_paid >= invoice.invoice_amount:
            invoice.payment_status = 'paid'
        elif total_paid > 0:
            invoice.payment_status = 'partial'
        else:
            invoice.payment_status = 'unpaid'
        session.flush()

        new_invoice_payment_status = invoice.payment_status

        # Audit log after all mutations are applied
        log_financial_audit(
            session=session,
            workspace_id=workspace_id,
            entity_type='payment',
            entity_id=payment_id,
            action_type='deleted',
            performed_by=user_id,
            related_entity_type='invoice',
            related_entity_id=invoice.id,
            changes=create_change_dict(before=payment_snapshot),
            description=f"Payment of ${payment_amount_str} deleted from invoice ID {invoice.id}"
        )

        if old_invoice_payment_status != new_invoice_payment_status:
            log_financial_audit(
                session=session,
                workspace_id=workspace_id,
                entity_type='invoice',
                entity_id=invoice.id,
                action_type='status_changed',
                performed_by=user_id,
                changes={'payment_status': {'before': old_invoice_payment_status, 'after': new_invoice_payment_status}},
                description=f"Invoice payment status changed from {old_invoice_payment_status} to {new_invoice_payment_status} after payment deletion"
            )

        self._sync_linked_po_stage(session, invoice, user_id)

        return payment


    def void_payment(
        self,
        session: Session,
        payment_id: int,
        workspace_id: int,
        user_id: int,
        void_note: str
    ) -> InvoicePayment:
        """Void a payment and recalculate invoice totals from remaining active payments."""
        payment = self.invoice_payment_dao.get_by_id_and_workspace(
            session, id=payment_id, workspace_id=workspace_id
        )
        if not payment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail=f"Payment with ID {payment_id} not found")
        if payment.is_voided:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Payment is already voided")

        invoice = self.account_invoice_dao.get_by_id_and_workspace(
            session, id=payment.invoice_id, workspace_id=workspace_id
        )
        if not invoice:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail=f"Invoice with ID {payment.invoice_id} not found")

        old_invoice_status = invoice.payment_status

        # Void the payment
        payment.is_voided = True
        payment.voided_at = datetime.utcnow()
        payment.voided_by = user_id
        payment.void_note = void_note
        session.flush()

        # Recalculate invoice totals from remaining active payments
        total_paid = self.invoice_payment_dao.get_total_paid_for_invoice(
            session, invoice_id=invoice.id, workspace_id=workspace_id
        )
        invoice.paid_amount = total_paid
        if total_paid >= invoice.invoice_amount:
            invoice.payment_status = 'paid'
        elif total_paid > 0:
            invoice.payment_status = 'partial'
        else:
            invoice.payment_status = 'unpaid'
        session.flush()

        log_financial_audit(
            session=session,
            workspace_id=workspace_id,
            entity_type='payment',
            entity_id=payment.id,
            action_type='voided',
            performed_by=user_id,
            related_entity_type='invoice',
            related_entity_id=invoice.id,
            changes={
                'payment_voided': extract_relevant_fields(payment, ['payment_amount', 'payment_date', 'payment_method']),
                **(
                    {'invoice_payment_status': {'before': old_invoice_status, 'after': invoice.payment_status}}
                    if old_invoice_status != invoice.payment_status else {}
                ),
            },
            description=f"Payment of ${payment.payment_amount} voided for invoice ID {invoice.id}. Reason: {void_note}"
        )

        account_invoice_manager._log_event(
            session,
            invoice,
            "payment_voided",
            "Payment voided",
            performed_by=user_id,
            metadata={
                "payment_id": payment.id,
                "payment_amount": str(payment.payment_amount),
                "payment_method": payment.payment_method,
                "void_note": void_note,
                "payment_status_before": old_invoice_status,
                "payment_status_after": invoice.payment_status,
            },
        )

        self._sync_linked_po_stage(session, invoice, user_id)
        return payment


    def _sync_linked_po_stage(
        self,
        session: Session,
        invoice: AccountInvoice,
        user_id: int | None,
    ) -> None:
        if invoice.order_type != 'purchase_order' or invoice.order_id is None:
            return
        from app.managers.purchase_order_manager import purchase_order_manager

        purchase_order_manager.sync_po_for_linked_invoice(
            session,
            invoice_id=invoice.id,
            workspace_id=invoice.workspace_id,
            user_id=user_id,
        )


# Singleton instance
invoice_payment_manager = InvoicePaymentManager()
