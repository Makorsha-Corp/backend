"""Expense order DAO. SECURITY: All queries MUST filter by workspace_id."""
import calendar
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, case, desc, func, or_
from sqlalchemy.orm import Query, Session

from app.dao.base import BaseDAO
from app.models.account import Account
from app.models.account_invoice import AccountInvoice
from app.models.expense_order import ExpenseOrder
from app.models.expense_order_item import ExpenseOrderItem
from app.schemas.expense_order import (
    ExpenseOrderCreate,
    ExpenseOrderItemCreate,
    ExpenseOrderItemUpdate,
    ExpenseOrderUpdate,
)
from app.utils.time import utcnow

# Synthetic EO stage ids — match frontend EO_STAGE_FILTER_OPTIONS.
EO_STAGE_DRAFT = 1
EO_STAGE_INVOICED = 2
EO_STAGE_COMPLETE = 3

EO_CATEGORY_LABELS: Dict[str, str] = {
    "factory": "Factory",
    "department": "Department",
    "other": "Other",
}

EO_STAGE_LABELS: Dict[str, str] = {
    "draft": "Draft",
    "invoiced": "Invoiced",
    "complete": "Complete",
}

EO_DUE_BUCKET_DEFS: Tuple[Tuple[str, str], ...] = (
    ("overdue", "Overdue"),
    ("due_this_week", "Due this week"),
    ("due_later_this_month", "Due later this month"),
    ("no_due_date", "No due date"),
)

EO_UNPAID_BUCKET_DEFS: Tuple[Tuple[str, str], ...] = (
    ("unpaid", "Unpaid"),
    ("partial", "Partial"),
    ("overdue", "Overdue"),
)


def _expense_order_is_complete_clause():
    return ExpenseOrder.completed_at.isnot(None)


def _expense_order_stage_key_expr():
    """SQL CASE → draft | invoiced | complete (matches frontend deriveExpenseOrderStageFromOrder)."""
    return case(
        (_expense_order_is_complete_clause(), "complete"),
        (ExpenseOrder.invoice_id.isnot(None), "invoiced"),
        else_="draft",
    )


def _category_label(slug: str) -> str:
    return EO_CATEGORY_LABELS.get(slug, slug.replace("_", " ").title())


def _due_date_bucket(due: date | None, *, today: date, end_of_week: date, end_of_month: date) -> str:
    if due is None:
        return "no_due_date"
    if due < today:
        return "overdue"
    if due <= end_of_week:
        return "due_this_week"
    if due <= end_of_month:
        return "due_later_this_month"
    return "beyond_scope"


def _due_window_dates() -> Tuple[date, date, date]:
    today = utcnow().date()
    end_of_week = today + timedelta(days=(6 - today.weekday()))
    last_day = calendar.monthrange(today.year, today.month)[1]
    end_of_month = date(today.year, today.month, last_day)
    return today, end_of_week, end_of_month


def _apply_expense_order_stage_filter(query: Query, status_ids: List[int]) -> Query:
    stage_clauses = []
    for stage_id in status_ids:
        if stage_id == EO_STAGE_DRAFT:
            stage_clauses.append(
                and_(
                    ExpenseOrder.completed_at.is_(None),
                    ExpenseOrder.invoice_id.is_(None),
                )
            )
        elif stage_id == EO_STAGE_INVOICED:
            stage_clauses.append(
                and_(
                    ExpenseOrder.completed_at.is_(None),
                    ExpenseOrder.invoice_id.isnot(None),
                )
            )
        elif stage_id == EO_STAGE_COMPLETE:
            stage_clauses.append(_expense_order_is_complete_clause())
    if stage_clauses:
        query = query.filter(or_(*stage_clauses))
    return query


