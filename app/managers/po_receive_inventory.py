"""Post and reverse purchase-order receive inventory per receive event item."""
from decimal import Decimal
from typing import List, Sequence, Tuple

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.dao.inventory_ledger import inventory_ledger_dao
from app.managers.inventory_movements import item_name, post_stock_in, post_stock_out
from app.managers.po_storage_inventory import PO_INVENTORY_SOURCE_TYPE as PO_LEGACY_LINE_SOURCE
from app.models.inventory_ledger import InventoryLedger
from app.models.machine_item_ledger import MachineItemLedger
from app.models.po_receive_event import PoReceiveEvent, PoReceiveEventItem
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_order_item import PurchaseOrderItem

PO_RECEIVE_EVENT_ITEM_SOURCE = 'po_receive_event_item'
PO_RECEIVE_EVENT_ITEM_REVERSAL_SOURCE = 'po_receive_event_item_reversal'
PO_LEGACY_LINE_REVERSAL_SOURCE = 'purchase_order_reversal'


def _delta_to_int(delta: Decimal, *, line_number: int) -> int:
    if delta != delta.to_integral_value():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f'Line {line_number} has a fractional quantity delta; '
                'inventory requires whole units'
            ),
        )
    qty = int(abs(delta))
    if qty <= 0:
        return 0
    return qty


def _ledger_exists(
    session: Session,
    *,
    workspace_id: int,
    source_type: str,
    source_id: int,
    model,
) -> bool:
    return (
        session.query(model.id)
        .filter(
            model.workspace_id == workspace_id,
            model.source_type == source_type,
            model.source_id == source_id,
        )
        .first()
        is not None
    )


def _storage_ledger_exists(session: Session, *, workspace_id: int, source_type: str, source_id: int) -> bool:
    return inventory_ledger_dao.exists_for_source(
        session, workspace_id=workspace_id, source_type=source_type, source_id=source_id
    )


def _machine_ledger_exists(session: Session, *, workspace_id: int, source_type: str, source_id: int) -> bool:
    return _ledger_exists(
        session,
        workspace_id=workspace_id,
        source_type=source_type,
        source_id=source_id,
        model=MachineItemLedger,
    )


def _location_for_po(po: PurchaseOrder) -> tuple[str, int] | None:
    if po.destination_type == 'storage':
        return 'storage', po.destination_id
    if po.destination_type == 'machine':
        return 'machine', po.destination_id
    return None


def _post_event_item_delta(
    session: Session,
    *,
    po: PurchaseOrder,
    event_item: PoReceiveEventItem,
    po_line: PurchaseOrderItem,
    workspace_id: int,
    user_id: int,
) -> bool:
    """Apply one receive-event item delta to inventory. Returns True if a ledger row was created."""
    if _storage_ledger_exists(
        session,
        workspace_id=workspace_id,
        source_type=PO_RECEIVE_EVENT_ITEM_SOURCE,
        source_id=event_item.id,
    ) or _machine_ledger_exists(
        session,
        workspace_id=workspace_id,
        source_type=PO_RECEIVE_EVENT_ITEM_SOURCE,
        source_id=event_item.id,
    ):
        return False

    location = _location_for_po(po)
    if location is None:
        return False

    location_type, location_id = location
    delta = Decimal(str(event_item.quantity_delta))
    if delta == 0:
        return False

    qty = _delta_to_int(delta, line_number=po_line.line_number)
    if qty <= 0:
        return False

    unit_cost = Decimal(str(po_line.unit_price))
    notes = f'PO {po.po_number} line {po_line.line_number} (receive event #{event_item.id})'

    if delta > 0:
        post_stock_in(
            session,
            location_type=location_type,
            location_id=location_id,
            item_id=po_line.item_id,
            qty=qty,
            unit_cost=unit_cost,
            transaction_type='purchase_order',
            source_type=PO_RECEIVE_EVENT_ITEM_SOURCE,
            source_id=event_item.id,
            notes=notes,
            workspace_id=workspace_id,
            user_id=user_id,
            activity_event_type='purchase_received' if location_type == 'machine' else None,
            activity_description=(
                f'Purchase received: {qty} units of {item_name(session, po_line.item_id, workspace_id)} '
                f'from PO {po.po_number}'
                if location_type == 'machine'
                else None
            ),
        )
    else:
        post_stock_out(
            session,
            location_type=location_type,
            location_id=location_id,
            item_id=po_line.item_id,
            qty=qty,
            transaction_type='inventory_adjustment',
            source_type=PO_RECEIVE_EVENT_ITEM_SOURCE,
            source_id=event_item.id,
            notes=f'{notes} — quantity correction',
            workspace_id=workspace_id,
            user_id=user_id,
            activity_event_type='purchase_correction' if location_type == 'machine' else None,
            activity_description=(
                f'Receiving correction: {qty} units of {item_name(session, po_line.item_id, workspace_id)} '
                f'removed from PO {po.po_number}'
                if location_type == 'machine'
                else None
            ),
        )
    return True


