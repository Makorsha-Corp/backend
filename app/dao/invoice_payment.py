"""Invoice payment DAO operations"""
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from datetime import date, timedelta
from decimal import Decimal
from app.dao.base import BaseDAO
from app.models.invoice_payment import InvoicePayment
from app.schemas.invoice_payment import InvoicePaymentCreate, InvoicePaymentUpdate


class InvoicePaymentDAO(BaseDAO[InvoicePayment, InvoicePaymentCreate, InvoicePaymentUpdate]):
    """DAO operations for InvoicePayment model"""

    def get_by_invoice(
        self, db: Session, *, invoice_id: int, workspace_id: int, skip: int = 0, limit: int = 100
    ) -> List[InvoicePayment]:
        """
        Get all payments for an invoice (SECURITY-CRITICAL)

        Args:
            db: Database session
            invoice_id: Invoice ID
            workspace_id: Workspace ID to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of payments for the invoice
        """
        return (
            db.query(InvoicePayment)
            .filter(
                InvoicePayment.workspace_id == workspace_id,
                InvoicePayment.invoice_id == invoice_id
            )
            .order_by(InvoicePayment.payment_date.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_date_range(
        self, db: Session, *, workspace_id: int, start_date: date, end_date: date,
        skip: int = 0, limit: int = 100
    ) -> List[InvoicePayment]:
        """
        Get payments within a date range (SECURITY-CRITICAL)

        Args:
            db: Database session
            workspace_id: Workspace ID to filter by
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of payments in the date range
        """
        return (
            db.query(InvoicePayment)
            .filter(
                InvoicePayment.workspace_id == workspace_id,
                InvoicePayment.payment_date >= start_date,
                InvoicePayment.payment_date <= end_date
            )
            .order_by(InvoicePayment.payment_date.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_payment_method(
        self, db: Session, *, workspace_id: int, payment_method: str,
        skip: int = 0, limit: int = 100
    ) -> List[InvoicePayment]:
        """
        Get payments by payment method (SECURITY-CRITICAL)

        Args:
            db: Database session
            workspace_id: Workspace ID to filter by
            payment_method: Payment method (cash, bank_transfer, cheque, card)
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of payments with matching method
        """
        return (
            db.query(InvoicePayment)
            .filter(
                InvoicePayment.workspace_id == workspace_id,
                InvoicePayment.payment_method == payment_method
            )
            .order_by(InvoicePayment.payment_date.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_total_paid_for_invoice(
        self, db: Session, *, invoice_id: int, workspace_id: int
    ) -> Decimal:
        """
        Calculate total amount paid for an invoice (SECURITY-CRITICAL)

        Args:
            db: Database session
            invoice_id: Invoice ID
            workspace_id: Workspace ID to filter by

        Returns:
            Total payment amount
        """
        result = (
            db.query(func.sum(InvoicePayment.payment_amount))
            .filter(
                InvoicePayment.workspace_id == workspace_id,
                InvoicePayment.invoice_id == invoice_id
            )
            .scalar()
        )
        return result if result else Decimal('0.00')

    def get_recent_payments(
        self, db: Session, *, workspace_id: int, days: int = 30, limit: int = 50
    ) -> List[InvoicePayment]:
        """
        Get recent payments within last N days (SECURITY-CRITICAL)

        Args:
            db: Database session
            workspace_id: Workspace ID to filter by
            days: Number of days to look back
            limit: Maximum number of records to return

        Returns:
            List of recent payments
        """
        cutoff_date = date.today() - timedelta(days=days)
        return (
            db.query(InvoicePayment)
            .filter(
                InvoicePayment.workspace_id == workspace_id,
                InvoicePayment.payment_date >= cutoff_date
            )
            .order_by(InvoicePayment.payment_date.desc())
            .limit(limit)
            .all()
        )


invoice_payment_dao = InvoicePaymentDAO(InvoicePayment)
