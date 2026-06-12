"""Code-defined purchase order stage workflow (Draft → Planning → Receiving → Complete)."""
from decimal import Decimal
from typing import Literal, Protocol, Sequence

PO_STAGES = ('Draft', 'Planning', 'Receiving', 'Complete')
PoStage = Literal['Draft', 'Planning', 'Receiving', 'Complete']


class PoStageItem(Protocol):
    quantity_received: Decimal | float | int | str | None


class PoStageOrder(Protocol):
    supplier_confirmed: bool
    details_confirmed: bool
    items_confirmed: bool


def _quantity_received_decimal(item: PoStageItem) -> Decimal:
    return Decimal(str(item.quantity_received or 0))


def derive_po_stage(po: PoStageOrder, items: Sequence[PoStageItem]) -> PoStage:
    """Derive PO stage from section confirms and receiving progress."""
    if items and any(_quantity_received_decimal(i) > 0 for i in items):
        return 'Receiving'
    if po.supplier_confirmed or po.details_confirmed or po.items_confirmed:
        return 'Planning'
    return 'Draft'


def is_po_complete(stage: str | None) -> bool:
    return stage == 'Complete'