def post_receive_event_inventory(
    session: Session,
    po: PurchaseOrder,
    event_items: Sequence[Tuple[PoReceiveEventItem, PurchaseOrderItem]],
    workspace_id: int,
    user_id: int,
) -> int:
    """Post inventory for receive event line deltas. Returns count of ledger rows created."""
    posted = 0
    for event_item, po_line in event_items:
        if _post_event_item_delta(
            session,
            po=po,
            event_item=event_item,
            po_line=po_line,
            workspace_id=workspace_id,
            user_id=user_id,
        ):
            posted += 1
    return posted


def _reverse_event_item_posting(
    session: Session,
    *,
    po: PurchaseOrder,
    event_item: PoReceiveEventItem,
    po_line: PurchaseOrderItem,
    workspace_id: int,
    user_id: int,
) -> bool:
    if _storage_ledger_exists(
        session,
        workspace_id=workspace_id,
        source_type=PO_RECEIVE_EVENT_ITEM_REVERSAL_SOURCE,
        source_id=event_item.id,
    ) or _machine_ledger_exists(
        session,
        workspace_id=workspace_id,
        source_type=PO_RECEIVE_EVENT_ITEM_REVERSAL_SOURCE,
        source_id=event_item.id,
    ):
        return False

    if not (
        _storage_ledger_exists(
            session,
            workspace_id=workspace_id,
            source_type=PO_RECEIVE_EVENT_ITEM_SOURCE,
            source_id=event_item.id,
        )
        or _machine_ledger_exists(
            session,
            workspace_id=workspace_id,
            source_type=PO_RECEIVE_EVENT_ITEM_SOURCE,
            source_id=event_item.id,
        )
    ):
        return False

    location = _location_for_po(po)
    if location is None:
        return False

    location_type, location_id = location
    delta = Decimal(str(event_item.quantity_delta))
    if delta == 0:
        return False

    qty = _delta_to_int(delta, line_number=po_line.line_number)
    if qty <= 0:
        return False

    unit_cost = Decimal(str(po_line.unit_price))
    notes = f'PO {po.po_number} voided — reverse receive event #{event_item.id} line {po_line.line_number}'

    if delta > 0:
        post_stock_out(
            session,
            location_type=location_type,
            location_id=location_id,
            item_id=po_line.item_id,
            qty=qty,
            transaction_type='inventory_adjustment',
            source_type=PO_RECEIVE_EVENT_ITEM_REVERSAL_SOURCE,
            source_id=event_item.id,
            notes=notes,
            workspace_id=workspace_id,
            user_id=user_id,
            activity_event_type='purchase_reversed' if location_type == 'machine' else None,
            activity_description=(
                f'PO {po.po_number} voided — {qty} units of '
                f'{item_name(session, po_line.item_id, workspace_id)} removed'
                if location_type == 'machine'
                else None
            ),
        )
    else:
        post_stock_in(
            session,
            location_type=location_type,
            location_id=location_id,
            item_id=po_line.item_id,
            qty=qty,
            unit_cost=unit_cost,
            transaction_type='inventory_adjustment',
            source_type=PO_RECEIVE_EVENT_ITEM_REVERSAL_SOURCE,
            source_id=event_item.id,
            notes=notes,
            workspace_id=workspace_id,
            user_id=user_id,
            activity_event_type='purchase_reversed' if location_type == 'machine' else None,
            activity_description=(
                f'PO {po.po_number} voided — {qty} units of '
                f'{item_name(session, po_line.item_id, workspace_id)} restored'
                if location_type == 'machine'
                else None
            ),
        )
    return True


