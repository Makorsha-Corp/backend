"""Generic stock in/out posting shared by any feature that moves or consumes inventory
(factory storage or a machine's on-hand stock). Extracted from `to_inventory.py` so
consumers other than Transfer Orders (e.g. Work Order item consumption) can reuse the
same validated, cost-tracked ledger-writing mechanics without duplicating them.
"""
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.dao.factory import factory_dao
from app.dao.inventory import inventory_dao
from app.dao.inventory_ledger import inventory_ledger_dao
from app.dao.machine import machine_dao
from app.dao.machine_item import machine_item_dao
from app.dao.machine_item_ledger import machine_item_ledger_dao
from app.dao.item import item_dao
from app.managers.machine_activity_manager import machine_activity_manager
from app.models.enums import InventoryTypeEnum


def item_name(session: Session, item_id: int, workspace_id: int) -> str:
    item = item_dao.get_by_id_and_workspace(session, id=item_id, workspace_id=workspace_id)
    return item.name if item else f"Item #{item_id}"


def weighted_avg_price(
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


def inventory_type_for_location(location_type: str) -> InventoryTypeEnum:
    if location_type == 'damaged':
        return InventoryTypeEnum.DAMAGED
    return InventoryTypeEnum.STORAGE


def _storage_out(
    session: Session,
    *,
    factory_id: int,
    item_id: int,
    inventory_type: InventoryTypeEnum,
    qty: int,
    transaction_type: str,
    source_type: str,
    source_id: int,
    notes: str,
    workspace_id: int,
    user_id: int,
    dest_type: Optional[str],
    dest_id: Optional[int],
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
            detail=f'Insufficient stock ({inv.qty} available, {qty} requested)',
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
            'transaction_type': transaction_type,
            'quantity': qty,
            'unit_cost': unit_cost,
            'total_cost': (unit_cost * Decimal(qty)).quantize(Decimal('0.01')),
            'qty_before': old_qty,
            'qty_after': new_qty,
            'avg_price_before': old_avg,
            'avg_price_after': old_avg,
            'source_type': source_type,
            'source_id': source_id,
            'transfer_destination_type': dest_type,
            'transfer_destination_id': dest_id,
            'notes': notes,
            'performed_by': user_id,
        },
    )
    inv.qty = new_qty
    inv.updated_by = user_id
    session.flush()
    return unit_cost


