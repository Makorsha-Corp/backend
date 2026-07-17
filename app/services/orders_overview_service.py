"""Aggregate order overview stats for dashboards."""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import and_, func, or_, cast, Date, case
from sqlalchemy.orm import Session, Query, aliased

from app.models.account import Account
from app.models.expense_order import ExpenseOrder
from app.models.factory import Factory
from app.models.item import Item
from app.models.machine import Machine
from app.models.project import Project
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_order_item import PurchaseOrderItem
from app.models.sales_order import SalesOrder
from app.models.sales_order_item import SalesOrderItem
from app.models.transfer_order import TransferOrder
from app.models.transfer_order_item import TransferOrderItem
from app.models.work_order import WorkOrder
from app.schemas.orders_overview import (
    OrdersOverviewStatsResponse,
    TopAccountRow,
    TopExpenseCategoryRow,
    TopFactoryRow,
    TopItemRow,
)


def _dec(value) -> Decimal:
    if value is None:
        return Decimal('0')
    return Decimal(str(value))


class OrdersOverviewService:
    def _po_report_date(self):
        return func.coalesce(PurchaseOrder.order_date, cast(PurchaseOrder.created_at, Date))

    def _in_date_range(self, column, from_date: date, to_date: date):
        return and_(column >= from_date, column <= to_date)

    def _filter_po_by_factory(self, query: Query, factory_id: int) -> Query:
        dest_machine = aliased(Machine)
        dest_project = aliased(Project)
        return (
            query.outerjoin(
                dest_machine,
                and_(
                    PurchaseOrder.destination_type == 'machine',
                    PurchaseOrder.destination_id == dest_machine.id,
                ),
            )
            .outerjoin(
                dest_project,
                and_(
                    PurchaseOrder.destination_type == 'project',
                    PurchaseOrder.destination_id == dest_project.id,
                ),
            )
            .filter(
                or_(
                    and_(
                        PurchaseOrder.destination_type.in_(('storage', 'damaged')),
                        PurchaseOrder.destination_id == factory_id,
                    ),
                    dest_machine.factory_id == factory_id,
                    dest_project.factory_id == factory_id,
                )
            )
        )

    def _filter_transfer_by_factory(self, query: Query, factory_id: int) -> Query:
        dest_machine = aliased(Machine)
        dest_project = aliased(Project)
        src_machine = aliased(Machine)
        return (
            query.outerjoin(
                dest_machine,
                and_(
                    TransferOrder.destination_location_type == 'machine',
                    TransferOrder.destination_location_id == dest_machine.id,
                ),
            )
            .outerjoin(
                dest_project,
                and_(
                    TransferOrder.destination_location_type == 'project',
                    TransferOrder.destination_location_id == dest_project.id,
                ),
            )
            .outerjoin(
                src_machine,
                and_(
                    TransferOrder.source_location_type == 'machine',
                    TransferOrder.source_location_id == src_machine.id,
                ),
            )
            .filter(
                or_(
                    and_(
                        TransferOrder.destination_location_type.in_(('storage', 'damaged')),
                        TransferOrder.destination_location_id == factory_id,
                    ),
                    and_(
                        TransferOrder.source_location_type.in_(('storage', 'damaged')),
                        TransferOrder.source_location_id == factory_id,
                    ),
                    dest_machine.factory_id == factory_id,
                    dest_project.factory_id == factory_id,
                    src_machine.factory_id == factory_id,
                )
            )
        )

    @staticmethod
    def _factory_from_location(
        location_type,
        location_id,
        machine_section_factory_id,
        project_factory_id,
    ):
        """Resolve storage/damaged/machine/project legs to a factory_id."""
        return case(
            (location_type.in_(('storage', 'damaged')), location_id),
            (location_type == 'machine', machine_section_factory_id),
            (location_type == 'project', project_factory_id),
            else_=None,
        )

    def _accumulate_factory(
        self,
        factory_map: dict[int, dict],
        factory_id: Optional[int],
        amount: Decimal,
        order_kind: str,
    ) -> None:
        if factory_id is None:
            return
        entry = factory_map[factory_id]
        entry['order_count'] += 1
        entry['total_value'] += amount
        if order_kind == 'purchase':
            entry['purchase_count'] += 1
        elif order_kind == 'transfer':
            entry['transfer_count'] += 1
        elif order_kind == 'sales':
            entry['sales_count'] += 1
        elif order_kind == 'work':
            entry['work_count'] += 1

    def _build_top_factories(
        self,
        db: Session,
        workspace_id: int,
        from_date: date,
        to_date: date,
        limit: int,
    ) -> list[TopFactoryRow]:
        factory_map: dict[int, dict] = defaultdict(
            lambda: {
                'order_count': 0,
                'total_value': Decimal('0'),
                'purchase_count': 0,
                'transfer_count': 0,
                'sales_count': 0,
                'work_count': 0,
            }
        )

        po_dest_machine = aliased(Machine)
        po_dest_project = aliased(Project)
        po_factory_id = self._factory_from_location(
            PurchaseOrder.destination_type,
            PurchaseOrder.destination_id,
            po_dest_machine.factory_id,
            po_dest_project.factory_id,
        )
        po_rows = (
            db.query(po_factory_id, PurchaseOrder.total_amount)
            .outerjoin(
                po_dest_machine,
                and_(
                    PurchaseOrder.destination_type == 'machine',
                    PurchaseOrder.destination_id == po_dest_machine.id,
                ),
            )
            .outerjoin(
                po_dest_project,
                and_(
                    PurchaseOrder.destination_type == 'project',
                    PurchaseOrder.destination_id == po_dest_project.id,
                ),
            )
            .filter(
                PurchaseOrder.workspace_id == workspace_id,
                self._in_date_range(self._po_report_date(), from_date, to_date),
            )
            .all()
        )
        for fid, amount in po_rows:
            self._accumulate_factory(factory_map, fid, _dec(amount), 'purchase')

        to_dest_machine = aliased(Machine)
        to_dest_project = aliased(Project)
        to_src_machine = aliased(Machine)
        dest_factory = self._factory_from_location(
            TransferOrder.destination_location_type,
            TransferOrder.destination_location_id,
            to_dest_machine.factory_id,
            to_dest_project.factory_id,
        )
        src_factory = self._factory_from_location(
            TransferOrder.source_location_type,
            TransferOrder.source_location_id,
            to_src_machine.factory_id,
            None,
        )
        transfer_factory_id = func.coalesce(dest_factory, src_factory)
        to_rows = (
            db.query(transfer_factory_id)
            .outerjoin(
                to_dest_machine,
                and_(
                    TransferOrder.destination_location_type == 'machine',
                    TransferOrder.destination_location_id == to_dest_machine.id,
                ),
            )
            .outerjoin(
                to_dest_project,
                and_(
                    TransferOrder.destination_location_type == 'project',
                    TransferOrder.destination_location_id == to_dest_project.id,
                ),
            )
            .outerjoin(
                to_src_machine,
                and_(
                    TransferOrder.source_location_type == 'machine',
                    TransferOrder.source_location_id == to_src_machine.id,
                ),
            )
            .filter(
                TransferOrder.workspace_id == workspace_id,
                self._in_date_range(cast(TransferOrder.created_at, Date), from_date, to_date),
            )
            .all()
        )
        for (fid,) in to_rows:
            self._accumulate_factory(factory_map, fid, Decimal('0'), 'transfer')

        so_rows = (
            db.query(SalesOrder.factory_id, SalesOrder.total_amount)
            .filter(
                SalesOrder.workspace_id == workspace_id,
                self._in_date_range(SalesOrder.order_date, from_date, to_date),
            )
            .all()
        )
        for fid, amount in so_rows:
            self._accumulate_factory(factory_map, fid, _dec(amount), 'sales')

        wo_rows = (
            db.query(WorkOrder.factory_id, WorkOrder.cost)
            .filter(
                WorkOrder.workspace_id == workspace_id,
                self._in_date_range(cast(WorkOrder.created_at, Date), from_date, to_date),
            )
            .all()
        )
        for fid, amount in wo_rows:
            self._accumulate_factory(factory_map, fid, _dec(amount), 'work')

        if not factory_map:
            return []

        factory_ids = list(factory_map.keys())
        names = {
            row.id: row.name
            for row in db.query(Factory.id, Factory.name).filter(Factory.id.in_(factory_ids)).all()
        }

        ranked = sorted(
            factory_map.items(),
            key=lambda x: (x[1]['order_count'], x[1]['total_value']),
            reverse=True,
        )[:limit]

        return [
            TopFactoryRow(
                factory_id=fid,
                factory_name=names.get(fid) or f'Factory #{fid}',
                order_count=data['order_count'],
                total_value=data['total_value'],
                purchase_count=data['purchase_count'],
                transfer_count=data['transfer_count'],
                sales_count=data['sales_count'],
                work_count=data['work_count'],
            )
            for fid, data in ranked
        ]

    def get_stats(
        self,
        db: Session,
        workspace_id: int,
        from_date: date,
        to_date: date,
        factory_id: Optional[int] = None,
        limit: int = 5,
    ) -> OrdersOverviewStatsResponse:
        limit = max(1, min(limit, 10))
        item_stats: dict[int, dict] = defaultdict(
            lambda: {
                'item_name': '',
                'item_unit': None,
                'total_quantity': Decimal('0'),
                'total_spend': Decimal('0'),
                'line_count': 0,
                'purchase_qty': Decimal('0'),
                'transfer_qty': Decimal('0'),
                'sales_qty': Decimal('0'),
            }
        )

        po_q = (
            db.query(
                PurchaseOrderItem.item_id,
                Item.name,
                Item.unit,
                PurchaseOrderItem.quantity_ordered,
                PurchaseOrderItem.line_subtotal,
            )
            .join(PurchaseOrder, PurchaseOrderItem.purchase_order_id == PurchaseOrder.id)
            .join(Item, PurchaseOrderItem.item_id == Item.id)
            .filter(
                PurchaseOrder.workspace_id == workspace_id,
                self._in_date_range(self._po_report_date(), from_date, to_date),
            )
        )
        if factory_id is not None:
            po_q = self._filter_po_by_factory(po_q, factory_id)
        for row in po_q.all():
            item_id, name, unit, qty, spend = row
            entry = item_stats[item_id]
            entry['item_name'] = name or entry['item_name']
            entry['item_unit'] = unit or entry['item_unit']
            q = _dec(qty)
            s = _dec(spend)
            entry['total_quantity'] += q
            entry['total_spend'] += s
            entry['line_count'] += 1
            entry['purchase_qty'] += q

        to_q = (
            db.query(
                TransferOrderItem.item_id,
                Item.name,
                Item.unit,
                TransferOrderItem.quantity,
            )
            .join(TransferOrder, TransferOrderItem.transfer_order_id == TransferOrder.id)
            .join(Item, TransferOrderItem.item_id == Item.id)
            .filter(
                TransferOrder.workspace_id == workspace_id,
                self._in_date_range(cast(TransferOrder.created_at, Date), from_date, to_date),
            )
        )
        if factory_id is not None:
            to_q = self._filter_transfer_by_factory(to_q, factory_id)
        for row in to_q.all():
            item_id, name, unit, qty = row
            entry = item_stats[item_id]
            entry['item_name'] = name or entry['item_name']
            entry['item_unit'] = unit or entry['item_unit']
            q = _dec(qty)
            entry['total_quantity'] += q
            entry['line_count'] += 1
            entry['transfer_qty'] += q

        so_q = (
            db.query(
                SalesOrderItem.item_id,
                Item.name,
                Item.unit,
                SalesOrderItem.quantity_ordered,
                SalesOrderItem.line_total,
            )
            .join(SalesOrder, SalesOrderItem.sales_order_id == SalesOrder.id)
            .join(Item, SalesOrderItem.item_id == Item.id)
            .filter(
                SalesOrder.workspace_id == workspace_id,
                self._in_date_range(SalesOrder.order_date, from_date, to_date),
            )
        )
        if factory_id is not None:
            so_q = so_q.filter(SalesOrder.factory_id == factory_id)
        for row in so_q.all():
            item_id, name, unit, qty, spend = row
            entry = item_stats[item_id]
            entry['item_name'] = name or entry['item_name']
            entry['item_unit'] = unit or entry['item_unit']
            q = _dec(qty)
            s = _dec(spend)
            entry['total_quantity'] += q
            entry['total_spend'] += s
            entry['line_count'] += 1
            entry['sales_qty'] += q

        top_items = sorted(
            item_stats.items(),
            key=lambda x: (x[1]['total_quantity'], x[1]['total_spend']),
            reverse=True,
        )[:limit]
        top_items_rows = [
            TopItemRow(
                item_id=item_id,
                item_name=data['item_name'] or f'Item #{item_id}',
                item_unit=data['item_unit'],
                total_quantity=data['total_quantity'],
                total_spend=data['total_spend'],
                line_count=data['line_count'],
                purchase_qty=data['purchase_qty'],
                transfer_qty=data['transfer_qty'],
                sales_qty=data['sales_qty'],
            )
            for item_id, data in top_items
        ]

        vendor_map: dict[int, dict] = defaultdict(lambda: {'name': '', 'spend': Decimal('0'), 'count': 0})

        po_vendor_q = (
            db.query(
                PurchaseOrder.account_id,
                Account.name,
                func.sum(PurchaseOrder.total_amount),
                func.count(PurchaseOrder.id),
            )
            .outerjoin(Account, PurchaseOrder.account_id == Account.id)
            .filter(
                PurchaseOrder.workspace_id == workspace_id,
                PurchaseOrder.account_id.isnot(None),
                self._in_date_range(self._po_report_date(), from_date, to_date),
            )
            .group_by(PurchaseOrder.account_id, Account.name)
        )
        if factory_id is not None:
            po_vendor_q = self._filter_po_by_factory(po_vendor_q, factory_id)
        for account_id, name, spend, count in po_vendor_q.all():
            vendor_map[account_id]['name'] = name or vendor_map[account_id]['name']
            vendor_map[account_id]['spend'] += _dec(spend)
            vendor_map[account_id]['count'] += int(count or 0)

        if factory_id is None:
            eo_vendor_q = (
                db.query(
                    ExpenseOrder.account_id,
                    Account.name,
                    func.sum(ExpenseOrder.total_amount),
                    func.count(ExpenseOrder.id),
                )
                .outerjoin(Account, ExpenseOrder.account_id == Account.id)
                .filter(
                    ExpenseOrder.workspace_id == workspace_id,
                    ExpenseOrder.account_id.isnot(None),
                    self._in_date_range(ExpenseOrder.expense_date, from_date, to_date),
                )
                .group_by(ExpenseOrder.account_id, Account.name)
            )
            for account_id, name, spend, count in eo_vendor_q.all():
                vendor_map[account_id]['name'] = name or vendor_map[account_id]['name']
                vendor_map[account_id]['spend'] += _dec(spend)
                vendor_map[account_id]['count'] += int(count or 0)

        top_vendors = sorted(vendor_map.items(), key=lambda x: x[1]['spend'], reverse=True)[:limit]
        top_vendor_rows = [
            TopAccountRow(
                account_id=aid,
                account_name=data['name'] or f'Account #{aid}',
                total_spend=data['spend'],
                order_count=data['count'],
            )
            for aid, data in top_vendors
        ]

        customer_q = (
            db.query(
                SalesOrder.account_id,
                Account.name,
                func.sum(SalesOrder.total_amount),
                func.count(SalesOrder.id),
            )
            .join(Account, SalesOrder.account_id == Account.id)
            .filter(
                SalesOrder.workspace_id == workspace_id,
                self._in_date_range(SalesOrder.order_date, from_date, to_date),
            )
            .group_by(SalesOrder.account_id, Account.name)
            .order_by(func.sum(SalesOrder.total_amount).desc())
            .limit(limit)
        )
        if factory_id is not None:
            customer_q = customer_q.filter(SalesOrder.factory_id == factory_id)
        top_customer_rows = [
            TopAccountRow(
                account_id=row[0],
                account_name=row[1] or f'Account #{row[0]}',
                total_spend=_dec(row[2]),
                order_count=int(row[3] or 0),
            )
            for row in customer_q.all()
        ]

        top_category_rows: list[TopExpenseCategoryRow] = []
        if factory_id is None:
            category_q = (
                db.query(
                    ExpenseOrder.expense_category,
                    func.sum(ExpenseOrder.total_amount),
                    func.count(ExpenseOrder.id),
                )
                .filter(
                    ExpenseOrder.workspace_id == workspace_id,
                    self._in_date_range(ExpenseOrder.expense_date, from_date, to_date),
                )
                .group_by(ExpenseOrder.expense_category)
                .order_by(func.sum(ExpenseOrder.total_amount).desc())
                .limit(limit)
            )
            top_category_rows = [
                TopExpenseCategoryRow(
                    category=row[0],
                    total_spend=_dec(row[1]),
                    order_count=int(row[2] or 0),
                )
                for row in category_q.all()
            ]

        top_factory_rows: list[TopFactoryRow] = []
        if factory_id is None:
            top_factory_rows = self._build_top_factories(
                db, workspace_id, from_date, to_date, limit
            )

        return OrdersOverviewStatsResponse(
            top_items=top_items_rows,
            top_vendors=top_vendor_rows,
            top_customers=top_customer_rows,
            top_expense_categories=top_category_rows,
            top_factories=top_factory_rows,
        )


orders_overview_service = OrdersOverviewService()
