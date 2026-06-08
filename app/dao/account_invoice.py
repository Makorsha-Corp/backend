"""Account invoice DAO operations"""
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List, Optional
from datetime import date
from decimal import Decimal
from app.dao.base import BaseDAO
from app.models.account_invoice import AccountInvoice
from app.models.account import Account
from app.schemas.account_invoice import AccountInvoiceCreate, AccountInvoiceUpdate


class AccountInvoiceDAO(BaseDAO[AccountInvoice, AccountInvoiceCreate, AccountInvoiceUpdate]):
    """DAO operations for AccountInvoice model"""

    def list_invoices(
        self,
        db: Session,
        *,
        workspace_id: int,
        account_id: Optional[int] = None,
        invoice_type: Optional[str] = None,
        payment_status: Optional[str] = None,
        invoice_status: Optional[str] = None,
        invoice_number_search: Optional[str] = None,
        account_name_search: Optional[str] = None,
        invoice_date_from: Optional[date] = None,
        invoice_date_to: Optional[date] = None,
        due_date_from: Optional[date] = None,
        due_date_to: Optional[date] = None,
        amount_min: Optional[Decimal] = None,
        amount_max: Optional[Decimal] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[AccountInvoice]:
        """
        Unified invoice listing with all filters. JOINs Account to exclude
        soft-deleted accounts from results. (SECURITY-CRITICAL)
        """
        query = (
            db.query(AccountInvoice)
            .join(Account, AccountInvoice.account_id == Account.id)
            .filter(
                AccountInvoice.workspace_id == workspace_id,
                Account.is_deleted == False,
            )
        )

        if account_id is not None:
            query = query.filter(AccountInvoice.account_id == account_id)
        if invoice_type:
            query = query.filter(AccountInvoice.invoice_type == invoice_type)
        if payment_status:
            query = query.filter(AccountInvoice.payment_status == payment_status)
        if invoice_status:
            query = query.filter(AccountInvoice.invoice_status == invoice_status)
        if invoice_number_search:
            term = f"%{invoice_number_search}%"
            query = query.filter(
                or_(
                    AccountInvoice.invoice_number.ilike(term),
                    AccountInvoice.vendor_invoice_number.ilike(term),
                )
            )
        if account_name_search:
            query = query.filter(Account.name.ilike(f"%{account_name_search}%"))
        if invoice_date_from:
            query = query.filter(AccountInvoice.invoice_date >= invoice_date_from)
        if invoice_date_to:
            query = query.filter(AccountInvoice.invoice_date <= invoice_date_to)
        if due_date_from:
            query = query.filter(AccountInvoice.due_date >= due_date_from)
        if due_date_to:
            query = query.filter(AccountInvoice.due_date <= due_date_to)
        if amount_min is not None:
            query = query.filter(AccountInvoice.invoice_amount >= amount_min)
        if amount_max is not None:
            query = query.filter(AccountInvoice.invoice_amount <= amount_max)

        return (
            query
            .order_by(AccountInvoice.invoice_date.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_order(
        self, db: Session, *, order_id: int, workspace_id: int
    ) -> List[AccountInvoice]:
        """Get all invoices for an order (SECURITY-CRITICAL)"""
        return (
            db.query(AccountInvoice)
            .filter(
                AccountInvoice.workspace_id == workspace_id,
                AccountInvoice.order_id == order_id
            )
            .all()
        )

    def update_paid_amount(
        self, db: Session, *, invoice_id: int, workspace_id: int, additional_payment: Decimal
    ) -> AccountInvoice:
        """Update paid amount for an invoice (SECURITY-CRITICAL)"""
        invoice = self.get_by_id_and_workspace(db, id=invoice_id, workspace_id=workspace_id)
        if invoice:
            invoice.paid_amount += additional_payment

            if invoice.paid_amount >= invoice.invoice_amount:
                invoice.payment_status = 'paid'
            elif invoice.paid_amount > 0:
                invoice.payment_status = 'partial'

            db.flush()
        return invoice

    def get_overdue_invoices(
        self, db: Session, *, workspace_id: int, as_of_date: date = None
    ) -> List[AccountInvoice]:
        """
        Get all overdue invoices (SECURITY-CRITICAL)

        TODO: Replace with a cron job that updates payment_status to 'overdue'
              nightly for confirmed invoices past their due_date with unpaid/partial status.
        """
        if as_of_date is None:
            as_of_date = date.today()

        return (
            db.query(AccountInvoice)
            .join(Account, AccountInvoice.account_id == Account.id)
            .filter(
                AccountInvoice.workspace_id == workspace_id,
                Account.is_deleted == False,
                AccountInvoice.payment_status.in_(['unpaid', 'partial']),
                AccountInvoice.invoice_status != 'voided',
                AccountInvoice.due_date < as_of_date
            )
            .order_by(AccountInvoice.due_date)
            .all()
        )

    def get_invoices_with_payments_enabled(
        self, db: Session, *, workspace_id: int, skip: int = 0, limit: int = 100
    ) -> List[AccountInvoice]:
        """Get invoices that have payments enabled"""
        return (
            db.query(AccountInvoice)
            .filter(
                AccountInvoice.workspace_id == workspace_id,
                AccountInvoice.allow_payments == True
            )
            .order_by(AccountInvoice.invoice_date.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )


account_invoice_dao = AccountInvoiceDAO(AccountInvoice)
