"""Post purchase-order return inventory per return item (goods going back to the supplier)."""
from decimal import Decimal
from typing import Sequence, Tuple

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.dao.inventory_ledger import inventory_ledger_dao
from app.managers.inventory_movements import item_name, post_stock_out
from app.models.machine_item_ledger import MachineItemLedger
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_order_item import PurchaseOrderItem
from app.models.purchase_order_return import PurchaseOrderReturnItem

PO_RETURN_ITEM_SOURCE = 'purchase_return_item'


def _machine_ledger_exists(session: Session, *, workspace_id: int, source_type: str, source_id: int) -> bool:
    return (
        session.query(MachineItemLedger.id)
        .filter(
            MachineItemLedger.workspace_id == workspace_id,
            MachineItemLedger.source_type == source_type,
            MachineItemLedger.source_id == source_id,
        )
        .first()
        is not None
    )


def _storage_ledger_exists(session: Session, *, workspace_id: int, source_type: str, source_id: int) -> bool:
    return inventory_ledger_dao.exists_for_source(
        session, workspace_id=workspace_id, source_type=source_type, source_id=source_id
    )


def _location_for_po(po: PurchaseOrder) -> tuple[str, int] | None:
    if po.destination_type == 'storage':
        return 'storage', po.destination_id
    if po.destination_type == 'machine':
        return 'machine', po.destination_id
    return None


def _quantity_to_int(quantity: Decimal, *, po_item_id: int) -> int:
    if quantity != quantity.to_integral_value():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'Return line for PO item {po_item_id} has a fractional quantity; inventory requires whole units',
        )
    return int(quantity)


def post_purchase_return_inventory(
    session: Session,
    po: PurchaseOrder,
    return_item_pairs: Sequence[Tuple[PurchaseOrderReturnItem, PurchaseOrderItem]],
    workspace_id: int,
    user_id: int,
) -> int:
    """Post stock-out for each completed return line. Returns count of ledger rows created."""
    location = _location_for_po(po)
    if location is None:
        return 0
    location_type, location_id = location

    posted = 0
    for return_item, po_line in return_item_pairs:
        if _storage_ledger_exists(
            session, workspace_id=workspace_id, source_type=PO_RETURN_ITEM_SOURCE, source_id=return_item.id
        ) or _machine_ledger_exists(
            session, workspace_id=workspace_id, source_type=PO_RETURN_ITEM_SOURCE, source_id=return_item.id
        ):
            continue

        qty = _quantity_to_int(Decimal(str(return_item.quantity_returned)), po_item_id=po_line.id)
        if qty <= 0:
            continue

        post_stock_out(
            session,
            location_type=location_type,
            location_id=location_id,
            item_id=po_line.item_id,
            qty=qty,
            transaction_type='purchase_return',
            source_type=PO_RETURN_ITEM_SOURCE,
            source_id=return_item.id,
            notes=f'PO {po.po_number} return {return_item.return_id} (line {po_line.line_number})',
            workspace_id=workspace_id,
            user_id=user_id,
            activity_event_type='purchase_returned' if location_type == 'machine' else None,
            activity_description=(
                f'Purchase returned: {qty} units of {item_name(session, po_line.item_id, workspace_id)} to supplier'
                if location_type == 'machine'
                else None
            ),
        )
        posted += 1
    return posted
