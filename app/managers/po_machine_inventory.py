"""Post completed purchase order lines into machine inventory."""
from decimal import Decimal
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.dao.item import item_dao
from app.dao.machine import machine_dao
from app.dao.machine_item import machine_item_dao
from app.dao.machine_item_ledger import machine_item_ledger_dao
from app.managers.machine_activity_manager import machine_activity_manager
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_order_item import PurchaseOrderItem
from app.models.machine_item_ledger import MachineItemLedger

PO_MACHINE_SOURCE_TYPE = "purchase_order"


def _quantity_to_int(quantity: Decimal, *, line_number: int) -> int:
    if quantity != quantity.to_integral_value():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Line {line_number} has a fractional received quantity; "
                "machine inventory requires whole units"
            ),
        )
    qty = int(quantity)
    if qty <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Line {line_number} has no received quantity to post",
        )
    return qty


def _weighted_avg_price(
    old_qty: int,
    old_avg: Optional[Decimal],
    add_qty: int,
    unit_cost: Decimal,
) -> Decimal:
    if add_qty <= 0:
        return old_avg or Decimal("0")
    if old_qty > 0 and old_avg is not None:
        numer = Decimal(old_qty) * old_avg + Decimal(add_qty) * unit_cost
        return (numer / Decimal(old_qty + add_qty)).quantize(Decimal("0.01"))
    return unit_cost


def _ensure_machine_item(
    session: Session, *, machine_id: int, item_id: int, workspace_id: int
):
    mi = machine_item_dao.get_by_machine_and_item(
        session, machine_id=machine_id, item_id=item_id, workspace_id=workspace_id
    )
    if mi:
        return mi
    return machine_item_dao.create(
        session,
        obj_in={
            "workspace_id": workspace_id,
            "machine_id": machine_id,
            "item_id": item_id,
            "qty": 0,
        },
    )


def _ledger_exists_for_source(
    session: Session, *, workspace_id: int, source_type: str, source_id: int
) -> bool:
    return (
        session.query(MachineItemLedger)
        .filter(
            MachineItemLedger.workspace_id == workspace_id,
            MachineItemLedger.source_type == source_type,
            MachineItemLedger.source_id == source_id,
        )
        .first()
        is not None
    )


