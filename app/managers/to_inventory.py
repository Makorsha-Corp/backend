"""Post completed transfer order lines into inventory / machine ledgers."""
from decimal import Decimal
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.dao.factory import factory_dao
from app.dao.inventory import inventory_dao
from app.dao.inventory_ledger import inventory_ledger_dao
from app.dao.machine import machine_dao
from app.dao.machine_item import machine_item_dao
from app.dao.machine_item_ledger import machine_item_ledger_dao
from app.models.enums import InventoryTypeEnum
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


def _weighted_avg_price(
    old_qty: int,
    old_avg: Optional[Decimal],
    add_qty: int,
    unit_cost: Decimal,
) -> Decimal:
    if add_qty <= 0:
        return old_avg or Decimal('0')
    if old_qty > 0 and old_avg is not None:
        numer = Decimal(old_qty) * old_avg + Decimal(add_qty) * unit_cost
        return (numer / Decimal(old_qty + add_qty)).quantize(Decimal('0.01'))
    return unit_cost


def _inventory_type_for_location(location_type: str) -> InventoryTypeEnum:
    if location_type == 'damaged':
        return InventoryTypeEnum.DAMAGED
    return InventoryTypeEnum.STORAGE


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


def _post_storage_out(
    session: Session,
    *,
    factory_id: int,
    item_id: int,
    inventory_type: InventoryTypeEnum,
    qty: int,
    line: TransferOrderItem,
    to: TransferOrder,
    workspace_id: int,
    user_id: int,
    dest_type: str,
    dest_id: int,
) -> Decimal:
    factory = factory_dao.get_by_id_and_workspace(session, id=factory_id, workspace_id=workspace_id)
    if not factory:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f'Factory with ID {factory_id} not found')

    inv = inventory_dao.ensure_for_factory_item_type(
        session,
        factory_id=factory_id,
        item_id=item_id,
        inventory_type=inventory_type,
        workspace_id=workspace_id,
        created_by=user_id,
    )
    if inv.qty < qty:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f'Line {line.line_number}: insufficient stock '
                f'({inv.qty} available, {qty} requested)'
            ),
        )

    unit_cost = inv.avg_price or Decimal('0')
    old_qty = inv.qty
    old_avg = inv.avg_price
    new_qty = old_qty - qty

    inventory_ledger_dao.create(
        session,
        obj_in={
            'workspace_id': workspace_id,
            'inventory_type': inventory_type,
            'factory_id': factory_id,
            'item_id': item_id,
            'transaction_type': 'transfer_out',
            'quantity': qty,
            'unit_cost': unit_cost,
            'total_cost': (unit_cost * Decimal(qty)).quantize(Decimal('0.01')),
            'qty_before': old_qty,
            'qty_after': new_qty,
            'avg_price_before': old_avg,
            'avg_price_after': old_avg,
            'source_type': TO_INVENTORY_SOURCE_TYPE,
            'source_id': line.id,
            'transfer_destination_type': dest_type,
            'transfer_destination_id': dest_id,
            'notes': f'{to.transfer_number} line {line.line_number} transfer out',
            'performed_by': user_id,
        },
    )
    inv.qty = new_qty
    inv.updated_by = user_id
    session.flush()
    return unit_cost


def _post_storage_in(
    session: Session,
    *,
    factory_id: int,
    item_id: int,
    inventory_type: InventoryTypeEnum,
    qty: int,
    unit_cost: Decimal,
    line: TransferOrderItem,
    to: TransferOrder,
    workspace_id: int,
    user_id: int,
    source_type: str,
    source_id: int,
) -> None:
    factory = factory_dao.get_by_id_and_workspace(session, id=factory_id, workspace_id=workspace_id)
    if not factory:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f'Factory with ID {factory_id} not found')

    inv = inventory_dao.ensure_for_factory_item_type(
        session,
        factory_id=factory_id,
        item_id=item_id,
        inventory_type=inventory_type,
        workspace_id=workspace_id,
        created_by=user_id,
    )
    old_qty = inv.qty
    old_avg = inv.avg_price
    new_qty = old_qty + qty
    new_avg = _weighted_avg_price(old_qty, old_avg, qty, unit_cost)

    inventory_ledger_dao.create(
        session,
        obj_in={
            'workspace_id': workspace_id,
            'inventory_type': inventory_type,
            'factory_id': factory_id,
            'item_id': item_id,
            'transaction_type': 'transfer_in',
            'quantity': qty,
            'unit_cost': unit_cost,
            'total_cost': (unit_cost * Decimal(qty)).quantize(Decimal('0.01')),
            'qty_before': old_qty,
            'qty_after': new_qty,
            'avg_price_before': old_avg,
            'avg_price_after': new_avg,
            'source_type': TO_INVENTORY_SOURCE_TYPE,
            'source_id': line.id,
            'transfer_source_type': source_type,
            'transfer_source_id': source_id,
            'notes': f'{to.transfer_number} line {line.line_number} transfer in',
            'performed_by': user_id,
        },
    )
    inv.qty = new_qty
    inv.avg_price = new_avg
    inv.updated_by = user_id
    session.flush()


def _ensure_machine_item(
    session: Session,
    *,
    machine_id: int,
    item_id: int,
    workspace_id: int,
) -> object:
    mi = machine_item_dao.get_by_machine_and_item(
        session, machine_id=machine_id, item_id=item_id, workspace_id=workspace_id
    )
    if mi:
        return mi
    return machine_item_dao.create(
        session,
        obj_in={
            'workspace_id': workspace_id,
            'machine_id': machine_id,
            'item_id': item_id,
            'qty': 0,
        },
    )


