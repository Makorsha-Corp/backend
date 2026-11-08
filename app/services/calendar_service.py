"""Calendar service — aggregates dated records across the workspace."""
from __future__ import annotations

from datetime import date, datetime
from typing import Callable, Iterable, List, Optional, Sequence, Set, Tuple
from urllib.parse import urlencode

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from app.models.account_invoice import AccountInvoice
from app.models.expense_order import ExpenseOrder
from app.models.invoice_payment import InvoicePayment
from app.models.production_batch import ProductionBatch
from app.models.project import Project
from app.models.purchase_order import PurchaseOrder
from app.models.sales_delivery import SalesDelivery
from app.models.sales_order import SalesOrder
from app.models.work_order import WorkOrder
from app.schemas.calendar import CalendarCategory, CalendarEventResponse
from app.services.base_service import BaseService

DateFieldSpec = Tuple[str, str]  # (column_attr, human label)
DateChipSpec = Tuple[str, str, date]  # (event field key, label, calendar day)


def work_order_date_chip_specs(
    planned_date: Optional[date],
    end_date: Optional[date],
) -> List[DateChipSpec]:
    """One chip per distinct calendar day; same-day planned+end → planned only."""
    specs: List[DateChipSpec] = []
    if planned_date is not None:
        specs.append(("planned_date", "Planned date", planned_date))
    if end_date is not None and end_date != planned_date:
        specs.append(("end_date", "End date", end_date))
    elif planned_date is None and end_date is not None:
        specs.append(("end_date", "End date", end_date))
    return specs


def build_work_order_calendar_link(
    work_order_id: int,
    *,
    factory_id: Optional[int] = None,
    machine_id: Optional[int] = None,
) -> str:
    params: dict[str, str] = {"tab": "workOrders", "orderId": str(work_order_id)}
    if machine_id is not None:
        params["woMachine"] = str(machine_id)
    if factory_id is not None:
        params["factoryId"] = str(factory_id)
    return f"/machines?{urlencode(params)}"


def build_production_batch_calendar_link(batch_id: int) -> str:
    return f"/production?batchId={batch_id}"


def production_batch_date_chip_specs(
    batch_date: date,
    planned_start_at: Optional[datetime],
    actual_start_time: Optional[datetime],
) -> List[DateChipSpec]:
    specs: List[DateChipSpec] = []
    if planned_start_at is not None:
        primary_day = planned_start_at.date()
        specs.append(("planned_start", "Planned start", primary_day))
    else:
        specs.append(("batch_date", "Batch date", batch_date))
    actual_day = actual_start_time.date() if actual_start_time else None
    primary_day = specs[0][2]
    if actual_day is not None and actual_day != primary_day:
        specs.append(("actual_start", "Actual start", actual_day))
    return specs


def _event_id(source_type: str, record_id: int, date_field: str) -> str:
    return f"{source_type}:{record_id}:{date_field}"


def _date_in_range(value: Optional[date], start: date, end: date) -> bool:
    return value is not None and start <= value <= end


def _dt_to_date(value: Optional[datetime]) -> Optional[date]:
    if value is None:
        return None
    return value.date()


