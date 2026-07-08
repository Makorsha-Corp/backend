"""Post completed transfer order lines into inventory / machine ledgers.

Thin transfer-order-specific wrapper around the generic stock movement helpers in
`app.managers.inventory_movements`.
"""
from decimal import Decimal
from typing import List

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.dao.inventory_ledger import inventory_ledger_dao
from app.managers.inventory_movements import item_name, post_stock_in, post_stock_out
from app.models.machine_item_ledger import MachineItemLedger
from app.models.transfer_order import TransferOrder
from app.models.transfer_order_item import TransferOrderItem

TO_INVENTORY_SOURCE_TYPE = 'transfer_order'


def _quantity_to_int(quantity: Decimal, *, line_number: int) -> int:
    if quantity != quantity.to_integral_value():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f'Line {line_number} has a fractional quantity; '
                'inventory transfers require whole units'
            ),
        )
    qty = int(quantity)
    if qty <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'Line {line_number} has no quantity to transfer',
        )
    return qty


def _line_already_posted(session: Session, workspace_id: int, line_id: int) -> bool:
    if inventory_ledger_dao.exists_for_source(
        session,
        workspace_id=workspace_id,
        source_type=TO_INVENTORY_SOURCE_TYPE,
        source_id=line_id,
    ):
        return True
    return (
        session.query(MachineItemLedger.id)
        .filter(
            MachineItemLedger.workspace_id == workspace_id,
            MachineItemLedger.source_type == TO_INVENTORY_SOURCE_TYPE,
            MachineItemLedger.source_id == line_id,
        )
        .first()
        is not None
    )


def _post_location_out(
    session: Session,
    *,
    location_type: str,
    location_id: int,
    item_id: int,
    qty: int,
    line: TransferOrderItem,
    to: TransferOrder,
    workspace_id: int,
    user_id: int,
    dest_type: str,
    dest_id: int,
) -> Decimal:
    if location_type not in ('storage', 'damaged', 'machine'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'Unsupported source location type: {location_type}',
        )
    label = item_name(session, item_id, workspace_id)
    return post_stock_out(
        session,
        location_type=location_type,
        location_id=location_id,
        item_id=item_id,
        qty=qty,
        transaction_type='transfer_out',
        source_type=TO_INVENTORY_SOURCE_TYPE,
        source_id=line.id,
        notes=f'{to.transfer_number} line {line.line_number} transfer out',
        workspace_id=workspace_id,
        user_id=user_id,
        dest_type=dest_type,
        dest_id=dest_id,
        activity_event_type='transfer_out',
        activity_description=f'Transfer out: {qty} units of {label} ({to.transfer_number})',
    )


def _post_location_in(
    session: Session,
    *,
    location_type: str,
    location_id: int,
    item_id: int,
    qty: int,
    unit_cost: Decimal,
    line: TransferOrderItem,
    to: TransferOrder,
    workspace_id: int,
    user_id: int,
    source_type: str,
    source_id: int,
) -> None:
    if location_type == 'project':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Project destination inventory posting is not yet supported',
        )
    if location_type not in ('storage', 'damaged', 'machine'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'Unsupported destination location type: {location_type}',
        )
    label = item_name(session, item_id, workspace_id)
    post_stock_in(
        session,
        location_type=location_type,
        location_id=location_id,
        item_id=item_id,
        qty=qty,
        unit_cost=unit_cost,
        transaction_type='transfer_in',
        source_type=TO_INVENTORY_SOURCE_TYPE,
        source_id=line.id,
        notes=f'{to.transfer_number} line {line.line_number} transfer in',
        workspace_id=workspace_id,
        user_id=user_id,
        source_loc_type=source_type,
        source_loc_id=source_id,
        activity_event_type='transfer_in',
        activity_description=f'Transfer in: {qty} units of {label} ({to.transfer_number})',
    )


def post_transfer_order_inventory(
    session: Session,
    to: TransferOrder,
    items: List[TransferOrderItem],
    workspace_id: int,
    user_id: int,
) -> int:
    """Move inventory for all transfer lines. Returns number of lines posted."""
    lines_posted = 0
    for line in items:
        if _line_already_posted(session, workspace_id, line.id):
            continue

        qty = _quantity_to_int(Decimal(str(line.quantity)), line_number=line.line_number)
        unit_cost = _post_location_out(
            session,
            location_type=to.source_location_type,
            location_id=to.source_location_id,
            item_id=line.item_id,
            qty=qty,
            line=line,
            to=to,
            workspace_id=workspace_id,
            user_id=user_id,
            dest_type=to.destination_location_type,
            dest_id=to.destination_location_id,
        )
        _post_location_in(
            session,
            location_type=to.destination_location_type,
            location_id=to.destination_location_id,
            item_id=line.item_id,
            qty=qty,
            unit_cost=unit_cost,
            line=line,
            to=to,
            workspace_id=workspace_id,
            user_id=user_id,
            source_type=to.source_location_type,
            source_id=to.source_location_id,
        )
        lines_posted += 1

    return lines_posted