def _get_machine_unit_cost(session: Session, *, machine_id: int, item_id: int, workspace_id: int) -> Decimal:
    latest = machine_item_ledger_dao.get_latest_entry(
        session, machine_id=machine_id, item_id=item_id, workspace_id=workspace_id
    )
    if latest and latest.avg_price_after is not None:
        return Decimal(str(latest.avg_price_after))
    return Decimal('0')


def _post_machine_out(
    session: Session,
    *,
    machine_id: int,
    item_id: int,
    qty: int,
    line: TransferOrderItem,
    to: TransferOrder,
    workspace_id: int,
    user_id: int,
    dest_type: str,
    dest_id: int,
) -> Decimal:
    machine = machine_dao.get_by_id_and_workspace(session, id=machine_id, workspace_id=workspace_id)
    if not machine:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f'Machine with ID {machine_id} not found')

    mi = _ensure_machine_item(session, machine_id=machine_id, item_id=item_id, workspace_id=workspace_id)
    if mi.qty < qty:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f'Line {line.line_number}: insufficient machine stock '
                f'({mi.qty} available, {qty} requested)'
            ),
        )

    unit_cost = _get_machine_unit_cost(session, machine_id=machine_id, item_id=item_id, workspace_id=workspace_id)
    qty_before = mi.qty
    qty_after = qty_before - qty
    value_before = Decimal(qty_before) * unit_cost
    value_after = Decimal(qty_after) * unit_cost

    machine_item_ledger_dao.create(
        session,
        obj_in={
            'workspace_id': workspace_id,
            'machine_id': machine_id,
            'item_id': item_id,
            'transaction_type': 'transfer_out',
            'quantity': qty,
            'unit_cost': unit_cost,
            'total_cost': (unit_cost * Decimal(qty)).quantize(Decimal('0.01')),
            'qty_before': qty_before,
            'qty_after': qty_after,
            'value_before': value_before,
            'value_after': value_after,
            'avg_price_before': unit_cost,
            'avg_price_after': unit_cost,
            'source_type': TO_INVENTORY_SOURCE_TYPE,
            'source_id': line.id,
            'transfer_destination_type': dest_type,
            'transfer_destination_id': dest_id,
            'notes': f'{to.transfer_number} line {line.line_number} transfer out',
            'performed_by': user_id,
        },
    )
    mi.qty = qty_after
    session.flush()
    return unit_cost


def _post_machine_in(
    session: Session,
    *,
    machine_id: int,
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
    machine = machine_dao.get_by_id_and_workspace(session, id=machine_id, workspace_id=workspace_id)
    if not machine:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f'Machine with ID {machine_id} not found')

    mi = _ensure_machine_item(session, machine_id=machine_id, item_id=item_id, workspace_id=workspace_id)
    qty_before = mi.qty
    qty_after = qty_before + qty
    avg_before = _get_machine_unit_cost(session, machine_id=machine_id, item_id=item_id, workspace_id=workspace_id)
    avg_after = _weighted_avg_price(qty_before, avg_before if qty_before > 0 else None, qty, unit_cost)
    value_before = Decimal(qty_before) * avg_before
    value_after = Decimal(qty_after) * avg_after

    machine_item_ledger_dao.create(
        session,
        obj_in={
            'workspace_id': workspace_id,
            'machine_id': machine_id,
            'item_id': item_id,
            'transaction_type': 'transfer_in',
            'quantity': qty,
            'unit_cost': unit_cost,
            'total_cost': (unit_cost * Decimal(qty)).quantize(Decimal('0.01')),
            'qty_before': qty_before,
            'qty_after': qty_after,
            'value_before': value_before,
            'value_after': value_after,
            'avg_price_before': avg_before,
            'avg_price_after': avg_after,
            'source_type': TO_INVENTORY_SOURCE_TYPE,
            'source_id': line.id,
            'transfer_source_type': source_type,
            'transfer_source_id': source_id,
            'notes': f'{to.transfer_number} line {line.line_number} transfer in',
            'performed_by': user_id,
        },
    )
    mi.qty = qty_after
    session.flush()


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
    if location_type in ('storage', 'damaged'):
        return _post_storage_out(
            session,
            factory_id=location_id,
            item_id=item_id,
            inventory_type=_inventory_type_for_location(location_type),
            qty=qty,
            line=line,
            to=to,
            workspace_id=workspace_id,
            user_id=user_id,
            dest_type=dest_type,
            dest_id=dest_id,
        )
    if location_type == 'machine':
        return _post_machine_out(
            session,
            machine_id=location_id,
            item_id=item_id,
            qty=qty,
            line=line,
            to=to,
            workspace_id=workspace_id,
            user_id=user_id,
            dest_type=dest_type,
            dest_id=dest_id,
        )
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f'Unsupported source location type: {location_type}',
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
    if location_type in ('storage', 'damaged'):
        _post_storage_in(
            session,
            factory_id=location_id,
            item_id=item_id,
            inventory_type=_inventory_type_for_location(location_type),
            qty=qty,
            unit_cost=unit_cost,
            line=line,
            to=to,
            workspace_id=workspace_id,
            user_id=user_id,
            source_type=source_type,
            source_id=source_id,
        )
        return
    if location_type == 'machine':
        _post_machine_in(
            session,
            machine_id=location_id,
            item_id=item_id,
            qty=qty,
            unit_cost=unit_cost,
            line=line,
            to=to,
            workspace_id=workspace_id,
            user_id=user_id,
            source_type=source_type,
            source_id=source_id,
        )
        return
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f'Unsupported destination location type: {location_type}',
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