def _apply_expense_order_hub_filters(
    query: Query,
    *,
    workspace_id: int,
    expense_category: Optional[str] = None,
    account_id: Optional[int] = None,
    invoice_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    status_ids: Optional[List[int]] = None,
    invoice_filter: Optional[str] = None,
    search: Optional[str] = None,
    exclude_complete: bool = True,
    exclude_voided: bool = True,
) -> Query:
    query = query.filter(ExpenseOrder.workspace_id == workspace_id)

    if expense_category:
        query = query.filter(ExpenseOrder.expense_category == expense_category)
    if account_id is not None:
        query = query.filter(ExpenseOrder.account_id == account_id)
    if invoice_id is not None:
        query = query.filter(ExpenseOrder.invoice_id == invoice_id)
    if date_from is not None:
        query = query.filter(ExpenseOrder.expense_date >= date_from)
    if date_to is not None:
        query = query.filter(ExpenseOrder.expense_date <= date_to)
    if status_ids:
        query = _apply_expense_order_stage_filter(query, status_ids)

    if invoice_filter == "invoiced":
        query = query.filter(ExpenseOrder.invoice_id.isnot(None))
    elif invoice_filter == "not_invoiced":
        query = query.filter(ExpenseOrder.invoice_id.is_(None))

    if exclude_voided:
        query = query.filter(ExpenseOrder.voided.is_(False))

    if exclude_complete:
        query = query.filter(ExpenseOrder.completed_at.is_(None))

    if search and search.strip():
        term = search.strip()
        label_filters = []
        lowered = term.lower()
        for slug, label in (
            ("factory", "Factory"),
            ("department", "Department"),
            ("other", "Other"),
        ):
            if lowered in label.lower() or label.lower().startswith(lowered):
                label_filters.append(ExpenseOrder.expense_category == slug)
        query = query.outerjoin(Account, Account.id == ExpenseOrder.account_id).filter(
            or_(
                ExpenseOrder.expense_number.ilike(f"%{term}%"),
                ExpenseOrder.expense_category.ilike(f"%{term}%"),
                Account.name.ilike(f"%{term}%"),
                *label_filters,
            )
        )

    return query


def _hub_base_query(db: Session, *, workspace_id: int, **filters) -> Query:
    query = db.query(ExpenseOrder)
    return _apply_expense_order_hub_filters(query, workspace_id=workspace_id, **filters)