def _storage_in(
    session: Session,
    *,
    factory_id: int,
    item_id: int,
    inventory_type: InventoryTypeEnum,
    qty: int,
    unit_cost: Decimal,
    transaction_type: str,
    source_type: str,
    source_id: int,
    notes: str,
    workspace_id: int,
    user_id: int,
    source_loc_type: Optional[str],
    source_loc_id: Optional[int],
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
    new_avg = weighted_avg_price(old_qty, old_avg, qty, unit_cost)

    inventory_ledger_dao.create(
        session,
        obj_in={
            'workspace_id': workspace_id,
            'inventory_type': inventory_type,
            'factory_id': factory_id,
            'item_id': item_id,
            'transaction_type': transaction_type,
            'quantity': qty,
            'unit_cost': unit_cost,
            'total_cost': (unit_cost * Decimal(qty)).quantize(Decimal('0.01')),
            'qty_before': old_qty,
            'qty_after': new_qty,
            'avg_price_before': old_avg,
            'avg_price_after': new_avg,
            'source_type': source_type,
            'source_id': source_id,
            'transfer_source_type': source_loc_type,
            'transfer_source_id': source_loc_id,
            'notes': notes,
            'performed_by': user_id,
        },
    )
    inv.qty = new_qty
    inv.avg_price = new_avg
    inv.updated_by = user_id
    session.flush()


def ensure_machine_item(session: Session, *, machine_id: int, item_id: int, workspace_id: int):
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


def get_machine_unit_cost(session: Session, *, machine_id: int, item_id: int, workspace_id: int) -> Decimal:
    latest = machine_item_ledger_dao.get_latest_entry(
        session, machine_id=machine_id, item_id=item_id, workspace_id=workspace_id
    )
    if latest and latest.avg_price_after is not None:
        return Decimal(str(latest.avg_price_after))
    return Decimal('0')


def _machine_out(
    session: Session,
    *,
    machine_id: int,
    item_id: int,
    qty: int,
    transaction_type: str,
    source_type: str,
    source_id: int,
    notes: str,
    workspace_id: int,
    user_id: int,
    dest_type: Optional[str],
    dest_id: Optional[int],
    activity_event_type: str,
    activity_description: Optional[str] = None,
) -> Decimal:
    machine = machine_dao.get_by_id_and_workspace(session, id=machine_id, workspace_id=workspace_id)
    if not machine:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f'Machine with ID {machine_id} not found')

    mi = ensure_machine_item(session, machine_id=machine_id, item_id=item_id, workspace_id=workspace_id)
    if mi.qty < qty:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'Insufficient machine stock ({mi.qty} available, {qty} requested)',
        )

    unit_cost = get_machine_unit_cost(session, machine_id=machine_id, item_id=item_id, workspace_id=workspace_id)
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
            'transaction_type': transaction_type,
            'quantity': qty,
            'unit_cost': unit_cost,
            'total_cost': (unit_cost * Decimal(qty)).quantize(Decimal('0.01')),
            'qty_before': qty_before,
            'qty_after': qty_after,
            'value_before': value_before,
            'value_after': value_after,
            'avg_price_before': unit_cost,
            'avg_price_after': unit_cost,
            'source_type': source_type,
            'source_id': source_id,
            'transfer_destination_type': dest_type,
            'transfer_destination_id': dest_id,
            'notes': notes,
            'performed_by': user_id,
        },
    )
    mi.qty = qty_after
    session.flush()

    name = item_name(session, item_id, workspace_id)
    metadata = {"item_id": item_id, "item_name": name, "quantity": qty}
    if source_type == 'work_order':
        metadata['work_order_id'] = source_id
    machine_activity_manager.log_event(
        session,
        machine_id,
        workspace_id,
        activity_event_type,
        activity_description or f"{transaction_type}: {qty} units of {name}",
        performed_by=user_id,
        metadata=metadata,
    )
    return unit_cost


def _machine_in(
    session: Session,
    *,
    machine_id: int,
    item_id: int,
    qty: int,
    unit_cost: Decimal,
    transaction_type: str,
    source_type: str,
    source_id: int,
    notes: str,
    workspace_id: int,
    user_id: int,
    source_loc_type: Optional[str],
    source_loc_id: Optional[int],
    activity_event_type: str,
    activity_description: Optional[str] = None,
) -> None:
    machine = machine_dao.get_by_id_and_workspace(session, id=machine_id, workspace_id=workspace_id)
    if not machine:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f'Machine with ID {machine_id} not found')

    mi = ensure_machine_item(session, machine_id=machine_id, item_id=item_id, workspace_id=workspace_id)
    qty_before = mi.qty
    qty_after = qty_before + qty
    avg_before = get_machine_unit_cost(session, machine_id=machine_id, item_id=item_id, workspace_id=workspace_id)
    avg_after = weighted_avg_price(qty_before, avg_before if qty_before > 0 else None, qty, unit_cost)
    value_before = Decimal(qty_before) * avg_before
    value_after = Decimal(qty_after) * avg_after

    machine_item_ledger_dao.create(
        session,
        obj_in={
            'workspace_id': workspace_id,
            'machine_id': machine_id,
            'item_id': item_id,
            'transaction_type': transaction_type,
            'quantity': qty,
            'unit_cost': unit_cost,
            'total_cost': (unit_cost * Decimal(qty)).quantize(Decimal('0.01')),
            'qty_before': qty_before,
            'qty_after': qty_after,
            'value_before': value_before,
            'value_after': value_after,
            'avg_price_before': avg_before,
            'avg_price_after': avg_after,
            'source_type': source_type,
            'source_id': source_id,
            'transfer_source_type': source_loc_type,
            'transfer_source_id': source_loc_id,
            'notes': notes,
            'performed_by': user_id,
        },
    )
    mi.qty = qty_after
    session.flush()

    name = item_name(session, item_id, workspace_id)
    metadata = {"item_id": item_id, "item_name": name, "quantity": qty}
    if source_type == 'work_order':
        metadata['work_order_id'] = source_id
    machine_activity_manager.log_event(
        session,
        machine_id,
        workspace_id,
        activity_event_type,
        activity_description or f"{transaction_type}: {qty} units of {name}",
        performed_by=user_id,
        metadata=metadata,
    )


