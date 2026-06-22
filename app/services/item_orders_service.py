"""Orders that include a catalog item."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import Date, and_, cast, func
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.managers.item_manager import item_manager
from app.models.account import Account
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_order_item import PurchaseOrderItem
from app.models.sales_order import SalesOrder
from app.models.sales_order_item import SalesOrderItem
from app.models.status import Status
from app.models.transfer_order import TransferOrder
from app.models.transfer_order_item import TransferOrderItem
from app.models.work_order import WorkOrder
from app.models.work_order_item import WorkOrderItem
from app.schemas.item_orders import ItemOrderRowResponse, ItemOrdersListResponse, ItemOrderType


def _dec(value) -> Decimal:
    if value is None:
        return Decimal('0')
    return Decimal(str(value))


def _in_date_range(column, from_date: date, to_date: date):
    return and_(column >= from_date, column <= to_date)


def _weighted_unit_price(line_total: Decimal, quantity: Decimal) -> Decimal | None:
    if quantity <= 0:
        return None
    return line_total / quantity


class ItemOrdersService:
    def get_orders_for_item(
        self,
        db: Session,
        *,
        workspace_id: int,
        item_id: int,
        skip: int = 0,
        limit: int = 50,
        order_type: Optional[ItemOrderType] = None,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
    ) -> ItemOrdersListResponse:
        item = item_manager.get_item(db, item_id, workspace_id)
        if not item:
            raise NotFoundError(f"Item with ID {item_id} not found")

        rows: List[ItemOrderRowResponse] = []

        if order_type is None or order_type == 'purchase_order':
            rows.extend(
                self._purchase_rows(
                    db,
                    workspace_id=workspace_id,
                    item_id=item_id,
                    from_date=from_date,
                    to_date=to_date,
                )
            )
        if order_type is None or order_type == 'transfer_order':
            rows.extend(
                self._transfer_rows(
                    db,
                    workspace_id=workspace_id,
                    item_id=item_id,
                    from_date=from_date,
                    to_date=to_date,
                )
            )
        if order_type is None or order_type == 'sales_order':
            rows.extend(
                self._sales_rows(
                    db,
                    workspace_id=workspace_id,
                    item_id=item_id,
                    from_date=from_date,
                    to_date=to_date,
                )
            )
        if order_type is None or order_type == 'work_order':
            rows.extend(
                self._work_rows(
                    db,
                    workspace_id=workspace_id,
                    item_id=item_id,
                    from_date=from_date,
                    to_date=to_date,
                )
            )

        rows.sort(key=lambda row: row.created_at, reverse=True)
        total = len(rows)
        page = rows[skip : skip + limit]
        return ItemOrdersListResponse(items=page, total=total)

    def _purchase_rows(
        self,
        db: Session,
        *,
        workspace_id: int,
        item_id: int,
        from_date: Optional[date],
        to_date: Optional[date],
    ) -> List[ItemOrderRowResponse]:
        order_date_col = func.coalesce(
            PurchaseOrder.order_date,
            cast(PurchaseOrder.created_at, Date),
        )
        filters = [
            PurchaseOrder.workspace_id == workspace_id,
            PurchaseOrderItem.item_id == item_id,
        ]
        if from_date is not None and to_date is not None:
            filters.append(_in_date_range(order_date_col, from_date, to_date))

        results = (
            db.query(
                PurchaseOrder.id,
                PurchaseOrder.po_number,
                order_date_col.label('order_date'),
                PurchaseOrder.created_at,
                func.sum(PurchaseOrderItem.quantity_ordered).label('quantity'),
                func.sum(PurchaseOrderItem.line_subtotal).label('line_total'),
                Account.name,
                Status.name,
            )
            .join(
                PurchaseOrderItem,
                PurchaseOrderItem.purchase_order_id == PurchaseOrder.id,
            )
            .outerjoin(Account, PurchaseOrder.account_id == Account.id)
            .outerjoin(Status, PurchaseOrder.current_status_id == Status.id)
            .filter(*filters)
            .group_by(
                PurchaseOrder.id,
                PurchaseOrder.po_number,
                order_date_col,
                PurchaseOrder.created_at,
                Account.name,
                Status.name,
            )
            .all()
        )

        rows: List[ItemOrderRowResponse] = []
        for po_id, po_number, order_date, created_at, qty, line_total, account_name, status_name in results:
            quantity = _dec(qty)
            total = _dec(line_total)
            rows.append(
                ItemOrderRowResponse(
                    order_type='purchase_order',
                    order_id=po_id,
                    order_number=po_number,
                    order_date=order_date,
                    quantity=quantity,
                    unit_price=_weighted_unit_price(total, quantity),
                    line_total=total if total > 0 else None,
                    status_name=status_name,
                    account_name=account_name,
                    created_at=created_at,
                )
            )
        return rows

    def _transfer_rows(
        self,
        db: Session,
        *,
        workspace_id: int,
        item_id: int,
        from_date: Optional[date],
        to_date: Optional[date],
    ) -> List[ItemOrderRowResponse]:
        order_date_col = func.coalesce(
            TransferOrder.order_date,
            cast(TransferOrder.created_at, Date),
        )
        filters = [
            TransferOrder.workspace_id == workspace_id,
            TransferOrderItem.item_id == item_id,
        ]
        if from_date is not None and to_date is not None:
            filters.append(_in_date_range(order_date_col, from_date, to_date))

        results = (
            db.query(
                TransferOrder.id,
                TransferOrder.transfer_number,
                order_date_col.label('order_date'),
                TransferOrder.created_at,
                func.sum(TransferOrderItem.quantity).label('quantity'),
                Status.name,
            )
            .join(
                TransferOrderItem,
                TransferOrderItem.transfer_order_id == TransferOrder.id,
            )
            .outerjoin(Status, TransferOrder.current_status_id == Status.id)
            .filter(*filters)
            .group_by(
                TransferOrder.id,
                TransferOrder.transfer_number,
                order_date_col,
                TransferOrder.created_at,
                Status.name,
            )
            .all()
        )

        rows: List[ItemOrderRowResponse] = []
        for to_id, transfer_number, order_date, created_at, qty, status_name in results:
            rows.append(
                ItemOrderRowResponse(
                    order_type='transfer_order',
                    order_id=to_id,
                    order_number=transfer_number,
                    order_date=order_date,
                    quantity=_dec(qty),
                    status_name=status_name,
                    created_at=created_at,
                )
            )
        return rows

    def _sales_rows(
        self,
        db: Session,
        *,
        workspace_id: int,
        item_id: int,
        from_date: Optional[date],
        to_date: Optional[date],
    ) -> List[ItemOrderRowResponse]:
        order_date_col = func.coalesce(
            SalesOrder.order_date,
            cast(SalesOrder.created_at, Date),
        )
        filters = [
            SalesOrder.workspace_id == workspace_id,
            SalesOrderItem.item_id == item_id,
        ]
        if from_date is not None and to_date is not None:
            filters.append(_in_date_range(order_date_col, from_date, to_date))

        results = (
            db.query(
                SalesOrder.id,
                SalesOrder.sales_order_number,
                order_date_col.label('order_date'),
                SalesOrder.created_at,
                func.sum(SalesOrderItem.quantity_ordered).label('quantity'),
                func.sum(SalesOrderItem.line_total).label('line_total'),
                Account.name,
                Status.name,
            )
            .join(
                SalesOrderItem,
                SalesOrderItem.sales_order_id == SalesOrder.id,
            )
            .outerjoin(Account, SalesOrder.account_id == Account.id)
            .outerjoin(Status, SalesOrder.current_status_id == Status.id)
            .filter(*filters)
            .group_by(
                SalesOrder.id,
                SalesOrder.sales_order_number,
                order_date_col,
                SalesOrder.created_at,
                Account.name,
                Status.name,
            )
            .all()
        )

        rows: List[ItemOrderRowResponse] = []
        for so_id, so_number, order_date, created_at, qty, line_total, account_name, status_name in results:
            quantity = _dec(qty)
            total = _dec(line_total)
            rows.append(
                ItemOrderRowResponse(
                    order_type='sales_order',
                    order_id=so_id,
                    order_number=so_number,
                    order_date=order_date,
                    quantity=quantity,
                    unit_price=_weighted_unit_price(total, quantity),
                    line_total=total if total > 0 else None,
                    status_name=status_name,
                    account_name=account_name,
                    created_at=created_at,
                )
            )
        return rows

    def _work_rows(
        self,
        db: Session,
        *,
        workspace_id: int,
        item_id: int,
        from_date: Optional[date],
        to_date: Optional[date],
    ) -> List[ItemOrderRowResponse]:
        order_date_col = cast(WorkOrder.created_at, Date)
        filters = [
            WorkOrder.workspace_id == workspace_id,
            WorkOrderItem.item_id == item_id,
        ]
        if from_date is not None and to_date is not None:
            filters.append(_in_date_range(order_date_col, from_date, to_date))

        results = (
            db.query(
                WorkOrder.id,
                WorkOrder.work_order_number,
                order_date_col.label('order_date'),
                WorkOrder.created_at,
                func.sum(WorkOrderItem.quantity).label('quantity'),
                WorkOrder.status,
            )
            .join(
                WorkOrderItem,
                WorkOrderItem.work_order_id == WorkOrder.id,
            )
            .filter(*filters)
            .group_by(
                WorkOrder.id,
                WorkOrder.work_order_number,
                order_date_col,
                WorkOrder.created_at,
                WorkOrder.status,
            )
            .all()
        )

        rows: List[ItemOrderRowResponse] = []
        for wo_id, wo_number, order_date, created_at, qty, status in results:
            rows.append(
                ItemOrderRowResponse(
                    order_type='work_order',
                    order_id=wo_id,
                    order_number=wo_number,
                    order_date=order_date,
                    quantity=_dec(qty),
                    status_name=status.value if status is not None else None,
                    created_at=created_at,
                )
            )
        return rows


item_orders_service = ItemOrdersService()