class ExpenseOrderDAO(BaseDAO[ExpenseOrder, ExpenseOrderCreate, ExpenseOrderUpdate]):
    def get_by_workspace(
        self,
        db: Session,
        *,
        workspace_id: int,
        expense_category: Optional[str] = None,
        account_id: Optional[int] = None,
        invoice_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[ExpenseOrder]:
        query = db.query(ExpenseOrder).filter(ExpenseOrder.workspace_id == workspace_id)
        if expense_category:
            query = query.filter(ExpenseOrder.expense_category == expense_category)
        if account_id:
            query = query.filter(ExpenseOrder.account_id == account_id)
        if invoice_id is not None:
            query = query.filter(ExpenseOrder.invoice_id == invoice_id)
        return query.order_by(desc(ExpenseOrder.created_at)).offset(skip).limit(limit).all()

    def list_for_hub(
        self,
        db: Session,
        *,
        workspace_id: int,
        skip: int = 0,
        limit: int = 50,
        **filters,
    ) -> List[ExpenseOrder]:
        return (
            _hub_base_query(db, workspace_id=workspace_id, **filters)
            .order_by(
                desc(ExpenseOrder.expense_date),
                desc(ExpenseOrder.created_at),
                desc(ExpenseOrder.id),
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count_for_hub(self, db: Session, *, workspace_id: int, **filters) -> int:
        filtered_ids = (
            _hub_base_query(db, workspace_id=workspace_id, **filters)
            .with_entities(ExpenseOrder.id)
            .distinct()
            .subquery()
        )
        return int(db.query(func.count()).select_from(filtered_ids).scalar() or 0)

    def list_recent_for_hub(
        self,
        db: Session,
        *,
        workspace_id: int,
        limit: int = 10,
        **filters,
    ) -> List[ExpenseOrder]:
        return (
            _hub_base_query(db, workspace_id=workspace_id, **filters)
            .order_by(desc(ExpenseOrder.updated_at), desc(ExpenseOrder.created_at))
            .limit(limit)
            .all()
        )

    def aggregate_hub_stats(
        self, db: Session, *, workspace_id: int, **filters
    ) -> Tuple[int, Decimal, int, Decimal, int]:
        filtered_ids = (
            _hub_base_query(db, workspace_id=workspace_id, **filters)
            .with_entities(ExpenseOrder.id)
            .distinct()
            .subquery()
        )
        query = db.query(ExpenseOrder).filter(ExpenseOrder.id.in_(filtered_ids))

        open_count_expr = case(
            (_expense_order_is_complete_clause(), 0),
            else_=1,
        )
        open_value_expr = case(
            (_expense_order_is_complete_clause(), 0),
            else_=ExpenseOrder.total_amount,
        )
        not_invoiced_expr = case((ExpenseOrder.invoice_id.is_(None), 1), else_=0)

        row = query.with_entities(
            func.count(ExpenseOrder.id),
            func.coalesce(func.sum(ExpenseOrder.total_amount), 0),
            func.coalesce(func.sum(open_count_expr), 0),
            func.coalesce(func.sum(open_value_expr), 0),
            func.coalesce(func.sum(not_invoiced_expr), 0),
        ).one()

        return (
            int(row[0] or 0),
            Decimal(str(row[1] or 0)),
            int(row[2] or 0),
            Decimal(str(row[3] or 0)),
            int(row[4] or 0),
        )

    def _filtered_orders_query(
        self, db: Session, *, workspace_id: int, **filters
    ) -> Query:
        filtered_ids = (
            _hub_base_query(db, workspace_id=workspace_id, **filters)
            .with_entities(ExpenseOrder.id)
            .distinct()
            .subquery()
        )
        return db.query(ExpenseOrder).filter(ExpenseOrder.id.in_(filtered_ids))

    def aggregate_financial_snapshot_filtered(
        self, db: Session, *, workspace_id: int, **filters
    ) -> Dict[str, Any]:
        """Category, stage, and open-by-account buckets for hub filter scope."""
        base = self._filtered_orders_query(db, workspace_id=workspace_id, **filters)

        category_rows = (
            base.with_entities(
                ExpenseOrder.expense_category,
                func.count(ExpenseOrder.id),
                func.coalesce(func.sum(ExpenseOrder.total_amount), 0),
            )
            .group_by(ExpenseOrder.expense_category)
            .order_by(desc(func.coalesce(func.sum(ExpenseOrder.total_amount), 0)))
            .all()
        )
        category_breakdown = []
        other_count = 0
        other_value = Decimal("0")
        for idx, (slug, count, total) in enumerate(category_rows):
            value = Decimal(str(total or 0))
            if idx < 6:
                category_breakdown.append(
                    {
                        "key": slug,
                        "label": _category_label(slug),
                        "count": int(count or 0),
                        "total_value": value,
                    }
                )
            else:
                other_count += int(count or 0)
                other_value += value
        if other_count > 0:
            category_breakdown.append(
                {
                    "key": "other",
                    "label": "Other",
                    "count": other_count,
                    "total_value": other_value,
                }
            )

        stage_key = _expense_order_stage_key_expr()
        stage_rows = (
            base.with_entities(
                stage_key.label("stage_key"),
                func.count(ExpenseOrder.id),
                func.coalesce(func.sum(ExpenseOrder.total_amount), 0),
            )
            .group_by(stage_key)
            .all()
        )
        stage_map = {
            str(row[0]): (int(row[1] or 0), Decimal(str(row[2] or 0))) for row in stage_rows
        }
        stage_pipeline = [
            {
                "key": key,
                "label": EO_STAGE_LABELS[key],
                "count": stage_map.get(key, (0, Decimal("0")))[0],
                "total_value": stage_map.get(key, (0, Decimal("0")))[1],
            }
            for key in ("draft", "invoiced", "complete")
        ]

        open_base = base.filter(ExpenseOrder.completed_at.is_(None))
        account_rows = (
            open_base.join(Account, Account.id == ExpenseOrder.account_id)
            .with_entities(
                ExpenseOrder.account_id,
                Account.name,
                func.count(ExpenseOrder.id),
                func.coalesce(func.sum(ExpenseOrder.total_amount), 0),
            )
            .group_by(ExpenseOrder.account_id, Account.name)
            .order_by(desc(func.coalesce(func.sum(ExpenseOrder.total_amount), 0)))
            .limit(5)
            .all()
        )
        open_by_account = [
            {
                "account_id": int(account_id),
                "account_name": name,
                "count": int(count or 0),
                "total_value": Decimal(str(total or 0)),
            }
            for account_id, name, count, total in account_rows
            if account_id is not None
        ]

        return {
            "category_breakdown": category_breakdown,
            "stage_pipeline": stage_pipeline,
            "open_by_account": open_by_account,
        }

    def aggregate_financial_snapshot_actionable(
        self, db: Session, *, workspace_id: int
    ) -> Dict[str, Any]:
        """Due timeline and unpaid pipeline for all open non-voided workspace orders."""
        today, end_of_week, end_of_month = _due_window_dates()

        open_orders = (
            db.query(ExpenseOrder)
            .filter(
                ExpenseOrder.workspace_id == workspace_id,
                ExpenseOrder.voided.is_(False),
                ExpenseOrder.completed_at.is_(None),
            )
            .order_by(ExpenseOrder.due_date.asc().nulls_last(), ExpenseOrder.expense_number)
            .all()
        )

        due_buckets: Dict[str, Dict[str, Any]] = {
            key: {"key": key, "label": label, "count": 0, "total_value": Decimal("0"), "samples": []}
            for key, label in EO_DUE_BUCKET_DEFS
        }
        for order in open_orders:
            bucket_key = _due_date_bucket(
                order.due_date, today=today, end_of_week=end_of_week, end_of_month=end_of_month
            )
            if bucket_key not in due_buckets:
                continue
            bucket = due_buckets[bucket_key]
            bucket["count"] += 1
            bucket["total_value"] += Decimal(str(order.total_amount or 0))
            if len(bucket["samples"]) < 3:
                sublabel = order.due_date.isoformat() if order.due_date else None
                bucket["samples"].append(
                    {
                        "id": order.id,
                        "order_number": order.expense_number,
                        "total_value": Decimal(str(order.total_amount or 0)),
                        "sublabel": sublabel,
                    }
                )

        due_timeline = [due_buckets[key] for key, _ in EO_DUE_BUCKET_DEFS]

        unpaid_rows = (
            db.query(ExpenseOrder, AccountInvoice)
            .join(AccountInvoice, AccountInvoice.id == ExpenseOrder.invoice_id)
            .filter(
                ExpenseOrder.workspace_id == workspace_id,
                ExpenseOrder.voided.is_(False),
                ExpenseOrder.completed_at.is_(None),
                ExpenseOrder.invoice_id.isnot(None),
                AccountInvoice.invoice_status != "voided",
                AccountInvoice.payment_status.in_(("unpaid", "partial", "overdue")),
            )
            .order_by(desc(AccountInvoice.invoice_amount - AccountInvoice.paid_amount))
            .all()
        )

        unpaid_buckets: Dict[str, Dict[str, Any]] = {
            key: {
                "key": key,
                "label": label,
                "count": 0,
                "outstanding_value": Decimal("0"),
                "samples": [],
            }
            for key, label in EO_UNPAID_BUCKET_DEFS
        }
        for order, invoice in unpaid_rows:
            status = invoice.payment_status
            if status not in unpaid_buckets:
                continue
            outstanding = Decimal(str(invoice.invoice_amount or 0)) - Decimal(
                str(invoice.paid_amount or 0)
            )
            bucket = unpaid_buckets[status]
            bucket["count"] += 1
            bucket["outstanding_value"] += outstanding
            if len(bucket["samples"]) < 3:
                bucket["samples"].append(
                    {
                        "id": order.id,
                        "order_number": order.expense_number,
                        "total_value": outstanding,
                        "sublabel": status,
                    }
                )

        unpaid_pipeline = [unpaid_buckets[key] for key, _ in EO_UNPAID_BUCKET_DEFS]

        return {
            "due_timeline": due_timeline,
            "unpaid_pipeline": unpaid_pipeline,
        }

    def get_by_id_and_workspace(
        self, db: Session, *, id: int, workspace_id: int
    ) -> Optional[ExpenseOrder]:
        return (
            db.query(ExpenseOrder)
            .filter(ExpenseOrder.id == id, ExpenseOrder.workspace_id == workspace_id)
            .first()
        )

    def get_next_number(self, db: Session, *, workspace_id: int) -> str:
        from datetime import datetime

        year = datetime.now().year
        prefix = f"EXP-{year}-"
        last = (
            db.query(ExpenseOrder)
            .filter(
                ExpenseOrder.workspace_id == workspace_id,
                ExpenseOrder.expense_number.like(f"{prefix}%"),
            )
            .order_by(desc(ExpenseOrder.expense_number))
            .first()
        )
        if last:
            try:
                return f"{prefix}{int(last.expense_number.split('-')[-1]) + 1:03d}"
            except (ValueError, IndexError):
                pass
        return f"{prefix}001"


class ExpenseOrderItemDAO(
    BaseDAO[ExpenseOrderItem, ExpenseOrderItemCreate, ExpenseOrderItemUpdate]
):
    def get_by_order(
        self, db: Session, *, expense_order_id: int, workspace_id: int
    ) -> List[ExpenseOrderItem]:
        return (
            db.query(ExpenseOrderItem)
            .filter(
                ExpenseOrderItem.expense_order_id == expense_order_id,
                ExpenseOrderItem.workspace_id == workspace_id,
            )
            .order_by(ExpenseOrderItem.line_number)
            .all()
        )

    def get_by_id_and_workspace(
        self, db: Session, *, id: int, workspace_id: int
    ) -> Optional[ExpenseOrderItem]:
        return (
            db.query(ExpenseOrderItem)
            .filter(ExpenseOrderItem.id == id, ExpenseOrderItem.workspace_id == workspace_id)
            .first()
        )


expense_order_dao = ExpenseOrderDAO(ExpenseOrder)
expense_order_item_dao = ExpenseOrderItemDAO(ExpenseOrderItem)
