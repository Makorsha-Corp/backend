"""Batch price history insights for items on a purchase order."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Sequence, Tuple

from sqlalchemy import Date, cast, func
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.account import Account
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_order_item import PurchaseOrderItem
from app.schemas.purchase_order_item_insights import (
    ItemPriceInsightLowest,
    ItemPriceInsightRef,
    ItemPriceInsightRow,
    PoItemPriceInsightsResponse,
)
from app.managers.purchase_order_manager import purchase_order_manager


def _dec(value) -> Decimal:
    if value is None:
        return Decimal('0')
    return Decimal(str(value))


@dataclass(frozen=True)
class _HistoryLine:
    item_id: int
    line_id: int
    purchase_order_id: int
    po_number: str
    account_id: int | None
    account_name: str | None
    unit_price: Decimal | None
    quantity_ordered: Decimal
    order_date: date | None


def _to_ref(line: _HistoryLine) -> ItemPriceInsightRef:
    return ItemPriceInsightRef(
        purchase_order_id=line.purchase_order_id,
        po_number=line.po_number,
        account_id=line.account_id,
        account_name=line.account_name,
        unit_price=line.unit_price,
        order_date=line.order_date,
    )


class PurchaseOrderItemInsightsService:
    def get_item_price_insights(
        self,
        db: Session,
        *,
        po_id: int,
        workspace_id: int,
    ) -> PoItemPriceInsightsResponse:
        po = purchase_order_manager.get_purchase_order(db, po_id=po_id, workspace_id=workspace_id)
        if not po:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f'Purchase order with ID {po_id} not found',
            )

        po_items = purchase_order_manager.item_dao.get_by_order(
            db, purchase_order_id=po.id, workspace_id=workspace_id
        )
        item_ids = sorted({row.item_id for row in po_items})
        if not item_ids:
            return PoItemPriceInsightsResponse(items=[])

        lines = self._fetch_history_lines(
            db,
            workspace_id=workspace_id,
            item_ids=item_ids,
            exclude_po_id=po_id,
        )

        by_item: Dict[int, List[_HistoryLine]] = {iid: [] for iid in item_ids}
        for line in lines:
            by_item.setdefault(line.item_id, []).append(line)

        today = date.today()
        rows: List[ItemPriceInsightRow] = []
        for item_id in item_ids:
            item_lines = by_item.get(item_id, [])
            rows.append(
                ItemPriceInsightRow(
                    item_id=item_id,
                    last_ordered=self._pick_last_ordered(item_lines),
                    lowest=ItemPriceInsightLowest(
                        avg_supplier=self._pick_avg_supplier_lowest(item_lines),
                        all_time=self._pick_min_price_ref(item_lines),
                        days_30=self._pick_min_price_ref(
                            item_lines,
                            from_date=today - timedelta(days=30),
                            to_date=today,
                        ),
                        days_90=self._pick_min_price_ref(
                            item_lines,
                            from_date=today - timedelta(days=90),
                            to_date=today,
                        ),
                    ),
                )
            )

        return PoItemPriceInsightsResponse(items=rows)

    def _fetch_history_lines(
        self,
        db: Session,
        *,
        workspace_id: int,
        item_ids: Sequence[int],
        exclude_po_id: int,
    ) -> List[_HistoryLine]:
        order_date_col = func.coalesce(
            PurchaseOrder.order_date,
            cast(PurchaseOrder.created_at, Date),
        )

        results = (
            db.query(
                PurchaseOrderItem.item_id,
                PurchaseOrderItem.id,
                PurchaseOrderItem.unit_price,
                PurchaseOrderItem.quantity_ordered,
                PurchaseOrder.id,
                PurchaseOrder.po_number,
                PurchaseOrder.account_id,
                Account.name,
                order_date_col,
            )
            .join(PurchaseOrder, PurchaseOrderItem.purchase_order_id == PurchaseOrder.id)
            .outerjoin(Account, PurchaseOrder.account_id == Account.id)
            .filter(
                PurchaseOrder.workspace_id == workspace_id,
                PurchaseOrderItem.item_id.in_(item_ids),
                PurchaseOrder.voided.is_(False),
                PurchaseOrder.id != exclude_po_id,
            )
            .all()
        )

        return [
            _HistoryLine(
                item_id=row[0],
                line_id=row[1],
                unit_price=_dec(row[2]) if row[2] is not None else None,
                quantity_ordered=_dec(row[3]),
                purchase_order_id=row[4],
                po_number=row[5],
                account_id=row[6],
                account_name=row[7],
                order_date=row[8],
            )
            for row in results
        ]

    def _pick_last_ordered(self, lines: List[_HistoryLine]) -> ItemPriceInsightRef | None:
        priced = [ln for ln in lines if ln.order_date is not None]
        if not priced:
            if not lines:
                return None
            line = max(lines, key=lambda ln: (ln.line_id,))
            return _to_ref(line)

        line = max(
            priced,
            key=lambda ln: (ln.order_date, ln.line_id),
        )
        return _to_ref(line)

    def _pick_min_price_ref(
        self,
        lines: List[_HistoryLine],
        *,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> ItemPriceInsightRef | None:
        candidates = [
            ln
            for ln in lines
            if ln.unit_price is not None and ln.unit_price > 0
        ]
        if from_date is not None and to_date is not None:
            candidates = [
                ln
                for ln in candidates
                if ln.order_date is not None and from_date <= ln.order_date <= to_date
            ]
        if not candidates:
            return None

        line = min(
            candidates,
            key=lambda ln: (
                ln.unit_price,
                ln.order_date or date.min,
                ln.purchase_order_id,
                ln.line_id,
            ),
        )
        return _to_ref(line)

    def _pick_avg_supplier_lowest(self, lines: List[_HistoryLine]) -> ItemPriceInsightRef | None:
        priced = [
            ln
            for ln in lines
            if ln.account_id is not None and ln.unit_price is not None and ln.unit_price > 0
        ]
        if not priced:
            return None

        buckets: Dict[int, dict] = {}
        for ln in priced:
            bucket = buckets.setdefault(
                ln.account_id,
                {
                    'account_name': ln.account_name or f'Account #{ln.account_id}',
                    'po_ids': set(),
                    'total_qty_weight': Decimal('0'),
                    'weighted_sum': Decimal('0'),
                    'lines': [],
                },
            )
            if ln.account_name:
                bucket['account_name'] = ln.account_name
            bucket['po_ids'].add(ln.purchase_order_id)
            qty = ln.quantity_ordered if ln.quantity_ordered > 0 else Decimal('1')
            bucket['total_qty_weight'] += qty
            bucket['weighted_sum'] += qty * ln.unit_price
            bucket['lines'].append(ln)

        best_account_id: int | None = None
        best_avg: Decimal | None = None
        best_order_count = -1

        for account_id, data in buckets.items():
            if data['total_qty_weight'] <= 0:
                continue
            avg = data['weighted_sum'] / data['total_qty_weight']
            order_count = len(data['po_ids'])
            if (
                best_avg is None
                or avg < best_avg
                or (avg == best_avg and order_count > best_order_count)
            ):
                best_avg = avg
                best_account_id = account_id
                best_order_count = order_count

        if best_account_id is None:
            return None

        supplier_lines = buckets[best_account_id]['lines']
        ref_line = min(
            supplier_lines,
            key=lambda ln: (
                ln.unit_price,
                -(ln.order_date.toordinal() if ln.order_date else 0),
                ln.purchase_order_id,
                ln.line_id,
            ),
        )
        return _to_ref(ref_line)


purchase_order_item_insights_service = PurchaseOrderItemInsightsService()
