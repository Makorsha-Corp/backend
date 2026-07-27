"""Expense order DAO. SECURITY: All queries MUST filter by workspace_id."""
from datetime import date
from decimal import Decimal
from typing import List, Optional, Tuple

from sqlalchemy import and_, case, desc, func, or_
from sqlalchemy.orm import Query, Session

from app.dao.base import BaseDAO
from app.models.account import Account
from app.models.expense_order import ExpenseOrder
from app.models.expense_order_item import ExpenseOrderItem
from app.schemas.expense_order import (
    ExpenseOrderCreate,
    ExpenseOrderItemCreate,
    ExpenseOrderItemUpdate,
    ExpenseOrderUpdate,
)

# Synthetic EO stage ids — match frontend EO_STAGE_FILTER_OPTIONS.
EO_STAGE_DRAFT = 1
EO_STAGE_INVOICED = 2
EO_STAGE_COMPLETE = 3


def _expense_order_is_complete_clause():
    return ExpenseOrder.completed_at.isnot(None)


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
            .order_by(desc(ExpenseOrder.expense_date), desc(ExpenseOrder.created_at))
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
