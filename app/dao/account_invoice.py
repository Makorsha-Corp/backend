"""Account invoice DAO operations"""
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date
from decimal import Decimal
from app.dao.base import BaseDAO
from app.models.account_invoice import AccountInvoice
from app.schemas.account_invoice import AccountInvoiceCreate, AccountInvoiceUpdate


class AccountInvoiceDAO(BaseDAO[AccountInvoice, AccountInvoiceCreate, AccountInvoiceUpdate]):
    """DAO operations for AccountInvoice model"""

    def get_by_account(
        self, db: Session, *, account_id: int, workspace_id: int, skip: int = 0, limit: int = 100
    ) -> List[AccountInvoice]:
        """
        Get all invoices for an account (SECURITY-CRITICAL)

        Args:
            db: Database session
            account_id: Account ID
            workspace_id: Workspace ID to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of invoices for the account
        """
        return (
            db.query(AccountInvoice)
            .filter(
                AccountInvoice.workspace_id == workspace_id,
                AccountInvoice.account_id == account_id
            )
            .order_by(AccountInvoice.invoice_date.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_order(
        self, db: Session, *, order_id: int, workspace_id: int
    ) -> List[AccountInvoice]:
        """
        Get all invoices for an order (SECURITY-CRITICAL)

        Args:
            db: Database session
            order_id: Order ID
            workspace_id: Workspace ID to filter by

        Returns:
            List of invoices for the order
        """
        return (
            db.query(AccountInvoice)
            .filter(
                AccountInvoice.workspace_id == workspace_id,
                AccountInvoice.order_id == order_id
            )
            .all()
        )

    def get_by_status(
        self, db: Session, *, payment_status: str, workspace_id: int, skip: int = 0, limit: int = 100
    ) -> List[AccountInvoice]:
        """
        Get invoices by payment status (SECURITY-CRITICAL)

        Args:
            db: Database session
            payment_status: Payment status ('unpaid', 'partial', 'paid', 'overdue')
            workspace_id: Workspace ID to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of invoices with matching status
        """
        return (
            db.query(AccountInvoice)
            .filter(
                AccountInvoice.workspace_id == workspace_id,
                AccountInvoice.payment_status == payment_status
            )
            .order_by(AccountInvoice.due_date)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_type(
        self, db: Session, *, invoice_type: str, workspace_id: int, skip: int = 0, limit: int = 100
    ) -> List[AccountInvoice]:
        """
        Get invoices by type (payable or receivable) (SECURITY-CRITICAL)

        Args:
            db: Database session
            invoice_type: Invoice type ('payable' or 'receivable')
            workspace_id: Workspace ID to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of invoices with matching type
        """
        return (
            db.query(AccountInvoice)
            .filter(
                AccountInvoice.workspace_id == workspace_id,
                AccountInvoice.invoice_type == invoice_type
            )
            .order_by(AccountInvoice.invoice_date.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_unpaid_invoices(
        self, db: Session, *, workspace_id: int, skip: int = 0, limit: int = 100
    ) -> List[AccountInvoice]:
        """
        Get all unpaid and partially paid invoices (SECURITY-CRITICAL)

        Args:
            db: Database session
            workspace_id: Workspace ID to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of unpaid/partial invoices
        """
        return (
            db.query(AccountInvoice)
            .filter(
                AccountInvoice.workspace_id == workspace_id,
                AccountInvoice.payment_status.in_(['unpaid', 'partial', 'overdue'])
            )
            .order_by(AccountInvoice.due_date)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_overdue_invoices(
        self, db: Session, *, workspace_id: int, as_of_date: date = None
    ) -> List[AccountInvoice]:
        """
        Get all overdue invoices (SECURITY-CRITICAL)

        Args:
            db: Database session
            workspace_id: Workspace ID to filter by
            as_of_date: Date to check overdue status (defaults to today)

        Returns:
            List of overdue invoices
        """
        if as_of_date is None:
            as_of_date = date.today()

        return (
            db.query(AccountInvoice)
            .filter(
                AccountInvoice.workspace_id == workspace_id,
                AccountInvoice.payment_status.in_(['unpaid', 'partial']),
                AccountInvoice.due_date < as_of_date
            )
            .order_by(AccountInvoice.due_date)
            .all()
        )

    def update_paid_amount(
        self, db: Session, *, invoice_id: int, workspace_id: int, additional_payment: Decimal
    ) -> AccountInvoice:
        """
        Update paid amount for an invoice (SECURITY-CRITICAL)

        Args:
            db: Database session
            invoice_id: Invoice ID
            workspace_id: Workspace ID to filter by
            additional_payment: Amount to add to paid_amount

        Returns:
            Updated invoice
        """
        invoice = self.get_by_id_and_workspace(db, id=invoice_id, workspace_id=workspace_id)
        if invoice:
            invoice.paid_amount += additional_payment

            # Update payment status
            if invoice.paid_amount >= invoice.invoice_amount:
                invoice.payment_status = 'paid'
            elif invoice.paid_amount > 0:
                invoice.payment_status = 'partial'

            db.flush()
        return invoice

    def get_invoices_with_payments_enabled(
        self, db: Session, *, workspace_id: int, skip: int = 0, limit: int = 100
    ) -> List[AccountInvoice]:
        """
        Get invoices that have payments enabled

        Args:
            db: Database session
            workspace_id: Workspace ID to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of invoices with allow_payments=True
        """
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
