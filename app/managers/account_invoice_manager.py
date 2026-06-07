"""
Account Invoice Manager

Business logic for account invoice operations.
Lifecycle: draft → confirmed → voided (terminal)
"""
from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from decimal import Decimal

from app.managers.base_manager import BaseManager
from app.models.account_invoice import AccountInvoice
from app.models.invoice_payment import InvoicePayment
from app.models.invoice_status_tracker import InvoiceStatusTracker
from app.models.profile import Profile
from app.schemas.account_invoice import AccountInvoiceCreate, AccountInvoiceUpdate, VoidInvoiceRequest
from app.dao.account_invoice import account_invoice_dao
from app.dao.account import account_dao
from app.utils.audit_logger import log_financial_audit, create_change_dict, extract_relevant_fields


class AccountInvoiceManager(BaseManager[AccountInvoice]):

    def __init__(self):
        super().__init__(AccountInvoice)
        self.account_invoice_dao = account_invoice_dao
        self.account_dao = account_dao

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_or_404(self, session: Session, invoice_id: int, workspace_id: int) -> AccountInvoice:
        invoice = self.account_invoice_dao.get_by_id_and_workspace(
            session, id=invoice_id, workspace_id=workspace_id
        )
        if not invoice:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Invoice with ID {invoice_id} not found"
            )
        return invoice

    def _log_status_change(
        self,
        session: Session,
        invoice: AccountInvoice,
        from_status: str,
        to_status: str,
        changed_by: int
    ) -> None:
        """Write one row to invoice_status_tracker."""
        entry = InvoiceStatusTracker(
            workspace_id=invoice.workspace_id,
            invoice_id=invoice.id,
            from_status=from_status,
            to_status=to_status,
            changed_by=changed_by,
            changed_at=datetime.utcnow(),
        )
        session.add(entry)

    def _recalculate_payment_status(self, invoice: AccountInvoice) -> None:
        if invoice.paid_amount >= invoice.invoice_amount:
            invoice.payment_status = 'paid'
        elif invoice.paid_amount > 0:
            invoice.payment_status = 'partial'
        else:
            invoice.payment_status = 'unpaid'

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create_invoice(
        self,
        session: Session,
        invoice_data: AccountInvoiceCreate,
        workspace_id: int,
        user_id: int
    ) -> AccountInvoice:
        account = self.account_dao.get_by_id_and_workspace(
            session, id=invoice_data.account_id, workspace_id=workspace_id
        )
        if not account:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail=f"Account with ID {invoice_data.account_id} not found")
        if account.is_deleted:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Cannot create invoice for deleted account")
        if not account.is_active:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Cannot create invoice for inactive account")
        if not account.allow_invoices:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Invoices are not allowed for this account")

        invoice_dict = invoice_data.model_dump()
        invoice_dict['workspace_id'] = workspace_id
        invoice_dict['created_by'] = user_id
        invoice_dict['paid_amount'] = Decimal('0.00')
        invoice_dict['payment_status'] = 'unpaid'
        invoice_dict['invoice_status'] = 'draft'

        invoice = self.account_invoice_dao.create(session, obj_in=invoice_dict)

        log_financial_audit(
            session=session,
            workspace_id=workspace_id,
            entity_type='invoice',
            entity_id=invoice.id,
            action_type='created',
            performed_by=user_id,
            related_entity_type='account',
            related_entity_id=invoice.account_id,
            changes=create_change_dict(after=extract_relevant_fields(
                invoice, ['invoice_type', 'invoice_amount', 'invoice_number', 'invoice_date', 'due_date', 'invoice_status']
            )),
            description=f"{invoice.invoice_type.capitalize()} invoice created (draft) for account ID {invoice.account_id}"
        )
        return invoice

    def get_invoice(self, session: Session, invoice_id: int, workspace_id: int) -> AccountInvoice:
        return self._get_or_404(session, invoice_id, workspace_id)

    def list_invoices(
        self,
        session: Session,
        workspace_id: int,
        account_id: Optional[int] = None,
        invoice_type: Optional[str] = None,
        payment_status: Optional[str] = None,
        invoice_number_search: Optional[str] = None,
        account_name_search: Optional[str] = None,
        invoice_date_from=None,
        invoice_date_to=None,
        due_date_from=None,
        due_date_to=None,
        amount_min=None,
        amount_max=None,
        skip: int = 0,
        limit: int = 100
    ) -> List[AccountInvoice]:
        """List invoices with all filters. Excludes invoices from soft-deleted accounts."""
        return self.account_invoice_dao.list_invoices(
            session,
            workspace_id=workspace_id,
            account_id=account_id,
            invoice_type=invoice_type,
            payment_status=payment_status,
            invoice_number_search=invoice_number_search,
            account_name_search=account_name_search,
            invoice_date_from=invoice_date_from,
            invoice_date_to=invoice_date_to,
            due_date_from=due_date_from,
            due_date_to=due_date_to,
            amount_min=amount_min,
            amount_max=amount_max,
            skip=skip,
            limit=limit,
        )

    def update_invoice(
        self,
        session: Session,
        invoice_id: int,
        invoice_data: AccountInvoiceUpdate,
        workspace_id: int,
        user_id: int
    ) -> AccountInvoice:
        invoice = self._get_or_404(session, invoice_id, workspace_id)

        if invoice.invoice_status == 'voided':
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Voided invoices cannot be edited")

        # Capture original status BEFORE any mutation so dropped_to_draft is correct
        original_status = invoice.invoice_status

        if invoice.invoice_status == 'confirmed':
            if invoice.paid_amount > 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot edit a confirmed invoice that has active payments. "
                           "Void all payments first, then you can edit."
                )
            # No active payments — allow edit, drop back to draft
            invoice.invoice_status = 'draft'

        if invoice_data.account_id and invoice_data.account_id != invoice.account_id:
            account = self.account_dao.get_by_id_and_workspace(
                session, id=invoice_data.account_id, workspace_id=workspace_id
            )
            if not account:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                    detail=f"Account with ID {invoice_data.account_id} not found")
            if account.is_deleted:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                    detail="Cannot assign invoice to deleted account")

        before_state = extract_relevant_fields(
            invoice, ['invoice_type', 'invoice_amount', 'invoice_number', 'invoice_date', 'due_date', 'payment_status', 'invoice_status']
        )

        dropped_to_draft = original_status == 'confirmed' and invoice.invoice_status == 'draft'

        update_dict = invoice_data.model_dump(exclude_unset=True)
        # Guard: these fields are system-managed and must never be set via the update endpoint
        for protected in ('invoice_status', 'paid_amount', 'void_note'):
            update_dict.pop(protected, None)
        update_dict['updated_by'] = user_id

        updated_invoice = self.account_invoice_dao.update(session, db_obj=invoice, obj_in=update_dict)

        if dropped_to_draft:
            self._log_status_change(session, updated_invoice, 'confirmed', 'draft', user_id)

        after_state = extract_relevant_fields(
            updated_invoice, ['invoice_type', 'invoice_amount', 'invoice_number', 'invoice_date', 'due_date', 'payment_status', 'invoice_status']
        )

        log_financial_audit(
            session=session,
            workspace_id=workspace_id,
            entity_type='invoice',
            entity_id=invoice.id,
            action_type='updated',
            performed_by=user_id,
            related_entity_type='account',
            related_entity_id=invoice.account_id,
            changes=create_change_dict(before=before_state, after=after_state),
            description=f"Invoice {invoice.invoice_number or invoice.id} updated"
                        + (" — moved back to draft" if dropped_to_draft else "")
        )
        return updated_invoice

    def delete_invoice(
        self,
        session: Session,
        invoice_id: int,
        workspace_id: int,
        user_id: int
    ) -> AccountInvoice:
        invoice = self._get_or_404(session, invoice_id, workspace_id)

        if invoice.invoice_status != 'draft':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Only draft invoices can be deleted. "
                       f"This invoice is '{invoice.invoice_status}'. Use void instead."
            )

        log_financial_audit(
            session=session,
            workspace_id=workspace_id,
            entity_type='invoice',
            entity_id=invoice.id,
            action_type='deleted',
            performed_by=user_id,
            related_entity_type='account',
            related_entity_id=invoice.account_id,
            changes=create_change_dict(before=extract_relevant_fields(
                invoice, ['invoice_type', 'invoice_amount', 'invoice_number', 'invoice_date']
            )),
            description=f"Draft invoice {invoice.invoice_number or invoice.id} deleted"
        )

        self.account_invoice_dao.remove(session, id=invoice_id)
        return invoice

    # ------------------------------------------------------------------
    # Lifecycle actions
    # ------------------------------------------------------------------

    def confirm_invoice(
        self,
        session: Session,
        invoice_id: int,
        workspace_id: int,
        user_id: int
    ) -> AccountInvoice:
        invoice = self._get_or_404(session, invoice_id, workspace_id)

        if invoice.invoice_status == 'voided':
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Voided invoices cannot be confirmed")
        if invoice.invoice_status == 'confirmed':
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Invoice is already confirmed")

        invoice.invoice_status = 'confirmed'
        session.flush()

        self._log_status_change(session, invoice, 'draft', 'confirmed', user_id)

        log_financial_audit(
            session=session,
            workspace_id=workspace_id,
            entity_type='invoice',
            entity_id=invoice.id,
            action_type='confirmed',
            performed_by=user_id,
            related_entity_type='account',
            related_entity_id=invoice.account_id,
            changes={'invoice_status': {'before': 'draft', 'after': 'confirmed'}},
            description=f"Invoice {invoice.invoice_number or invoice.id} confirmed"
        )
        return invoice

    def void_invoice(
        self,
        session: Session,
        invoice_id: int,
        workspace_id: int,
        user_id: int,
        void_note: str
    ) -> AccountInvoice:
        invoice = self._get_or_404(session, invoice_id, workspace_id)

        if invoice.invoice_status == 'voided':
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Invoice is already voided")
        if invoice.invoice_status == 'draft':
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Draft invoices cannot be voided — delete them instead")

        now = datetime.utcnow()
        system_payment_void_note = (
            f"Automatically voided — invoice #{invoice.id} was voided. Reason: {void_note}"
        )

        # Explicit query — do not rely on lazy-loaded backref inside an active transaction
        active_payments = (
            session.query(InvoicePayment)
            .filter(
                InvoicePayment.invoice_id == invoice.id,
                InvoicePayment.is_voided == False,
            )
            .all()
        )
        for payment in active_payments:
            payment.is_voided = True
            payment.voided_at = now
            payment.voided_by = user_id
            payment.void_note = system_payment_void_note

        # Void the invoice
        invoice.invoice_status = 'voided'
        invoice.void_note = void_note
        invoice.paid_amount = Decimal('0.00')
        invoice.payment_status = 'unpaid'
        session.flush()

        self._log_status_change(session, invoice, 'confirmed', 'voided', user_id)

        log_financial_audit(
            session=session,
            workspace_id=workspace_id,
            entity_type='invoice',
            entity_id=invoice.id,
            action_type='voided',
            performed_by=user_id,
            related_entity_type='account',
            related_entity_id=invoice.account_id,
            changes={'invoice_status': {'before': 'confirmed', 'after': 'voided'},
                     'payments_voided': len(active_payments)},
            description=f"Invoice {invoice.invoice_number or invoice.id} voided. "
                        f"{len(active_payments)} payment(s) auto-voided. Reason: {void_note}"
        )
        return invoice


    def get_status_history(
        self,
        session: Session,
        invoice_id: int,
        workspace_id: int
    ) -> list:
        """Return all status transitions for an invoice, oldest first, with changer name."""
        self._get_or_404(session, invoice_id, workspace_id)

        rows = (
            session.query(InvoiceStatusTracker, Profile.name.label('changed_by_name'))
            .outerjoin(Profile, InvoiceStatusTracker.changed_by == Profile.id)
            .filter(
                InvoiceStatusTracker.invoice_id == invoice_id,
                InvoiceStatusTracker.workspace_id == workspace_id,
            )
            .order_by(InvoiceStatusTracker.changed_at.asc())
            .all()
        )

        return [
            {
                'id': tracker.id,
                'invoice_id': tracker.invoice_id,
                'from_status': tracker.from_status,
                'to_status': tracker.to_status,
                'changed_by': tracker.changed_by,
                'changed_at': tracker.changed_at,
                'changed_by_name': changed_by_name,
            }
            for tracker, changed_by_name in rows
        ]


# Singleton instance
account_invoice_manager = AccountInvoiceManager()
