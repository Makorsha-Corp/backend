"""
Account Invoice Manager

Business logic for account invoice operations.
Lifecycle: draft → confirmed → voided (terminal)
receiving_started is a boolean flag on confirmed invoices, set when PO receiving is recorded.
"""
from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.managers.base_manager import BaseManager
from app.models.account_invoice import AccountInvoice
from app.models.invoice_payment import InvoicePayment
from app.schemas.account_invoice import AccountInvoiceCreate, AccountInvoiceUpdate
from app.dao.account_invoice import account_invoice_dao
from app.dao.account import account_dao
from app.dao.invoice_item import invoice_item_dao
from app.dao.invoice_event import invoice_event_dao


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
                detail=f"Invoice with ID {invoice_id} not found",
            )
        return invoice

    def _log_event(
        self,
        session: Session,
        invoice: AccountInvoice,
        event_type: str,
        description: str,
        performed_by: Optional[int] = None,
        metadata: Optional[dict] = None,
    ) -> None:
        invoice_event_dao.create_event(
            session,
            workspace_id=invoice.workspace_id,
            invoice_id=invoice.id,
            event_type=event_type,
            description=description,
            performed_by=performed_by,
            metadata=metadata,
        )

    def _recalculate_payment_status(self, invoice: AccountInvoice) -> None:
        if invoice.paid_amount >= invoice.invoice_amount:
            invoice.payment_status = "paid"
        elif invoice.paid_amount > 0:
            invoice.payment_status = "partial"
        else:
            invoice.payment_status = "unpaid"

    def _recalculate_invoice_amount(self, session: Session, invoice: AccountInvoice) -> None:
        """Recompute invoice_amount from the sum of its items."""
        items = invoice_item_dao.get_by_invoice(session, invoice_id=invoice.id, workspace_id=invoice.workspace_id)
        total = sum(Decimal(str(i.line_subtotal)) for i in items) if items else Decimal("0.00")
        invoice.invoice_amount = total
        self._recalculate_payment_status(invoice)

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create_invoice(
        self,
        session: Session,
        invoice_data: AccountInvoiceCreate,
        workspace_id: int,
        user_id: int,
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

        invoice_dict = invoice_data.model_dump(exclude_none=True)
        invoice_dict["workspace_id"] = workspace_id
        invoice_dict["created_by"] = user_id
        invoice_dict["paid_amount"] = Decimal("0.00")
        invoice_dict["payment_status"] = "unpaid"
        invoice_dict["invoice_status"] = "draft"
        invoice_dict["receiving_started"] = False

        invoice = self.account_invoice_dao.create(session, obj_in=invoice_dict)

        self._log_event(
            session, invoice, "created",
            "Draft invoice created",
            performed_by=user_id,
            metadata={"invoice_type": invoice.invoice_type, "account_id": invoice.account_id},
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
        invoice_status: Optional[str] = None,
        invoice_number_search: Optional[str] = None,
        account_name_search: Optional[str] = None,
        invoice_date_from=None,
        invoice_date_to=None,
        due_date_from=None,
        due_date_to=None,
        amount_min=None,
        amount_max=None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[AccountInvoice]:
        return self.account_invoice_dao.list_invoices(
            session,
            workspace_id=workspace_id,
            account_id=account_id,
            invoice_type=invoice_type,
            payment_status=payment_status,
            invoice_status=invoice_status,
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

    def summarize_invoices(
        self,
        session: Session,
        workspace_id: int,
        account_id: Optional[int] = None,
        invoice_type: Optional[str] = None,
        payment_status: Optional[str] = None,
        invoice_status: Optional[str] = None,
        invoice_number_search: Optional[str] = None,
        account_name_search: Optional[str] = None,
        invoice_date_from=None,
        invoice_date_to=None,
        due_date_from=None,
        due_date_to=None,
        amount_min=None,
        amount_max=None,
    ):
        return self.account_invoice_dao.summarize_invoices(
            session,
            workspace_id=workspace_id,
            account_id=account_id,
            invoice_type=invoice_type,
            payment_status=payment_status,
            invoice_status=invoice_status,
            invoice_number_search=invoice_number_search,
            account_name_search=account_name_search,
            invoice_date_from=invoice_date_from,
            invoice_date_to=invoice_date_to,
            due_date_from=due_date_from,
            due_date_to=due_date_to,
            amount_min=amount_min,
            amount_max=amount_max,
        )

    def update_invoice(
        self,
        session: Session,
        invoice_id: int,
        invoice_data: AccountInvoiceUpdate,
        workspace_id: int,
        user_id: int,
    ) -> AccountInvoice:
        invoice = self._get_or_404(session, invoice_id, workspace_id)

        if invoice.invoice_status == "voided":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Voided invoices cannot be edited")

        if invoice.invoice_status == "confirmed":
            # Confirmed invoices: admin fields + due date are mutable
            allowed = {"allow_payments", "payment_locked_reason", "due_date"}
            update_dict = {
                k: v for k, v in invoice_data.model_dump(exclude_unset=True).items()
                if k in allowed
            }
            if not update_dict:
                return invoice
            old_due_date = invoice.due_date
            update_dict["updated_by"] = user_id
            updated = self.account_invoice_dao.update(session, db_obj=invoice, obj_in=update_dict)
            changed = [k for k in update_dict if k != "updated_by"]

            if "due_date" in changed:
                old_str = old_due_date.isoformat() if old_due_date else None
                new_str = updated.due_date.isoformat() if updated.due_date else None
                self._log_event(
                    session, updated, "due_date_changed",
                    "Due date updated",
                    performed_by=user_id,
                    metadata={"old_due_date": old_str, "new_due_date": new_str},
                )
                changed = [k for k in changed if k != "due_date"]

            if changed:
                if "allow_payments" in changed:
                    enabled = update_dict.get("allow_payments")
                    self._log_event(
                        session, updated, "allow_payments_changed",
                        "Payments enabled" if enabled else "Payments disabled",
                        performed_by=user_id,
                        metadata={"allow_payments": enabled},
                    )
                if "payment_locked_reason" in changed:
                    reason = update_dict.get("payment_locked_reason")
                    self._log_event(
                        session, updated, "payment_lock_changed",
                        "Payment lock updated",
                        performed_by=user_id,
                        metadata={"payment_locked_reason": reason},
                    )
            return updated

        # Draft invoice: full edit allowed (except system-managed fields)
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

        update_dict = invoice_data.model_dump(exclude_unset=True)
        for protected in ("invoice_status", "paid_amount", "void_note", "invoice_amount", "receiving_started"):
            update_dict.pop(protected, None)

        update_dict["updated_by"] = user_id
        updated_invoice = self.account_invoice_dao.update(session, db_obj=invoice, obj_in=update_dict)

        self._log_event(
            session, updated_invoice, "item_manually_updated",
            "Invoice details updated",
            performed_by=user_id,
            metadata={k: str(v) for k, v in update_dict.items() if k != "updated_by"},
        )
        return updated_invoice

    def delete_invoice(
        self,
        session: Session,
        invoice_id: int,
        workspace_id: int,
        user_id: int,
    ) -> AccountInvoice:
        invoice = self._get_or_404(session, invoice_id, workspace_id)

        if invoice.invoice_status != "draft":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Only draft invoices can be deleted. "
                       f"This invoice is '{invoice.invoice_status}'. Use void instead.",
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
        user_id: int,
    ) -> AccountInvoice:
        invoice = self._get_or_404(session, invoice_id, workspace_id)

        if invoice.invoice_status == "voided":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Voided invoices cannot be confirmed")
        if invoice.invoice_status == "confirmed":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Invoice is already confirmed")

        # Recalculate amount from items and freeze
        self._recalculate_invoice_amount(session, invoice)
        now = datetime.utcnow()
        invoice.last_synced_at = now
        invoice.invoice_status = "confirmed"
        session.flush()

        self._log_event(
            session, invoice, "confirmed",
            "Invoice finalized",
            performed_by=user_id,
            metadata={"invoice_amount": str(invoice.invoice_amount)},
        )
        return invoice

    def revert_to_draft(
        self,
        session: Session,
        invoice_id: int,
        workspace_id: int,
        user_id: int,
    ) -> AccountInvoice:
        invoice = self._get_or_404(session, invoice_id, workspace_id)

        if invoice.invoice_status != "confirmed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Only confirmed invoices can be reverted to draft. Current status: '{invoice.invoice_status}'.",
            )
        if invoice.receiving_started:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot revert to draft — receiving has been recorded on the linked order. "
                       "Zero out received quantities first.",
            )
        if Decimal(str(invoice.paid_amount or 0)) > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot revert to draft — invoice has active payments. Void all payments first.",
            )

        invoice.invoice_status = "draft"
        session.flush()

        self._log_event(
            session, invoice, "reverted_to_draft",
            "Reverted to draft",
            performed_by=user_id,
        )
        return invoice

    def void_invoice(
        self,
        session: Session,
        invoice_id: int,
        workspace_id: int,
        user_id: int,
        void_note: str,
    ) -> AccountInvoice:
        invoice = self._get_or_404(session, invoice_id, workspace_id)

        if invoice.invoice_status == "voided":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Invoice is already voided")
        if invoice.invoice_status == "draft":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Draft invoices cannot be voided — delete them instead")

        now = datetime.utcnow()
        system_void_note = f"Automatically voided — invoice #{invoice.id} was voided. Reason: {void_note}"

        active_payments = (
            session.query(InvoicePayment)
            .filter(InvoicePayment.invoice_id == invoice.id, InvoicePayment.is_voided == False)
            .all()
        )
        for payment in active_payments:
            payment.is_voided = True
            payment.voided_at = now
            payment.voided_by = user_id
            payment.void_note = system_void_note

        prior_status = invoice.invoice_status
        invoice.invoice_status = "voided"
        invoice.void_note = void_note
        invoice.paid_amount = Decimal("0.00")
        invoice.payment_status = "unpaid"
        session.flush()

        self._log_event(
            session, invoice, "voided",
            "Invoice voided",
            performed_by=user_id,
            metadata={
                "prior_status": prior_status,
                "payments_voided": len(active_payments),
                "void_note": void_note,
            },
        )
        return invoice

    def set_receiving_started(
        self,
        session: Session,
        invoice_id: int,
        workspace_id: int,
        performed_by: Optional[int],
        reason: str = "",
    ) -> AccountInvoice:
        """Flip receiving_started = True and log the event. No-op if already set."""
        invoice = self.account_invoice_dao.get_by_id_and_workspace(
            session, id=invoice_id, workspace_id=workspace_id
        )
        if not invoice or invoice.receiving_started:
            return invoice
        invoice.receiving_started = True
        session.flush()
        self._log_event(
            session, invoice, "receiving_started_set",
            reason or "Receiving started on linked order",
            performed_by=performed_by,
        )
        return invoice

    # ------------------------------------------------------------------
    # Item sync helpers (called from services)
    # ------------------------------------------------------------------

    def sync_items_from_list(
        self,
        session: Session,
        invoice: AccountInvoice,
        items: list[dict],
        user_id: Optional[int],
        is_manual: bool = False,
    ) -> None:
        """
        Replace invoice items with the provided list and recalculate invoice_amount.
        items is a list of dicts with keys matching InvoiceItem columns.
        Only allowed on draft invoices.
        """
        if invoice.invoice_status != "draft":
            return

        invoice_item_dao.delete_all_for_invoice(session, invoice.id)

        now = datetime.utcnow()
        for item_dict in items:
            item_dict.setdefault("workspace_id", invoice.workspace_id)
            item_dict.setdefault("invoice_id", invoice.id)
            item_dict.setdefault("created_by", user_id)
            item_dict["last_synced_at"] = now
            invoice_item_dao.create(session, obj_in=item_dict)

        invoice.last_synced_at = now
        self._recalculate_invoice_amount(session, invoice)
        session.flush()

        event_type = "item_manually_updated" if is_manual else "items_synced"
        description = (
            "Items updated"
            if is_manual
            else f"Items synced from order ({len(items)} lines)"
        )
        item_summaries = [
            {
                "description": item.get("description") or f"Line {item.get('line_number', idx + 1)}",
                "quantity": str(item["quantity"]) if item.get("quantity") is not None else None,
                "unit": item.get("unit"),
                "unit_price": str(item["unit_price"]) if item.get("unit_price") is not None else None,
                "line_subtotal": str(item["line_subtotal"]) if item.get("line_subtotal") is not None else None,
            }
            for idx, item in enumerate(items)
        ]
        self._log_event(
            session, invoice, event_type, description,
            performed_by=user_id,
            metadata={"item_count": len(items), "items": item_summaries},
        )

    # ------------------------------------------------------------------
    # Events log (replaces get_status_history)
    # ------------------------------------------------------------------

    def get_events(self, session: Session, invoice_id: int, workspace_id: int) -> list:
        self._get_or_404(session, invoice_id, workspace_id)
        return invoice_event_dao.get_by_invoice(session, invoice_id=invoice_id, workspace_id=workspace_id)

    def get_items(self, session: Session, invoice_id: int, workspace_id: int) -> list:
        self._get_or_404(session, invoice_id, workspace_id)
        return invoice_item_dao.get_by_invoice(session, invoice_id=invoice_id, workspace_id=workspace_id)


# Singleton instance
account_invoice_manager = AccountInvoiceManager()
