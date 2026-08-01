"""Purchase order DAO. SECURITY: All queries MUST filter by workspace_id."""
from datetime import date, datetime, time
from decimal import Decimal
from typing import List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy import and_, case, desc, func, or_
from sqlalchemy.orm import Query, Session, joinedload

from app.dao.base import BaseDAO
from app.models.account import Account
from app.models.account_invoice import AccountInvoice
from app.models.item import Item
from app.models.machine import Machine
from app.models.project import Project
from app.models.project_component import ProjectComponent
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_order_item import PurchaseOrderItem
from app.models.status import Status
from app.schemas.purchase_order import PurchaseOrderCreate, PurchaseOrderUpdate, PurchaseOrderItemCreate, PurchaseOrderItemUpdate


def _purchase_order_is_fully_closed_clause():
    """Complete stage and paid — matches frontend isPurchaseOrderFullyClosed."""
    return and_(Status.name == "Complete", PurchaseOrder.paid.is_(True))


def _apply_purchase_order_hub_filters(
    query: Query,
    *,
    workspace_id: int,
    account_id: Optional[int] = None,
    invoice_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    status_ids: Optional[List[int]] = None,
    factory_id: Optional[int] = None,
    destination_type: Optional[str] = None,
    invoice_filter: Optional[str] = None,
    search: Optional[str] = None,
    exclude_complete: bool = True,
    exclude_voided: bool = True,
) -> Query:
    query = query.filter(PurchaseOrder.workspace_id == workspace_id)

    if account_id is not None:
        query = query.filter(PurchaseOrder.account_id == account_id)
    if invoice_id is not None:
        query = query.filter(PurchaseOrder.invoice_id == invoice_id)
    if date_from is not None:
        query = query.filter(PurchaseOrder.created_at >= datetime.combine(date_from, time.min))
    if date_to is not None:
        query = query.filter(PurchaseOrder.created_at <= datetime.combine(date_to, time.max))
    if status_ids:
        query = query.filter(PurchaseOrder.current_status_id.in_(status_ids))
    if destination_type:
        query = query.filter(PurchaseOrder.destination_type == destination_type)

    if factory_id is not None:
        session = query.session
        machine_ids = session.query(Machine.id).filter(
            Machine.workspace_id == workspace_id,
            Machine.factory_id == factory_id,
        )
        component_ids = (
            session.query(ProjectComponent.id)
            .join(Project, Project.id == ProjectComponent.project_id)
            .filter(
                ProjectComponent.workspace_id == workspace_id,
                Project.factory_id == factory_id,
            )
        )
        query = query.filter(
            or_(
                and_(
                    PurchaseOrder.destination_type == "storage",
                    PurchaseOrder.destination_id == factory_id,
                ),
                and_(
                    PurchaseOrder.destination_type == "machine",
                    PurchaseOrder.destination_id.in_(machine_ids),
                ),
                and_(
                    PurchaseOrder.destination_type == "project",
                    PurchaseOrder.destination_id.in_(component_ids),
                ),
            )
        )

    if invoice_filter == "invoiced":
        query = query.filter(PurchaseOrder.invoice_id.isnot(None))
    elif invoice_filter == "not_invoiced":
        query = query.filter(PurchaseOrder.invoice_id.is_(None))
    elif invoice_filter == "outstanding_payment":
        query = query.join(
            AccountInvoice,
            AccountInvoice.id == PurchaseOrder.invoice_id,
        ).filter(
            AccountInvoice.payment_status.isnot(None),
            AccountInvoice.payment_status != "paid",
        )

    if exclude_voided:
        query = query.filter(PurchaseOrder.voided.is_(False))

    if exclude_complete:
        query = query.join(PurchaseOrder.current_status).filter(
            ~_purchase_order_is_fully_closed_clause()
        )

    if search and search.strip():
        term = search.strip()
        query = query.outerjoin(Account, Account.id == PurchaseOrder.account_id).filter(
            or_(
                PurchaseOrder.po_number.ilike(f"%{term}%"),
                Account.name.ilike(f"%{term}%"),
            )
        )

    return query


def _hub_base_query(
    db: Session,
    *,
    workspace_id: int,
    **filters,
) -> Query:
    query = db.query(PurchaseOrder).options(joinedload(PurchaseOrder.current_status))
    return _apply_purchase_order_hub_filters(query, workspace_id=workspace_id, **filters)


