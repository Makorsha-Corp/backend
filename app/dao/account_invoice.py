"""Account invoice DAO operations"""
from sqlalchemy.orm import Session, Query
from sqlalchemy import or_, func, case
from typing import List, Optional, Tuple
from datetime import date
from decimal import Decimal
from app.dao.base import BaseDAO
from app.models.account_invoice import AccountInvoice
from app.models.account import Account
from app.schemas.account_invoice import AccountInvoiceCreate, AccountInvoiceUpdate


class AccountInvoiceDAO(BaseDAO[AccountInvoice, AccountInvoiceCreate, AccountInvoiceUpdate]):
    """DAO operations for AccountInvoice model"""

    def _build_filtered_query(
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
        open_balance_only: bool = False,
    ) -> Query:
        """
        Base query with all list filters. JOINs Account to exclude
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
        if open_balance_only:
            query = query.filter(
                AccountInvoice.invoice_status != 'voided',
                AccountInvoice.payment_status.in_(['unpaid', 'partial', 'overdue']),
            )

        return query

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
        """Unified invoice listing with all filters."""
        query = self._build_filtered_query(
            db,
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
        return (
            query
            .order_by(AccountInvoice.invoice_date.desc(), AccountInvoice.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def list_invoices_page(
        self,
        db: Session,
        *,
        workspace_id: int,
        account_id: int,
        open_balance_only: bool = False,
        prioritize_purchase_order_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 10,
    ) -> Tuple[List[AccountInvoice], int]:
        """Paginated invoice listing with total count."""
        return self.list_invoices_page_filtered(
            db,
            workspace_id=workspace_id,
            account_id=account_id,
            open_balance_only=open_balance_only,
            prioritize_purchase_order_id=prioritize_purchase_order_id,
            skip=skip,
            limit=limit,
        )

    def _open_balance_subquery(self, db: Session, *, workspace_id: int, invoice_type: str):
        return (
            db.query(
                AccountInvoice.account_id.label("account_id"),
                func.coalesce(func.sum(AccountInvoice.outstanding_amount), 0).label(
                    "outstanding_total"
                ),
                func.count(AccountInvoice.id).label("open_count"),
                func.max(
                    case((AccountInvoice.payment_status == "overdue", 1), else_=0)
                ).label("has_overdue"),
            )
            .join(Account, AccountInvoice.account_id == Account.id)
            .filter(
                AccountInvoice.workspace_id == workspace_id,
                Account.is_deleted == False,
                AccountInvoice.invoice_type == invoice_type,
                AccountInvoice.invoice_status != "voided",
                AccountInvoice.payment_status.in_(["unpaid", "partial", "overdue"]),
            )
            .group_by(AccountInvoice.account_id)
            .subquery()
        )

    def list_accounts_hub_page(
        self,
        db: Session,
        *,
        workspace_id: int,
        section: str = "overview",
        search: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[tuple], int]:
        """
        Paginated accounts for the accounts hub with open-balance rollups.
        section: overview | payable | receivable
        """
        payable_sq = self._open_balance_subquery(db, workspace_id=workspace_id, invoice_type="payable")
        receivable_sq = self._open_balance_subquery(
            db, workspace_id=workspace_id, invoice_type="receivable"
        )

        query = (
            db.query(Account, payable_sq, receivable_sq)
            .outerjoin(payable_sq, Account.id == payable_sq.c.account_id)
            .outerjoin(receivable_sq, Account.id == receivable_sq.c.account_id)
            .filter(
                Account.workspace_id == workspace_id,
                Account.is_active == True,
                Account.is_deleted == False,
            )
        )

        if section == "payable":
            query = query.filter(payable_sq.c.outstanding_total > 0)
        elif section == "receivable":
            query = query.filter(receivable_sq.c.outstanding_total > 0)

        if search:
            query = query.filter(Account.name.ilike(f"%{search}%"))

        total = query.count()
        rows = (
            query.order_by(Account.name.asc(), Account.id.asc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return rows, total

    def summarize_open_hub_type(
        self,
        db: Session,
        *,
        workspace_id: int,
        invoice_type: str,
    ) -> Tuple[int, Decimal, int, int]:
        """Open-balance aggregates for one invoice type across the workspace."""
        query = self._build_filtered_query(
            db,
            workspace_id=workspace_id,
            invoice_type=invoice_type,
            open_balance_only=True,
        )
        open_count = query.count()
        outstanding_row = query.with_entities(
            func.coalesce(func.sum(AccountInvoice.outstanding_amount), 0),
        ).one()
        overdue_count = query.filter(AccountInvoice.payment_status == "overdue").count()
        accounts_with_open = (
            query.with_entities(func.count(func.distinct(AccountInvoice.account_id))).scalar()
            or 0
        )
        return open_count, Decimal(outstanding_row[0]), overdue_count, int(accounts_with_open)

    def count_accounts_with_any_open_balance(
        self,
        db: Session,
        *,
        workspace_id: int,
    ) -> int:
        query = self._build_filtered_query(
            db,
            workspace_id=workspace_id,
            open_balance_only=True,
        )
        return (
            query.with_entities(func.count(func.distinct(AccountInvoice.account_id))).scalar()
            or 0
        )

    def list_invoices_page_filtered(
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
        open_balance_only: bool = False,
        prioritize_purchase_order_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 10,
    ) -> Tuple[List[AccountInvoice], int]:
        """Paginated invoice listing with filters and total count."""
        query = self._build_filtered_query(
            db,
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
            open_balance_only=open_balance_only,
        )
        total = query.count()

        if prioritize_purchase_order_id is not None:
            priority = case(
                (
                    (AccountInvoice.order_id == prioritize_purchase_order_id)
                    & (AccountInvoice.order_type == "purchase_order"),
                    0,
                ),
                else_=1,
            )
            query = query.order_by(
                priority,
                AccountInvoice.invoice_date.desc(),
                AccountInvoice.id.desc(),
            )
        else:
            query = query.order_by(
                AccountInvoice.invoice_date.desc(),
                AccountInvoice.id.desc(),
            )

        items = query.offset(skip).limit(limit).all()
        return items, total

    def summarize_invoices(
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
    ) -> Tuple[int, Decimal, Decimal, Decimal]:
        """
        Aggregate invoice counts and amounts for matching filters.
        Financial totals exclude voided invoices (matches frontend rollups).
        """
        query = self._build_filtered_query(
            db,
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

        invoice_count = query.count()

        financial = query.filter(AccountInvoice.invoice_status != 'voided').with_entities(
            func.coalesce(func.sum(AccountInvoice.invoice_amount), 0),
            func.coalesce(func.sum(AccountInvoice.paid_amount), 0),
            func.coalesce(func.sum(AccountInvoice.outstanding_amount), 0),
        ).one()

        return (
            invoice_count,
            Decimal(financial[0]),
            Decimal(financial[1]),
            Decimal(financial[2]),
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
