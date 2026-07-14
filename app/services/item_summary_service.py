"""Aggregate item catalog detail for the item hub dialog."""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from sqlalchemy import cast, Date, func
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.dao.inventory import inventory_dao
from app.dao.inventory_ledger import inventory_ledger_dao
from app.dao.machine_item import machine_item_dao
from app.dao.machine_item_ledger import machine_item_ledger_dao
from app.dao.product import product_dao
from app.dao.product_ledger import product_ledger_dao
from app.managers.item_manager import item_manager
from app.models.account import Account
from app.models.enums import InventoryTypeEnum
from app.models.factory import Factory
from app.models.factory_section import FactorySection
from app.models.machine import Machine
from app.models.machine_section_assignment import MachineSectionAssignment
from app.models.production_batch import ProductionBatch
from app.models.production_batch_item import ProductionBatchItem
from app.models.production_formula import ProductionFormula
from app.models.production_formula_item import ProductionFormulaItem
from app.models.project import Project
from app.models.project_component import ProjectComponent
from app.models.project_component_item import ProjectComponentItem
from app.models.expense_order import ExpenseOrder
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_order_item import PurchaseOrderItem
from app.models.sales_order import SalesOrder
from app.models.sales_order_item import SalesOrderItem
from app.models.transfer_order import TransferOrder
from app.models.transfer_order_item import TransferOrderItem
from app.models.work_order import WorkOrder
from app.models.work_order_item import WorkOrderItem
from app.schemas.item_summary import (
    ItemSummaryInventoryRow,
    ItemSummaryItem,
    ItemSummaryKpis,
    ItemSummaryMachinePlacement,
    ItemSummaryOrderStats,
    ItemSummaryOrderStatsPeriod,
    ItemSummaryPeriodPricing,
    ItemSummaryPricing,
    ItemSummaryPricingPeriod,
    ItemSummaryProductRow,
    ItemSummaryRecentActivity,
    ItemSummaryResponse,
    ItemSummarySupplierHighlights,
    ItemSummarySupplierPeriod,
    ItemSummarySupplierRow,
    ItemSummarySupplierStats,
    ItemSummarySupplierStatsPeriod,
    ItemSummaryTag,
    ItemSummaryBatchUsage,
    ItemSummaryFormulaUsage,
    ItemSummaryProjectUsage,
    ItemSummaryUsageCounts,
    ItemSummaryUsageDetails,
    ItemSummaryWorkOrderUsage,
)

USAGE_PREVIEW_LIMIT = 5
from app.services.orders_overview_service import orders_overview_service


def _dec(value) -> Decimal:
    if value is None:
        return Decimal('0')
    return Decimal(str(value))


def _est_value(qty: int, avg_price) -> Optional[Decimal]:
    if avg_price is None or qty <= 0:
        return None
    return _dec(avg_price) * qty