class PurchaseOrderDAO(BaseDAO[PurchaseOrder, PurchaseOrderCreate, PurchaseOrderUpdate]):
    def get_by_workspace(
        self,
        db: Session,
        *,
        workspace_id: int,
        account_id: Optional[int] = None,
        invoice_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[PurchaseOrder]:
        query = (
            db.query(PurchaseOrder)
            .options(joinedload(PurchaseOrder.current_status))
            .filter(PurchaseOrder.workspace_id == workspace_id)
        )
        if account_id:
            query = query.filter(PurchaseOrder.account_id == account_id)
        if invoice_id is not None:
            query = query.filter(PurchaseOrder.invoice_id == invoice_id)
        return query.order_by(desc(PurchaseOrder.created_at)).offset(skip).limit(limit).all()

    def list_for_hub(
        self,
        db: Session,
        *,
        workspace_id: int,
        skip: int = 0,
        limit: int = 50,
        **filters,
    ) -> List[PurchaseOrder]:
        return (
            _hub_base_query(db, workspace_id=workspace_id, **filters)
            .order_by(desc(PurchaseOrder.created_at), desc(PurchaseOrder.id))
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count_for_hub(self, db: Session, *, workspace_id: int, **filters) -> int:
        filtered_ids = (
            _hub_base_query(db, workspace_id=workspace_id, **filters)
            .with_entities(PurchaseOrder.id)
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
    ) -> List[PurchaseOrder]:
        return (
            _hub_base_query(db, workspace_id=workspace_id, **filters)
            .order_by(desc(PurchaseOrder.updated_at), desc(PurchaseOrder.created_at))
            .limit(limit)
            .all()
        )

    def get_pending_highlights_for_hub(
        self, db: Session, *, workspace_id: int, **filters
    ) -> dict:
        base = (
            _hub_base_query(db, workspace_id=workspace_id, **filters)
            .join(PurchaseOrder.current_status)
        )

        planning_q = base.filter(Status.name == "Planning")
        planning_count = planning_q.count()
        planning_sample = (
            planning_q.order_by(desc(PurchaseOrder.updated_at)).limit(3).all()
        )

        missing_q = planning_q.filter(
            PurchaseOrder.invoice_id.is_(None),
            PurchaseOrder.account_id.isnot(None),
        )
        missing_count = missing_q.count()
        missing_sample = (
            missing_q.order_by(desc(PurchaseOrder.updated_at)).limit(3).all()
        )

        draft_sample = (
            base.filter(Status.name == "Draft")
            .order_by(PurchaseOrder.created_at.asc())
            .limit(5)
            .all()
        )

        def _highlight(order: PurchaseOrder) -> dict:
            status = order.current_status
            return {
                "id": order.id,
                "order_number": order.po_number,
                "status_name": status.name if status else None,
                "created_at": order.created_at,
            }

        return {
            "pending_planning_count": planning_count,
            "pending_planning": [_highlight(o) for o in planning_sample],
            "missing_invoice_count": missing_count,
            "missing_invoice": [_highlight(o) for o in missing_sample],
            "oldest_drafts": [_highlight(o) for o in draft_sample],
        }

    def aggregate_hub_stats(
        self, db: Session, *, workspace_id: int, **filters
    ) -> Tuple[int, Decimal, int, Decimal, int]:
        filtered_ids = (
            _hub_base_query(db, workspace_id=workspace_id, **filters)
            .with_entities(PurchaseOrder.id)
            .distinct()
            .subquery()
        )
        query = (
            db.query(PurchaseOrder)
            .filter(PurchaseOrder.id.in_(filtered_ids))
            .outerjoin(PurchaseOrder.current_status)
        )

        open_count_expr = case(
            (_purchase_order_is_fully_closed_clause(), 0),
            else_=1,
        )
        open_value_expr = case(
            (_purchase_order_is_fully_closed_clause(), 0),
            else_=PurchaseOrder.total_amount,
        )
        not_invoiced_expr = case((PurchaseOrder.invoice_id.is_(None), 1), else_=0)

        row = query.with_entities(
            func.count(PurchaseOrder.id),
            func.coalesce(func.sum(PurchaseOrder.total_amount), 0),
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

    def list_for_destination(
        self,
        db: Session,
        *,
        workspace_id: int,
        destination_type: str,
        destination_id: int,
    ) -> List[PurchaseOrder]:
        return (
            db.query(PurchaseOrder)
            .options(joinedload(PurchaseOrder.current_status))
            .filter(
                PurchaseOrder.workspace_id == workspace_id,
                PurchaseOrder.destination_type == destination_type,
                PurchaseOrder.destination_id == destination_id,
            )
            .order_by(desc(PurchaseOrder.created_at))
            .all()
        )

    def get_by_id_and_workspace(self, db: Session, *, id: int, workspace_id: int) -> Optional[PurchaseOrder]:
        return (
            db.query(PurchaseOrder)
            .options(joinedload(PurchaseOrder.current_status))
            .filter(PurchaseOrder.id == id, PurchaseOrder.workspace_id == workspace_id)
            .first()
        )

    def get_by_invoice_id(
        self, db: Session, *, invoice_id: int, workspace_id: int
    ) -> Optional[PurchaseOrder]:
        return (
            db.query(PurchaseOrder)
            .filter(
                PurchaseOrder.invoice_id == invoice_id,
                PurchaseOrder.workspace_id == workspace_id,
            )
            .first()
        )

    def get_next_number(self, db: Session, *, workspace_id: int) -> str:
        """Backward-compatible alias for allocate_po_number."""
        return self.allocate_po_number(db, workspace_id=workspace_id)

    def allocate_po_number(self, db: Session, *, workspace_id: int) -> str:
        """
        Next PO number for this workspace/year, skipping any po_number already
        taken globally (handles legacy global-unique constraint on po_number).
        """
        from datetime import datetime

        year = datetime.now().year
        prefix = f"PO-{year}-"

        rows = (
            db.query(PurchaseOrder.po_number)
            .filter(
                PurchaseOrder.workspace_id == workspace_id,
                PurchaseOrder.po_number.like(f"{prefix}%"),
            )
            .all()
        )
        max_seq = 0
        for (num,) in rows:
            try:
                max_seq = max(max_seq, int(str(num).rsplit("-", 1)[-1]))
            except ValueError:
                continue

        seq = max_seq + 1 if max_seq else 1
        for _ in range(1000):
            candidate = f"{prefix}{seq:03d}"
            taken = (
                db.query(PurchaseOrder.id)
                .filter(PurchaseOrder.po_number == candidate)
                .first()
            )
            if not taken:
                return candidate
            seq += 1

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not allocate a unique purchase order number",
        )


class PurchaseOrderItemDAO(BaseDAO[PurchaseOrderItem, PurchaseOrderItemCreate, PurchaseOrderItemUpdate]):
    def get_by_order(self, db: Session, *, purchase_order_id: int, workspace_id: int) -> List[PurchaseOrderItem]:
        return db.query(PurchaseOrderItem).filter(PurchaseOrderItem.purchase_order_id == purchase_order_id, PurchaseOrderItem.workspace_id == workspace_id).order_by(PurchaseOrderItem.line_number).all()

    def get_by_purchase_order_ids(
        self,
        db: Session,
        *,
        workspace_id: int,
        purchase_order_ids: List[int],
    ) -> List[PurchaseOrderItem]:
        if not purchase_order_ids:
            return []
        return (
            db.query(PurchaseOrderItem)
            .filter(
                PurchaseOrderItem.workspace_id == workspace_id,
                PurchaseOrderItem.purchase_order_id.in_(purchase_order_ids),
            )
            .order_by(PurchaseOrderItem.purchase_order_id, PurchaseOrderItem.line_number)
            .all()
        )

    def get_by_id_and_workspace(self, db: Session, *, id: int, workspace_id: int) -> Optional[PurchaseOrderItem]:
        return db.query(PurchaseOrderItem).filter(PurchaseOrderItem.id == id, PurchaseOrderItem.workspace_id == workspace_id).first()

    def summarize_by_purchase_order_ids(
        self,
        db: Session,
        *,
        workspace_id: int,
        purchase_order_ids: List[int],
    ) -> dict[int, dict]:
        if not purchase_order_ids:
            return {}
        rows = (
            db.query(
                PurchaseOrderItem.purchase_order_id,
                func.count(PurchaseOrderItem.id),
                func.coalesce(func.sum(PurchaseOrderItem.quantity_ordered), 0),
                func.coalesce(func.sum(PurchaseOrderItem.quantity_received), 0),
            )
            .filter(
                PurchaseOrderItem.workspace_id == workspace_id,
                PurchaseOrderItem.purchase_order_id.in_(purchase_order_ids),
            )
            .group_by(PurchaseOrderItem.purchase_order_id)
            .all()
        )
        return {
            po_id: {
                "item_count": int(count),
                "quantity_ordered_total": ordered,
                "quantity_received_total": received,
            }
            for po_id, count, ordered, received in rows
        }

    def preview_names_by_purchase_order_ids(
        self,
        db: Session,
        *,
        workspace_id: int,
        purchase_order_ids: List[int],
        limit: int = 4,
    ) -> dict[int, list[str]]:
        if not purchase_order_ids or limit <= 0:
            return {}
        rows = (
            db.query(
                PurchaseOrderItem.purchase_order_id,
                PurchaseOrderItem.item_id,
                Item.name,
            )
            .join(Item, PurchaseOrderItem.item_id == Item.id)
            .filter(
                PurchaseOrderItem.workspace_id == workspace_id,
                PurchaseOrderItem.purchase_order_id.in_(purchase_order_ids),
            )
            .order_by(PurchaseOrderItem.purchase_order_id, PurchaseOrderItem.line_number)
            .all()
        )
        previews: dict[int, list[str]] = {}
        for po_id, item_id, item_name in rows:
            bucket = previews.setdefault(po_id, [])
            if len(bucket) >= limit:
                continue
            bucket.append(item_name if item_name else f"Item #{item_id}")
        return previews


purchase_order_dao = PurchaseOrderDAO(PurchaseOrder)
purchase_order_item_dao = PurchaseOrderItemDAO(PurchaseOrderItem)