def _reverse_legacy_line_posting(
    session: Session,
    *,
    po: PurchaseOrder,
    po_line: PurchaseOrderItem,
    workspace_id: int,
    user_id: int,
) -> bool:
    """Reverse inventory posted at mark-complete under the legacy line.id source key."""
    if _storage_ledger_exists(
        session,
        workspace_id=workspace_id,
        source_type=PO_LEGACY_LINE_REVERSAL_SOURCE,
        source_id=po_line.id,
    ) or _machine_ledger_exists(
        session,
        workspace_id=workspace_id,
        source_type=PO_LEGACY_LINE_REVERSAL_SOURCE,
        source_id=po_line.id,
    ):
        return False

    storage_entry = (
        session.query(InventoryLedger)
        .filter(
            InventoryLedger.workspace_id == workspace_id,
            InventoryLedger.source_type == PO_LEGACY_LINE_SOURCE,
            InventoryLedger.source_id == po_line.id,
        )
        .first()
    )
    machine_entry = (
        session.query(MachineItemLedger)
        .filter(
            MachineItemLedger.workspace_id == workspace_id,
            MachineItemLedger.source_type == PO_LEGACY_LINE_SOURCE,
            MachineItemLedger.source_id == po_line.id,
        )
        .first()
    )
    if storage_entry is None and machine_entry is None:
        return False

    location = _location_for_po(po)
    if location is None:
        return False

    location_type, location_id = location
    if storage_entry is not None:
        qty = int(storage_entry.quantity)
        unit_cost = Decimal(str(storage_entry.unit_cost))
    else:
        qty = int(machine_entry.quantity)
        unit_cost = Decimal(str(machine_entry.unit_cost))

    notes = f'PO {po.po_number} voided — reverse legacy posting for line {po_line.line_number}'

    post_stock_out(
        session,
        location_type=location_type,
        location_id=location_id,
        item_id=po_line.item_id,
        qty=qty,
        transaction_type='inventory_adjustment',
        source_type=PO_LEGACY_LINE_REVERSAL_SOURCE,
        source_id=po_line.id,
        notes=notes,
        workspace_id=workspace_id,
        user_id=user_id,
        activity_event_type='purchase_reversed' if location_type == 'machine' else None,
        activity_description=(
            f'PO {po.po_number} voided — {qty} units of '
            f'{item_name(session, po_line.item_id, workspace_id)} removed'
            if location_type == 'machine'
            else None
        ),
    )
    return True


def reverse_po_receive_inventory(
    session: Session,
    po: PurchaseOrder,
    po_lines: List[PurchaseOrderItem],
    workspace_id: int,
    user_id: int,
) -> int:
    """Reverse all receive-event and legacy line inventory postings for a PO."""
    line_map = {line.id: line for line in po_lines}
    reversed_count = 0

    event_items = (
        session.query(PoReceiveEventItem)
        .join(PoReceiveEvent, PoReceiveEventItem.receive_event_id == PoReceiveEvent.id)
        .filter(
            PoReceiveEvent.purchase_order_id == po.id,
            PoReceiveEvent.workspace_id == workspace_id,
        )
        .order_by(PoReceiveEvent.created_at.desc(), PoReceiveEventItem.id.desc())
        .all()
    )

    for event_item in event_items:
        po_line = line_map.get(event_item.po_item_id)
        if po_line is None:
            continue
        if _reverse_event_item_posting(
            session,
            po=po,
            event_item=event_item,
            po_line=po_line,
            workspace_id=workspace_id,
            user_id=user_id,
        ):
            reversed_count += 1

    for po_line in po_lines:
        if _reverse_legacy_line_posting(
            session,
            po=po,
            po_line=po_line,
            workspace_id=workspace_id,
            user_id=user_id,
        ):
            reversed_count += 1

    return reversed_count
