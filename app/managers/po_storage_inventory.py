"""Post completed purchase order lines into factory STORAGE inventory."""
from decimal import Decimal
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.dao.factory import factory_dao
from app.dao.inventory import inventory_dao
from app.dao.inventory_ledger import inventory_ledger_dao
from app.models.enums import InventoryTypeEnum
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_order_item import PurchaseOrderItem

PO_INVENTORY_SOURCE_TYPE = 'purchase_order'


def _quantity_to_int(quantity: Decimal, *, line_number: int) -> int:
    if quantity != quantity.to_integral_value():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f'Line {line_number} has a fractional received quantity; '
                'storage inventory requires whole units'
            ),
        )
    qty = int(quantity)
    if qty <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'Line {line_number} has no received quantity to post',
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


def post_purchase_order_to_storage(
    session: Session,
    po: PurchaseOrder,
    items: List[PurchaseOrderItem],
    workspace_id: int,
    user_id: int,
) -> int:
    """
    Add fully received PO lines to factory STORAGE inventory.

    Returns the number of lines posted (skips already-posted lines).
    """
    if po.destination_type != 'storage':
        return 0

    factory_id = po.destination_id
    factory = factory_dao.get_by_id_and_workspace(
        session, id=factory_id, workspace_id=workspace_id
    )
    if not factory:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f'Factory with ID {factory_id} not found',
        )

    lines_posted = 0
    for line in items:
        if inventory_ledger_dao.exists_for_source(
            session,
            workspace_id=workspace_id,
            source_type=PO_INVENTORY_SOURCE_TYPE,
            source_id=line.id,
        ):
            continue

        received = Decimal(str(line.quantity_received or 0))
        qty = _quantity_to_int(received, line_number=line.line_number)
        unit_cost = Decimal(str(line.unit_price))

        inv = inventory_dao.get_by_factory_item_type(
            session,
            factory_id=factory_id,
            item_id=line.item_id,
            inventory_type=InventoryTypeEnum.STORAGE,
            workspace_id=workspace_id,
        )
        if not inv:
            inv = inventory_dao.create(
                session,
                obj_in={
                    'workspace_id': workspace_id,
                    'inventory_type': InventoryTypeEnum.STORAGE,
                    'factory_id': factory_id,
                    'item_id': line.item_id,
                    'qty': 0,
                    'avg_price': None,
                    'created_by': user_id,
                },
            )

        old_qty = inv.qty
        old_avg = inv.avg_price
        new_qty = old_qty + qty
        new_avg = _weighted_avg_price(old_qty, old_avg, qty, unit_cost)

        inventory_ledger_dao.create(
            session,
            obj_in={
                'workspace_id': workspace_id,
                'inventory_type': InventoryTypeEnum.STORAGE,
                'factory_id': factory_id,
                'item_id': line.item_id,
                'transaction_type': 'purchase_order',
                'quantity': qty,
                'unit_cost': unit_cost,
                'total_cost': (unit_cost * Decimal(qty)).quantize(Decimal('0.01')),
                'qty_before': old_qty,
                'qty_after': new_qty,
                'avg_price_before': old_avg,
                'avg_price_after': new_avg,
                'source_type': PO_INVENTORY_SOURCE_TYPE,
                'source_id': line.id,
                'notes': f'PO {po.po_number} line {line.line_number}',
                'performed_by': user_id,
            },
        )

        inv.qty = new_qty
        inv.avg_price = new_avg
        inv.updated_by = user_id
        session.flush()
        lines_posted += 1

    return lines_posted