class CalendarService(BaseService):
    """Read-only aggregation of workspace calendar events."""

    def get_events(
        self,
        db: Session,
        *,
        workspace_id: int,
        start: date,
        end: date,
        types: Optional[Sequence[CalendarCategory]] = None,
    ) -> List[CalendarEventResponse]:
        if start > end:
            raise ValueError("start must be on or before end")

        allowed: Optional[Set[CalendarCategory]] = set(types) if types else None
        events: List[CalendarEventResponse] = []

        collectors: List[Callable[[], List[CalendarEventResponse]]] = [
            lambda: self._collect_work_orders(db, workspace_id, start, end, allowed),
            lambda: self._collect_purchase_orders(db, workspace_id, start, end, allowed),
            lambda: self._collect_expense_orders(db, workspace_id, start, end, allowed),
            lambda: self._collect_sales_orders(db, workspace_id, start, end, allowed),
            lambda: self._collect_sales_deliveries(db, workspace_id, start, end, allowed),
            lambda: self._collect_invoices(db, workspace_id, start, end, allowed),
            lambda: self._collect_invoice_payments(db, workspace_id, start, end, allowed),
            lambda: self._collect_production_batches(db, workspace_id, start, end, allowed),
            lambda: self._collect_projects(db, workspace_id, start, end, allowed),
        ]

        for collect in collectors:
            events.extend(collect())

        events.sort(key=lambda e: (e.date, e.category.value, e.title))
        return events

    def _category_allowed(
        self, category: CalendarCategory, allowed: Optional[Set[CalendarCategory]]
    ) -> bool:
        return allowed is None or category in allowed

    def _expand_date_fields(
        self,
        *,
        record,
        source_type: str,
        category: CalendarCategory,
        date_fields: Iterable[DateFieldSpec],
        title: str,
        subtitle: Optional[str],
        link: str,
        start: date,
        end: date,
        meta: Optional[dict] = None,
    ) -> List[CalendarEventResponse]:
        out: List[CalendarEventResponse] = []
        base_meta = meta or {}
        for field_name, label in date_fields:
            value = getattr(record, field_name, None)
            if isinstance(value, datetime):
                value = value.date()
            if not _date_in_range(value, start, end):
                continue
            out.append(
                CalendarEventResponse(
                    id=_event_id(source_type, record.id, field_name),
                    category=category,
                    source_type=source_type,
                    record_id=record.id,
                    date=value,
                    date_label=label,
                    title=title,
                    subtitle=subtitle,
                    link=link,
                    meta=base_meta,
                )
            )
        return out

    def _collect_work_orders(
        self,
        db: Session,
        workspace_id: int,
        start: date,
        end: date,
        allowed: Optional[Set[CalendarCategory]],
    ) -> List[CalendarEventResponse]:
        if not self._category_allowed(CalendarCategory.WORK_ORDERS, allowed):
            return []

        rows = (
            db.query(WorkOrder)
            .filter(
                WorkOrder.workspace_id == workspace_id,
                WorkOrder.is_deleted.is_(False),
                or_(
                    and_(WorkOrder.planned_date.isnot(None), WorkOrder.planned_date >= start, WorkOrder.planned_date <= end),
                    and_(WorkOrder.end_date.isnot(None), WorkOrder.end_date >= start, WorkOrder.end_date <= end),
                ),
            )
            .all()
        )

        events: List[CalendarEventResponse] = []
        for row in rows:
            meta = {
                "status": row.status,
                "priority": row.priority.value if row.priority else None,
                "factory_id": row.factory_id,
                "machine_id": row.machine_id,
                "planned_start_at": row.planned_start_at.isoformat() if row.planned_start_at else None,
                "planned_end_at": row.planned_end_at.isoformat() if row.planned_end_at else None,
            }
            link = build_work_order_calendar_link(
                row.id,
                factory_id=row.factory_id,
                machine_id=row.machine_id,
            )
            for field_key, label, day in work_order_date_chip_specs(row.planned_date, row.end_date):
                if not _date_in_range(day, start, end):
                    continue
                events.append(
                    CalendarEventResponse(
                        id=_event_id("work_order", row.id, field_key),
                        category=CalendarCategory.WORK_ORDERS,
                        source_type="work_order",
                        record_id=row.id,
                        date=day,
                        date_label=label,
                        title=row.work_order_number,
                        subtitle=row.title,
                        link=link,
                        meta=meta,
                    )
                )
        return events

    def _collect_purchase_orders(
        self,
        db: Session,
        workspace_id: int,
        start: date,
        end: date,
        allowed: Optional[Set[CalendarCategory]],
    ) -> List[CalendarEventResponse]:
        if not self._category_allowed(CalendarCategory.PURCHASE, allowed):
            return []

        rows = (
            db.query(PurchaseOrder)
            .filter(
                PurchaseOrder.workspace_id == workspace_id,
                PurchaseOrder.voided.is_(False),
                or_(
                    and_(PurchaseOrder.order_date.isnot(None), PurchaseOrder.order_date >= start, PurchaseOrder.order_date <= end),
                    and_(PurchaseOrder.expected_delivery_date.isnot(None), PurchaseOrder.expected_delivery_date >= start, PurchaseOrder.expected_delivery_date <= end),
                    and_(PurchaseOrder.actual_delivery_date.isnot(None), PurchaseOrder.actual_delivery_date >= start, PurchaseOrder.actual_delivery_date <= end),
                ),
            )
            .all()
        )

        events: List[CalendarEventResponse] = []
        for row in rows:
            events.extend(
                self._expand_date_fields(
                    record=row,
                    source_type="purchase_order",
                    category=CalendarCategory.PURCHASE,
                    date_fields=[
                        ("order_date", "Order date"),
                        ("expected_delivery_date", "Expected delivery"),
                        ("actual_delivery_date", "Actual delivery"),
                    ],
                    title=row.po_number,
                    subtitle=row.description,
                    link=f"/orders/purchase?orderId={row.id}",
                    start=start,
                    end=end,
                    meta={
                        "total_amount": str(row.total_amount) if row.total_amount is not None else None,
                        "account_id": row.account_id,
                        "current_status_id": row.current_status_id,
                    },
                )
            )
        return events

    def _collect_expense_orders(
        self,
        db: Session,
        workspace_id: int,
        start: date,
        end: date,
        allowed: Optional[Set[CalendarCategory]],
    ) -> List[CalendarEventResponse]:
        if not self._category_allowed(CalendarCategory.EXPENSE, allowed):
            return []

        rows = (
            db.query(ExpenseOrder)
            .filter(
                ExpenseOrder.workspace_id == workspace_id,
                ExpenseOrder.voided.is_(False),
                or_(
                    and_(ExpenseOrder.expense_date >= start, ExpenseOrder.expense_date <= end),
                    and_(ExpenseOrder.due_date.isnot(None), ExpenseOrder.due_date >= start, ExpenseOrder.due_date <= end),
                ),
            )
            .all()
        )

        events: List[CalendarEventResponse] = []
        for row in rows:
            events.extend(
                self._expand_date_fields(
                    record=row,
                    source_type="expense_order",
                    category=CalendarCategory.EXPENSE,
                    date_fields=[
                        ("expense_date", "Expense date"),
                        ("due_date", "Due date"),
                    ],
                    title=row.expense_number,
                    subtitle=row.description,
                    link="/orders/expense",
                    start=start,
                    end=end,
                    meta={
                        "category": row.expense_category,
                        "total_amount": str(row.total_amount) if row.total_amount is not None else None,
                    },
                )
            )
        return events

    def _collect_sales_orders(
        self,
        db: Session,
        workspace_id: int,
        start: date,
        end: date,
        allowed: Optional[Set[CalendarCategory]],
    ) -> List[CalendarEventResponse]:
        if not self._category_allowed(CalendarCategory.SALES, allowed):
            return []

        rows = (
            db.query(SalesOrder)
            .filter(
                SalesOrder.workspace_id == workspace_id,
                or_(
                    and_(SalesOrder.order_date >= start, SalesOrder.order_date <= end),
                    and_(SalesOrder.expected_delivery_date.isnot(None), SalesOrder.expected_delivery_date >= start, SalesOrder.expected_delivery_date <= end),
                ),
            )
            .all()
        )

        events: List[CalendarEventResponse] = []
        for row in rows:
            events.extend(
                self._expand_date_fields(
                    record=row,
                    source_type="sales_order",
                    category=CalendarCategory.SALES,
                    date_fields=[
                        ("order_date", "Order date"),
                        ("expected_delivery_date", "Expected delivery"),
                    ],
                    title=row.sales_order_number,
                    subtitle=row.description,
                    link="/sales/overview",
                    start=start,
                    end=end,
                    meta={"total_amount": str(row.total_amount) if row.total_amount is not None else None},
                )
            )
        return events

    def _collect_sales_deliveries(
        self,
        db: Session,
        workspace_id: int,
        start: date,
        end: date,
        allowed: Optional[Set[CalendarCategory]],
    ) -> List[CalendarEventResponse]:
        if not self._category_allowed(CalendarCategory.SALES, allowed):
            return []

        rows = (
            db.query(SalesDelivery)
            .filter(
                SalesDelivery.workspace_id == workspace_id,
                SalesDelivery.delivery_status != "cancelled",
                or_(
                    and_(SalesDelivery.scheduled_date.isnot(None), SalesDelivery.scheduled_date >= start, SalesDelivery.scheduled_date <= end),
                    and_(SalesDelivery.actual_delivery_date.isnot(None), SalesDelivery.actual_delivery_date >= start, SalesDelivery.actual_delivery_date <= end),
                ),
            )
            .all()
        )

        events: List[CalendarEventResponse] = []
        for row in rows:
            events.extend(
                self._expand_date_fields(
                    record=row,
                    source_type="sales_delivery",
                    category=CalendarCategory.SALES,
                    date_fields=[
                        ("scheduled_date", "Scheduled delivery"),
                        ("actual_delivery_date", "Actual delivery"),
                    ],
                    title=row.delivery_number,
                    subtitle=f"Sales order #{row.sales_order_id}",
                    link="/sales/pipeline",
                    start=start,
                    end=end,
                    meta={"delivery_status": row.delivery_status},
                )
            )
        return events

    def _collect_invoices(
        self,
        db: Session,
        workspace_id: int,
        start: date,
        end: date,
        allowed: Optional[Set[CalendarCategory]],
    ) -> List[CalendarEventResponse]:
        if not self._category_allowed(CalendarCategory.INVOICES, allowed):
            return []

        rows = (
            db.query(AccountInvoice)
            .filter(
                AccountInvoice.workspace_id == workspace_id,
                AccountInvoice.invoice_status != "voided",
                or_(
                    and_(AccountInvoice.invoice_date >= start, AccountInvoice.invoice_date <= end),
                    and_(AccountInvoice.due_date.isnot(None), AccountInvoice.due_date >= start, AccountInvoice.due_date <= end),
                ),
            )
            .all()
        )

        events: List[CalendarEventResponse] = []
        for row in rows:
            events.extend(
                self._expand_date_fields(
                    record=row,
                    source_type="account_invoice",
                    category=CalendarCategory.INVOICES,
                    date_fields=[
                        ("invoice_date", "Invoice date"),
                        ("due_date", "Due date"),
                    ],
                    title=row.invoice_number or f"Invoice #{row.id}",
                    subtitle=row.description,
                    link=f"/accounts/{row.account_id}?invoiceId={row.id}",
                    start=start,
                    end=end,
                    meta={
                        "account_id": row.account_id,
                        "invoice_type": row.invoice_type,
                        "payment_status": row.payment_status,
                        "invoice_amount": str(row.invoice_amount) if row.invoice_amount is not None else None,
                    },
                )
            )
        return events

    def _collect_invoice_payments(
        self,
        db: Session,
        workspace_id: int,
        start: date,
        end: date,
        allowed: Optional[Set[CalendarCategory]],
    ) -> List[CalendarEventResponse]:
        if not self._category_allowed(CalendarCategory.INVOICES, allowed):
            return []

        rows = (
            db.query(InvoicePayment, AccountInvoice)
            .join(AccountInvoice, InvoicePayment.invoice_id == AccountInvoice.id)
            .filter(
                InvoicePayment.workspace_id == workspace_id,
                InvoicePayment.is_voided.is_(False),
                InvoicePayment.payment_date >= start,
                InvoicePayment.payment_date <= end,
            )
            .all()
        )

        return [
            CalendarEventResponse(
                id=_event_id("invoice_payment", payment.id, "payment_date"),
                category=CalendarCategory.INVOICES,
                source_type="invoice_payment",
                record_id=payment.id,
                date=payment.payment_date,
                date_label="Payment date",
                title=f"Payment #{payment.id}",
                subtitle=f"Invoice #{payment.invoice_id}",
                link=f"/accounts/{invoice.account_id}?invoiceId={invoice.id}",
                meta={
                    "invoice_id": payment.invoice_id,
                    "account_id": invoice.account_id,
                    "payment_amount": str(payment.payment_amount) if payment.payment_amount is not None else None,
                    "payment_method": payment.payment_method,
                },
            )
            for payment, invoice in rows
        ]

    def _collect_production_batches(
        self,
        db: Session,
        workspace_id: int,
        start: date,
        end: date,
        allowed: Optional[Set[CalendarCategory]],
    ) -> List[CalendarEventResponse]:
        if not self._category_allowed(CalendarCategory.PRODUCTION, allowed):
            return []

        rows = (
            db.query(ProductionBatch)
            .filter(
                ProductionBatch.workspace_id == workspace_id,
                ProductionBatch.status != "cancelled",
                or_(
                    and_(ProductionBatch.batch_date >= start, ProductionBatch.batch_date <= end),
                    and_(
                        ProductionBatch.planned_start_at.isnot(None),
                        func.date(ProductionBatch.planned_start_at) >= start,
                        func.date(ProductionBatch.planned_start_at) <= end,
                    ),
                    and_(
                        ProductionBatch.actual_start_time.isnot(None),
                        func.date(ProductionBatch.actual_start_time) >= start,
                        func.date(ProductionBatch.actual_start_time) <= end,
                    ),
                ),
            )
            .all()
        )

        events: List[CalendarEventResponse] = []
        for row in rows:
            link = build_production_batch_calendar_link(row.id)
            meta = {
                "status": row.status,
                "planned_start_at": row.planned_start_at.isoformat() if row.planned_start_at else None,
                "actual_start_time": row.actual_start_time.isoformat() if row.actual_start_time else None,
            }
            for field_key, label, day in production_batch_date_chip_specs(
                row.batch_date,
                row.planned_start_at,
                row.actual_start_time,
            ):
                if not _date_in_range(day, start, end):
                    continue
                events.append(
                    CalendarEventResponse(
                        id=_event_id("production_batch", row.id, field_key),
                        category=CalendarCategory.PRODUCTION,
                        source_type="production_batch",
                        record_id=row.id,
                        date=day,
                        date_label=label,
                        title=row.batch_number,
                        subtitle=row.notes,
                        link=link,
                        meta=meta,
                    )
                )
        return events

    def _collect_projects(
        self,
        db: Session,
        workspace_id: int,
        start: date,
        end: date,
        allowed: Optional[Set[CalendarCategory]],
    ) -> List[CalendarEventResponse]:
        if not self._category_allowed(CalendarCategory.PROJECTS, allowed):
            return []

        start_dt = datetime.combine(start, datetime.min.time())
        end_dt = datetime.combine(end, datetime.max.time())

        rows = (
            db.query(Project)
            .filter(
                Project.workspace_id == workspace_id,
                or_(
                    and_(Project.start_date.isnot(None), Project.start_date >= start_dt, Project.start_date <= end_dt),
                    and_(Project.end_date.isnot(None), Project.end_date >= start_dt, Project.end_date <= end_dt),
                    and_(Project.deadline.isnot(None), Project.deadline >= start_dt, Project.deadline <= end_dt),
                ),
            )
            .all()
        )

        events: List[CalendarEventResponse] = []
        for row in rows:
            # Normalize DateTime fields to date for event output
            class _ProjectDates:
                id = row.id
                start_date = _dt_to_date(row.start_date)
                end_date = _dt_to_date(row.end_date)
                deadline = _dt_to_date(row.deadline)

            events.extend(
                self._expand_date_fields(
                    record=_ProjectDates(),
                    source_type="project",
                    category=CalendarCategory.PROJECTS,
                    date_fields=[
                        ("start_date", "Start date"),
                        ("end_date", "End date"),
                        ("deadline", "Deadline"),
                    ],
                    title=row.name,
                    subtitle=row.description[:120] if row.description else None,
                    link="/project",
                    start=start,
                    end=end,
                    meta={"status": row.status.value if row.status else None},
                )
            )
        return events


calendar_service = CalendarService()