class ItemSummaryService:
    def get_summary(
        self,
        db: Session,
        *,
        item_id: int,
        workspace_id: int,
    ) -> ItemSummaryResponse:
        item = item_manager.get_item(db, item_id, workspace_id)
        if not item:
            raise NotFoundError(f"Item with ID {item_id} not found")

        tags = item_manager.get_tags_for_item(db, item_id=item_id, workspace_id=workspace_id)
        item_payload = ItemSummaryItem(
            id=item.id,
            workspace_id=item.workspace_id,
            name=item.name,
            description=item.description,
            unit=item.unit,
            sku=item.sku,
            is_active=item.is_active,
            created_at=item.created_at,
            updated_at=item.updated_at,
            created_by=item.created_by,
            updated_by=item.updated_by,
            tags=[
                ItemSummaryTag(
                    id=tag.id,
                    name=tag.name,
                    tag_code=tag.tag_code,
                    color=tag.color,
                    icon=tag.icon,
                    is_system_tag=tag.is_system_tag,
                )
                for tag in tags
            ],
        )

        factory_names = self._factory_name_map(db, workspace_id)
        machine_names = self._machine_name_map(db, workspace_id)
        machine_locations = self._machine_location_map(db, workspace_id)

        inventory_rows, storage_total, factory_stock_ids = self._inventory_rows(
            db, item_id=item_id, workspace_id=workspace_id, factory_names=factory_names
        )
        product_rows, product_total = self._product_rows(
            db, item_id=item_id, workspace_id=workspace_id, factory_names=factory_names
        )
        machine_placements = self._machine_placements(
            db,
            item_id=item_id,
            workspace_id=workspace_id,
            machine_locations=machine_locations,
        )

        today = date.today()
        order_stats = ItemSummaryOrderStatsPeriod(
            days_30=self._order_stats_for_item(
                db, workspace_id=workspace_id, item_id=item_id,
                from_date=today - timedelta(days=30), to_date=today,
            ),
            days_90=self._order_stats_for_item(
                db, workspace_id=workspace_id, item_id=item_id,
                from_date=today - timedelta(days=90), to_date=today,
            ),
            all_time=self._order_stats_for_item(
                db, workspace_id=workspace_id, item_id=item_id,
                from_date=None, to_date=None,
            ),
        )

        pricing = self._pricing(db, workspace_id=workspace_id, item_id=item_id, today=today)
        supplier_stats = self._supplier_stats(
            db, workspace_id=workspace_id, item_id=item_id, today=today
        )
        usage_counts, usage_details = self._usage(db, workspace_id=workspace_id, item_id=item_id)
        recent_activity = self._recent_activity(
            db,
            workspace_id=workspace_id,
            item_id=item_id,
            factory_names=factory_names,
            machine_names=machine_names,
        )

        kpis = ItemSummaryKpis(
            storage_qty_total=storage_total,
            machine_placement_count=len(machine_placements),
            product_qty_total=product_total,
            factory_count_with_stock=len(factory_stock_ids),
        )

        return ItemSummaryResponse(
            item=item_payload,
            kpis=kpis,
            inventory_rows=inventory_rows,
            product_rows=product_rows,
            machine_placements=machine_placements,
            order_stats=order_stats,
            pricing=pricing,
            supplier_stats=supplier_stats,
            usage_counts=usage_counts,
            usage_details=usage_details,
            recent_activity=recent_activity,
        )

    def _factory_name_map(self, db: Session, workspace_id: int) -> Dict[int, str]:
        rows = db.query(Factory.id, Factory.name).filter(Factory.workspace_id == workspace_id).all()
        return {row.id: row.name for row in rows}

    def _machine_name_map(self, db: Session, workspace_id: int) -> Dict[int, str]:
        rows = db.query(Machine.id, Machine.name).filter(Machine.workspace_id == workspace_id).all()
        return {row.id: row.name for row in rows}

    def _machine_location_map(self, db: Session, workspace_id: int) -> Dict[int, dict]:
        rows = (
            db.query(
                Machine.id,
                Machine.name,
                FactorySection.id,
                FactorySection.name,
                Factory.id,
                Factory.name,
            )
            .join(Factory, Machine.factory_id == Factory.id)
            .outerjoin(MachineSectionAssignment, MachineSectionAssignment.machine_id == Machine.id)
            .outerjoin(FactorySection, MachineSectionAssignment.factory_section_id == FactorySection.id)
            .filter(
                Machine.workspace_id == workspace_id,
                Machine.is_deleted.is_(False),
            )
            .all()
        )
        return {
            machine_id: {
                'machine_name': machine_name,
                'factory_section_id': section_id,
                'factory_section_name': section_name,
                'factory_id': factory_id,
                'factory_name': factory_name,
            }
            for machine_id, machine_name, section_id, section_name, factory_id, factory_name in rows
        }

    def _inventory_rows(
        self,
        db: Session,
        *,
        item_id: int,
        workspace_id: int,
        factory_names: Dict[int, str],
    ) -> Tuple[List[ItemSummaryInventoryRow], int, set[int]]:
        records = inventory_dao.get_by_item(db, item_id=item_id, workspace_id=workspace_id)
        rows: List[ItemSummaryInventoryRow] = []
        storage_total = 0
        factory_ids: set[int] = set()

        for inv in records:
            if inv.is_deleted or inv.qty <= 0:
                continue
            inv_type = (
                inv.inventory_type.value
                if isinstance(inv.inventory_type, InventoryTypeEnum)
                else str(inv.inventory_type)
            )
            if inv_type == InventoryTypeEnum.STORAGE.value:
                storage_total += inv.qty
            if inv.qty > 0:
                factory_ids.add(inv.factory_id)
            rows.append(
                ItemSummaryInventoryRow(
                    factory_id=inv.factory_id,
                    factory_name=factory_names.get(inv.factory_id, f'Factory #{inv.factory_id}'),
                    inventory_type=inv_type,
                    qty=inv.qty,
                    avg_price=inv.avg_price,
                    est_value=_est_value(inv.qty, inv.avg_price),
                )
            )

        rows.sort(key=lambda r: (r.factory_name, r.inventory_type))
        return rows, storage_total, factory_ids

    def _product_rows(
        self,
        db: Session,
        *,
        item_id: int,
        workspace_id: int,
        factory_names: Dict[int, str],
    ) -> Tuple[List[ItemSummaryProductRow], int]:
        records = product_dao.get_by_item(db, item_id=item_id, workspace_id=workspace_id)
        rows: List[ItemSummaryProductRow] = []
        total_qty = 0

        for prod in records:
            if prod.is_deleted or prod.qty <= 0:
                continue
            total_qty += prod.qty
            margin = None
            if prod.selling_price is not None and prod.avg_cost is not None:
                margin = _dec(prod.selling_price) - _dec(prod.avg_cost)
            rows.append(
                ItemSummaryProductRow(
                    factory_id=prod.factory_id,
                    factory_name=factory_names.get(prod.factory_id, f'Factory #{prod.factory_id}'),
                    qty=prod.qty,
                    avg_cost=prod.avg_cost,
                    selling_price=prod.selling_price,
                    is_available_for_sale=bool(prod.is_available_for_sale),
                    margin_hint=margin,
                )
            )

        rows.sort(key=lambda r: r.factory_name)
        return rows, total_qty

    def _machine_placements(
        self,
        db: Session,
        *,
        item_id: int,
        workspace_id: int,
        machine_locations: Dict[int, dict],
    ) -> List[ItemSummaryMachinePlacement]:
        records = machine_item_dao.get_by_item(db, item_id=item_id, workspace_id=workspace_id)
        rows: List[ItemSummaryMachinePlacement] = []

        for mi in records:
            low = mi.req_qty is not None and mi.qty < mi.req_qty
            location = machine_locations.get(mi.machine_id, {})
            factory_id = location.get('factory_id')
            factory_section_id = location.get('factory_section_id')
            rows.append(
                ItemSummaryMachinePlacement(
                    machine_id=mi.machine_id,
                    machine_name=location.get('machine_name', f'Machine #{mi.machine_id}'),
                    factory_id=factory_id if factory_id is not None else 0,
                    factory_name=location.get('factory_name', '—'),
                    factory_section_id=factory_section_id,
                    factory_section_name=location.get('factory_section_name'),
                    qty=mi.qty,
                    req_qty=mi.req_qty,
                    defective_qty=mi.defective_qty,
                    is_low_stock=low,
                )
            )

        rows.sort(
            key=lambda r: (
                not r.is_low_stock,
                r.factory_name,
                r.factory_section_name or '',
                r.machine_name,
            )
        )
        return rows

    def _order_stats_for_item(
        self,
        db: Session,
        *,
        workspace_id: int,
        item_id: int,
        from_date: Optional[date],
        to_date: Optional[date],
    ) -> ItemSummaryOrderStats:
        svc = orders_overview_service
        stats = ItemSummaryOrderStats()

        po_date = svc._po_report_date()
        po_filters = [
            PurchaseOrder.workspace_id == workspace_id,
            PurchaseOrderItem.item_id == item_id,
        ]
        if from_date is not None and to_date is not None:
            po_filters.append(svc._in_date_range(po_date, from_date, to_date))
        po_rows = (
            db.query(PurchaseOrderItem.quantity_ordered, PurchaseOrderItem.line_subtotal)
            .join(PurchaseOrder, PurchaseOrderItem.purchase_order_id == PurchaseOrder.id)
            .filter(*po_filters)
            .all()
        )
        for qty, spend in po_rows:
            q = _dec(qty)
            s = _dec(spend)
            stats.purchase_qty += q
            stats.total_quantity += q
            stats.total_spend += s
            stats.line_count += 1

        to_filters = [
            TransferOrder.workspace_id == workspace_id,
            TransferOrderItem.item_id == item_id,
        ]
        if from_date is not None and to_date is not None:
            to_filters.append(svc._in_date_range(cast(TransferOrder.created_at, Date), from_date, to_date))
        to_rows = (
            db.query(TransferOrderItem.quantity)
            .join(TransferOrder, TransferOrderItem.transfer_order_id == TransferOrder.id)
            .filter(*to_filters)
            .all()
        )
        for (qty,) in to_rows:
            q = _dec(qty)
            stats.transfer_qty += q
            stats.total_quantity += q
            stats.line_count += 1

        so_filters = [
            SalesOrder.workspace_id == workspace_id,
            SalesOrderItem.item_id == item_id,
        ]
        if from_date is not None and to_date is not None:
            so_filters.append(svc._in_date_range(SalesOrder.order_date, from_date, to_date))
        so_rows = (
            db.query(SalesOrderItem.quantity_ordered, SalesOrderItem.line_total)
            .join(SalesOrder, SalesOrderItem.sales_order_id == SalesOrder.id)
            .filter(*so_filters)
            .all()
        )
        for qty, spend in so_rows:
            q = _dec(qty)
            s = _dec(spend)
            stats.sales_qty += q
            stats.total_quantity += q
            stats.total_spend += s
            stats.line_count += 1

        return stats

    def _pricing_snapshot_from_po_lines(
        self, lines: List[Tuple]
    ) -> ItemSummaryPeriodPricing:
        prices: List[Decimal] = []
        weighted_sum = Decimal('0')
        weight_total = Decimal('0')
        for qty, price in lines:
            if price is None:
                continue
            p = _dec(price)
            q = _dec(qty)
            prices.append(p)
            weighted_sum += p * q
            weight_total += q

        return ItemSummaryPeriodPricing(
            avg_unit_price_weighted=(weighted_sum / weight_total) if weight_total > 0 else None,
            min_unit_price=min(prices) if prices else None,
            max_unit_price=max(prices) if prices else None,
        )

    def _pricing(
        self,
        db: Session,
        *,
        workspace_id: int,
        item_id: int,
        today: date,
    ) -> ItemSummaryPricing:
        svc = orders_overview_service
        po_date = svc._po_report_date()

        last_row = (
            db.query(PurchaseOrderItem.unit_price)
            .join(PurchaseOrder, PurchaseOrderItem.purchase_order_id == PurchaseOrder.id)
            .filter(
                PurchaseOrder.workspace_id == workspace_id,
                PurchaseOrderItem.item_id == item_id,
            )
            .order_by(po_date.desc(), PurchaseOrderItem.id.desc())
            .first()
        )

        def lines_for_days(days: int):
            from_date = today - timedelta(days=days)
            return (
                db.query(PurchaseOrderItem.quantity_ordered, PurchaseOrderItem.unit_price)
                .join(PurchaseOrder, PurchaseOrderItem.purchase_order_id == PurchaseOrder.id)
                .filter(
                    PurchaseOrder.workspace_id == workspace_id,
                    PurchaseOrderItem.item_id == item_id,
                    svc._in_date_range(po_date, from_date, today),
                )
                .all()
            )

        def lines_all_time():
            return (
                db.query(PurchaseOrderItem.quantity_ordered, PurchaseOrderItem.unit_price)
                .join(PurchaseOrder, PurchaseOrderItem.purchase_order_id == PurchaseOrder.id)
                .filter(
                    PurchaseOrder.workspace_id == workspace_id,
                    PurchaseOrderItem.item_id == item_id,
                )
                .all()
            )

        open_rows = (
            db.query(
                PurchaseOrderItem.quantity_ordered,
                PurchaseOrderItem.quantity_received,
            )
            .join(PurchaseOrder, PurchaseOrderItem.purchase_order_id == PurchaseOrder.id)
            .filter(
                PurchaseOrder.workspace_id == workspace_id,
                PurchaseOrderItem.item_id == item_id,
                PurchaseOrderItem.quantity_ordered > PurchaseOrderItem.quantity_received,
            )
            .all()
        )
        open_count = len(open_rows)
        open_qty = sum(_dec(o) - _dec(r) for o, r in open_rows)

        return ItemSummaryPricing(
            last_unit_price=_dec(last_row[0]) if last_row and last_row[0] is not None else None,
            open_po_line_count=open_count,
            open_qty_outstanding=open_qty,
            period=ItemSummaryPricingPeriod(
                days_30=self._pricing_snapshot_from_po_lines(lines_for_days(30)),
                days_90=self._pricing_snapshot_from_po_lines(lines_for_days(90)),
                all_time=self._pricing_snapshot_from_po_lines(lines_all_time()),
            ),
        )

    def _supplier_stats(
        self,
        db: Session,
        *,
        workspace_id: int,
        item_id: int,
        today: date,
    ) -> ItemSummarySupplierStats:
        svc = orders_overview_service
        po_date = svc._po_report_date()

        rows = (
            db.query(
                PurchaseOrder.account_id,
                Account.name,
                PurchaseOrder.id,
                PurchaseOrderItem.quantity_ordered,
                PurchaseOrderItem.unit_price,
                PurchaseOrderItem.line_subtotal,
                po_date,
            )
            .join(PurchaseOrder, PurchaseOrderItem.purchase_order_id == PurchaseOrder.id)
            .outerjoin(Account, PurchaseOrder.account_id == Account.id)
            .filter(
                PurchaseOrder.workspace_id == workspace_id,
                PurchaseOrderItem.item_id == item_id,
                PurchaseOrder.account_id.isnot(None),
            )
            .all()
        )

        return ItemSummarySupplierStats(
            period=ItemSummarySupplierStatsPeriod(
                days_30=self._supplier_period_snapshot(rows, today=today, days=30),
                days_90=self._supplier_period_snapshot(rows, today=today, days=90),
                all_time=self._supplier_period_snapshot(rows, today=today, days=None),
            ),
        )

    def _supplier_period_snapshot(
        self, rows, *, today: date, days: Optional[int]
    ) -> ItemSummarySupplierPeriod:
        if days is None:
            filtered = list(rows)
        else:
            from_date = today - timedelta(days=days)
            filtered = [
                row for row in rows
                if row[6] is not None and from_date <= row[6] <= today
            ]
        suppliers = self._supplier_rows_from_po_lines(filtered)
        cheapest = self._pick_cheapest_supplier(suppliers)
        most_frequent = self._pick_most_frequent_supplier(suppliers)
        suppliers.sort(key=lambda r: r.total_spend, reverse=True)
        return ItemSummarySupplierPeriod(
            highlights=ItemSummarySupplierHighlights(
                cheapest=cheapest,
                most_frequent=most_frequent,
            ),
            suppliers=suppliers[:10],
        )

    def _supplier_rows_from_po_lines(self, rows) -> List[ItemSummarySupplierRow]:
        buckets: Dict[int, dict] = {}

        for account_id, name, po_id, qty_raw, unit_price, line_subtotal, po_date_val in rows:
            if account_id is None:
                continue

            bucket = buckets.setdefault(
                account_id,
                {
                    'account_name': name or f'Account #{account_id}',
                    'po_ids': set(),
                    'total_qty': Decimal('0'),
                    'total_spend': Decimal('0'),
                    'weighted_sum': Decimal('0'),
                    'last_date': None,
                    'last_price': None,
                },
            )
            if name:
                bucket['account_name'] = name

            qty = _dec(qty_raw)
            price = _dec(unit_price)
            spend = _dec(line_subtotal)

            bucket['po_ids'].add(po_id)
            bucket['total_qty'] += qty
            bucket['total_spend'] += spend
            bucket['weighted_sum'] += qty * price

            if po_date_val is not None and (
                bucket['last_date'] is None or po_date_val > bucket['last_date']
            ):
                bucket['last_date'] = po_date_val
                bucket['last_price'] = price

        result: List[ItemSummarySupplierRow] = []
        for account_id, data in buckets.items():
            total_qty = data['total_qty']
            avg = (
                data['weighted_sum'] / total_qty
                if total_qty > 0
                else None
            )
            result.append(
                ItemSummarySupplierRow(
                    account_id=account_id,
                    account_name=data['account_name'],
                    order_count=len(data['po_ids']),
                    total_qty=total_qty,
                    total_spend=data['total_spend'],
                    avg_unit_price_weighted=avg,
                    last_unit_price=data['last_price'],
                    last_order_date=data['last_date'],
                )
            )
        return result

    def _pick_cheapest_supplier(
        self, rows: List[ItemSummarySupplierRow]
    ) -> Optional[ItemSummarySupplierRow]:
        candidates = [
            r for r in rows
            if r.avg_unit_price_weighted is not None and r.total_qty > 0
        ]
        if not candidates:
            return None
        return min(
            candidates,
            key=lambda r: (r.avg_unit_price_weighted, -r.order_count),
        )

    def _pick_most_frequent_supplier(
        self, rows: List[ItemSummarySupplierRow]
    ) -> Optional[ItemSummarySupplierRow]:
        if not rows:
            return None
        return max(
            rows,
            key=lambda r: (
                r.order_count,
                -(r.avg_unit_price_weighted or Decimal('999999999')),
            ),
        )

    def _usage(
        self, db: Session, *, workspace_id: int, item_id: int
    ) -> Tuple[ItemSummaryUsageCounts, ItemSummaryUsageDetails]:
        formula_count = (
            db.query(func.count(ProductionFormulaItem.id))
            .filter(
                ProductionFormulaItem.workspace_id == workspace_id,
                ProductionFormulaItem.item_id == item_id,
            )
            .scalar()
            or 0
        )
        batch_line_count = (
            db.query(func.count(ProductionBatchItem.id))
            .filter(
                ProductionBatchItem.workspace_id == workspace_id,
                ProductionBatchItem.item_id == item_id,
            )
            .scalar()
            or 0
        )
        project_component_count = (
            db.query(func.count(ProjectComponentItem.id))
            .filter(
                ProjectComponentItem.workspace_id == workspace_id,
                ProjectComponentItem.item_id == item_id,
            )
            .scalar()
            or 0
        )
        work_order_line_count = (
            db.query(func.count(WorkOrderItem.id))
            .filter(
                WorkOrderItem.workspace_id == workspace_id,
                WorkOrderItem.item_id == item_id,
            )
            .scalar()
            or 0
        )

        formula_rows = (
            db.query(
                ProductionFormula.id,
                ProductionFormula.formula_code,
                ProductionFormula.name,
                ProductionFormulaItem.item_role,
            )
            .join(
                ProductionFormulaItem,
                ProductionFormulaItem.formula_id == ProductionFormula.id,
            )
            .filter(
                ProductionFormulaItem.workspace_id == workspace_id,
                ProductionFormulaItem.item_id == item_id,
            )
            .order_by(ProductionFormula.name, ProductionFormulaItem.item_role)
            .limit(USAGE_PREVIEW_LIMIT)
            .all()
        )

        batch_rows = (
            db.query(
                ProductionBatch.id,
                ProductionBatch.batch_number,
                ProductionBatchItem.item_role,
                ProductionBatch.status,
            )
            .join(
                ProductionBatchItem,
                ProductionBatchItem.batch_id == ProductionBatch.id,
            )
            .filter(
                ProductionBatchItem.workspace_id == workspace_id,
                ProductionBatchItem.item_id == item_id,
            )
            .order_by(ProductionBatch.batch_date.desc(), ProductionBatch.id.desc())
            .limit(USAGE_PREVIEW_LIMIT)
            .all()
        )

        project_rows = (
            db.query(
                Project.id.label('project_id'),
                Project.name.label('project_name'),
                ProjectComponent.id.label('component_id'),
                ProjectComponent.name.label('component_name'),
            )
            .select_from(ProjectComponentItem)
            .join(
                ProjectComponent,
                ProjectComponentItem.project_component_id == ProjectComponent.id,
            )
            .join(Project, ProjectComponent.project_id == Project.id)
            .filter(
                ProjectComponentItem.workspace_id == workspace_id,
                ProjectComponentItem.item_id == item_id,
            )
            .order_by(Project.name, ProjectComponent.name)
            .limit(USAGE_PREVIEW_LIMIT)
            .all()
        )

        work_order_rows = (
            db.query(
                WorkOrder.id,
                WorkOrder.work_order_number,
                WorkOrder.title,
            )
            .join(WorkOrderItem, WorkOrderItem.work_order_id == WorkOrder.id)
            .filter(
                WorkOrderItem.workspace_id == workspace_id,
                WorkOrderItem.item_id == item_id,
            )
            .order_by(WorkOrderItem.created_at.desc(), WorkOrderItem.id.desc())
            .limit(USAGE_PREVIEW_LIMIT)
            .all()
        )

        counts = ItemSummaryUsageCounts(
            formula_count=int(formula_count),
            batch_line_count=int(batch_line_count),
            project_component_count=int(project_component_count),
            work_order_line_count=int(work_order_line_count),
        )
        details = ItemSummaryUsageDetails(
            formulas=[
                ItemSummaryFormulaUsage(
                    formula_id=row.id,
                    formula_code=row.formula_code,
                    name=row.name,
                    item_role=row.item_role,
                )
                for row in formula_rows
            ],
            batches=[
                ItemSummaryBatchUsage(
                    batch_id=row.id,
                    batch_number=row.batch_number,
                    item_role=row.item_role,
                    status=row.status,
                )
                for row in batch_rows
            ],
            projects=[
                ItemSummaryProjectUsage(
                    project_id=row.project_id,
                    project_name=row.project_name,
                    component_id=row.component_id,
                    component_name=row.component_name,
                )
                for row in project_rows
            ],
            work_orders=[
                ItemSummaryWorkOrderUsage(
                    work_order_id=row.id,
                    work_order_number=row.work_order_number,
                    title=row.title,
                )
                for row in work_order_rows
            ],
        )
        return counts, details

    def _resolve_order_link(
        self,
        db: Session,
        *,
        order_type: Optional[str],
        order_id: Optional[int],
        source_type: Optional[str],
        source_id: Optional[int],
    ) -> Tuple[Optional[str], Optional[int]]:
        if order_type and order_id:
            return order_type, order_id

        if not source_type or not source_id:
            return None, None

        if source_type == 'purchase_order':
            row = (
                db.query(PurchaseOrderItem.purchase_order_id)
                .filter(PurchaseOrderItem.id == source_id)
                .first()
            )
            return ('purchase_order', row[0]) if row else (None, None)

        if source_type == 'transfer_order':
            row = (
                db.query(TransferOrderItem.transfer_order_id)
                .filter(TransferOrderItem.id == source_id)
                .first()
            )
            return ('transfer_order', row[0]) if row else (None, None)

        return None, None

    def _resolve_order_number(
        self,
        db: Session,
        *,
        order_type: Optional[str],
        order_id: Optional[int],
    ) -> Optional[str]:
        if not order_type or not order_id:
            return None

        if order_type == 'purchase_order':
            row = db.query(PurchaseOrder.po_number).filter(PurchaseOrder.id == order_id).first()
        elif order_type == 'transfer_order':
            row = db.query(TransferOrder.transfer_number).filter(TransferOrder.id == order_id).first()
        elif order_type == 'sales_order':
            row = db.query(SalesOrder.sales_order_number).filter(SalesOrder.id == order_id).first()
        elif order_type == 'expense_order':
            row = db.query(ExpenseOrder.expense_number).filter(ExpenseOrder.id == order_id).first()
        elif order_type == 'work_order':
            row = db.query(WorkOrder.work_order_number).filter(WorkOrder.id == order_id).first()
        else:
            return None

        return row[0] if row else None

    def _activity_from_ledger(
        self,
        db: Session,
        *,
        source: str,
        performed_at,
        transaction_type: str,
        quantity: int,
        factory_id: Optional[int] = None,
        factory_name: Optional[str] = None,
        machine_id: Optional[int] = None,
        machine_name: Optional[str] = None,
        inventory_type: Optional[str] = None,
        order_type: Optional[str] = None,
        order_id: Optional[int] = None,
        source_type: Optional[str] = None,
        source_id: Optional[int] = None,
    ) -> ItemSummaryRecentActivity:
        resolved_type, resolved_id = self._resolve_order_link(
            db,
            order_type=order_type,
            order_id=order_id,
            source_type=source_type,
            source_id=source_id,
        )
        resolved_number = self._resolve_order_number(
            db, order_type=resolved_type, order_id=resolved_id
        )
        return ItemSummaryRecentActivity(
            source=source,  # type: ignore[arg-type]
            performed_at=performed_at,
            transaction_type=transaction_type,
            quantity=quantity,
            factory_id=factory_id,
            factory_name=factory_name,
            machine_id=machine_id,
            machine_name=machine_name,
            inventory_type=inventory_type,
            order_type=resolved_type,
            order_id=resolved_id,
            order_number=resolved_number,
        )

    def _recent_activity(
        self,
        db: Session,
        *,
        workspace_id: int,
        item_id: int,
        factory_names: Dict[int, str],
        machine_names: Dict[int, str],
        limit: int = 10,
    ) -> List[ItemSummaryRecentActivity]:
        per_source = max(limit, 5)
        combined: List[ItemSummaryRecentActivity] = []

        for entry in inventory_ledger_dao.get_by_workspace(
            db, workspace_id=workspace_id, item_id=item_id, skip=0, limit=per_source
        ):
            inv_type = (
                entry.inventory_type.value
                if hasattr(entry.inventory_type, 'value')
                else str(entry.inventory_type)
            )
            combined.append(
                self._activity_from_ledger(
                    db,
                    source='inventory',
                    performed_at=entry.performed_at,
                    transaction_type=entry.transaction_type,
                    quantity=int(entry.quantity),
                    factory_id=entry.factory_id,
                    factory_name=factory_names.get(entry.factory_id) if entry.factory_id else None,
                    inventory_type=inv_type,
                    source_type=entry.source_type,
                    source_id=entry.source_id,
                )
            )

        for entry in product_ledger_dao.get_by_workspace(
            db, workspace_id=workspace_id, item_id=item_id, skip=0, limit=per_source
        ):
            combined.append(
                self._activity_from_ledger(
                    db,
                    source='product',
                    performed_at=entry.performed_at,
                    transaction_type=entry.transaction_type,
                    quantity=int(entry.quantity),
                    factory_id=entry.factory_id,
                    factory_name=factory_names.get(entry.factory_id) if entry.factory_id else None,
                    source_type=entry.source_type,
                    source_id=entry.source_id,
                )
            )

        for entry in machine_item_ledger_dao.get_by_item(
            db, item_id=item_id, workspace_id=workspace_id, skip=0, limit=per_source
        ):
            combined.append(
                self._activity_from_ledger(
                    db,
                    source='machine',
                    performed_at=entry.performed_at,
                    transaction_type=entry.transaction_type,
                    quantity=int(entry.quantity),
                    machine_id=entry.machine_id,
                    machine_name=machine_names.get(entry.machine_id),
                    order_type=entry.order_type,
                    order_id=entry.order_id,
                    source_type=entry.source_type,
                    source_id=entry.source_id,
                )
            )

        combined.sort(key=lambda r: r.performed_at, reverse=True)
        return combined[:limit]


item_summary_service = ItemSummaryService()