def post_stock_out(
    session: Session,
    *,
    location_type: str,
    location_id: int,
    item_id: int,
    qty: int,
    transaction_type: str,
    source_type: str,
    source_id: int,
    notes: str,
    workspace_id: int,
    user_id: int,
    dest_type: Optional[str] = None,
    dest_id: Optional[int] = None,
    activity_event_type: Optional[str] = None,
    activity_description: Optional[str] = None,
) -> Decimal:
    """Deduct stock from a storage/damaged factory bucket or a machine's on-hand stock."""
    if location_type in ('storage', 'damaged'):
        return _storage_out(
            session,
            factory_id=location_id,
            item_id=item_id,
            inventory_type=inventory_type_for_location(location_type),
            qty=qty,
            transaction_type=transaction_type,
            source_type=source_type,
            source_id=source_id,
            notes=notes,
            workspace_id=workspace_id,
            user_id=user_id,
            dest_type=dest_type,
            dest_id=dest_id,
        )
    if location_type == 'machine':
        return _machine_out(
            session,
            machine_id=location_id,
            item_id=item_id,
            qty=qty,
            transaction_type=transaction_type,
            source_type=source_type,
            source_id=source_id,
            notes=notes,
            workspace_id=workspace_id,
            user_id=user_id,
            dest_type=dest_type,
            dest_id=dest_id,
            activity_event_type=activity_event_type or transaction_type,
            activity_description=activity_description,
        )
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f'Unsupported source location type: {location_type}',
    )


def post_stock_in(
    session: Session,
    *,
    location_type: str,
    location_id: int,
    item_id: int,
    qty: int,
    unit_cost: Decimal,
    transaction_type: str,
    source_type: str,
    source_id: int,
    notes: str,
    workspace_id: int,
    user_id: int,
    source_loc_type: Optional[str] = None,
    source_loc_id: Optional[int] = None,
    activity_event_type: Optional[str] = None,
    activity_description: Optional[str] = None,
) -> None:
    """Restore/add stock to a storage/damaged factory bucket or a machine's on-hand stock."""
    if location_type in ('storage', 'damaged'):
        _storage_in(
            session,
            factory_id=location_id,
            item_id=item_id,
            inventory_type=inventory_type_for_location(location_type),
            qty=qty,
            unit_cost=unit_cost,
            transaction_type=transaction_type,
            source_type=source_type,
            source_id=source_id,
            notes=notes,
            workspace_id=workspace_id,
            user_id=user_id,
            source_loc_type=source_loc_type,
            source_loc_id=source_loc_id,
        )
        return
    if location_type == 'machine':
        _machine_in(
            session,
            machine_id=location_id,
            item_id=item_id,
            qty=qty,
            unit_cost=unit_cost,
            transaction_type=transaction_type,
            source_type=source_type,
            source_id=source_id,
            notes=notes,
            workspace_id=workspace_id,
            user_id=user_id,
            source_loc_type=source_loc_type,
            source_loc_id=source_loc_id,
            activity_event_type=activity_event_type or transaction_type,
            activity_description=activity_description,
        )
        return
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f'Unsupported destination location type: {location_type}',
    )
