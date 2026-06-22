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


def post_purchase_order_to_machine(
    session: Session,
    po: PurchaseOrder,
    items: List[PurchaseOrderItem],
    workspace_id: int,
    user_id: int,
) -> int:
    """Add fully received PO lines to a machine destination. Returns lines posted."""
    if po.destination_type != "machine":
        return 0

    machine_id = po.destination_id
    machine = machine_dao.get_by_id_and_workspace(
        session, id=machine_id, workspace_id=workspace_id
    )
    if not machine:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Machine with ID {machine_id} not found",
        )

    lines_posted = 0
    for line in items:
        if _ledger_exists_for_source(
            session,
            workspace_id=workspace_id,
            source_type=PO_MACHINE_SOURCE_TYPE,
            source_id=line.id,
        ):
            continue

        received = Decimal(str(line.quantity_received or 0))
        qty = _quantity_to_int(received, line_number=line.line_number)
        unit_cost = Decimal(str(line.unit_price))

        mi = _ensure_machine_item(
            session, machine_id=machine_id, item_id=line.item_id, workspace_id=workspace_id
        )
        qty_before = mi.qty
        qty_after = qty_before + qty
        avg_before = Decimal("0")
        latest = machine_item_ledger_dao.get_latest_entry(
            session, machine_id=machine_id, item_id=line.item_id, workspace_id=workspace_id
        )
        if latest and latest.avg_price_after is not None:
            avg_before = Decimal(str(latest.avg_price_after))
        avg_after = _weighted_avg_price(qty_before, avg_before if qty_before > 0 else None, qty, unit_cost)

        machine_item_ledger_dao.create(
            session,
            obj_in={
                "workspace_id": workspace_id,
                "machine_id": machine_id,
                "item_id": line.item_id,
                "transaction_type": "purchase_order",
                "quantity": qty,
                "unit_cost": unit_cost,
                "total_cost": (unit_cost * Decimal(qty)).quantize(Decimal("0.01")),
                "qty_before": qty_before,
                "qty_after": qty_after,
                "value_before": Decimal(qty_before) * avg_before,
                "value_after": Decimal(qty_after) * avg_after,
                "avg_price_before": avg_before,
                "avg_price_after": avg_after,
                "source_type": PO_MACHINE_SOURCE_TYPE,
                "source_id": line.id,
                "notes": f"PO {po.po_number} line {line.line_number}",
                "performed_by": user_id,
            },
        )
        mi.qty = qty_after
        session.flush()

        catalog_item = item_dao.get_by_id_and_workspace(
            session, id=line.item_id, workspace_id=workspace_id
        )
        item_name = catalog_item.name if catalog_item else f"Item #{line.item_id}"
        machine_activity_manager.log_event(
            session,
            machine_id,
            workspace_id,
            "purchase_received",
            f"Purchase received: {qty} units of {item_name} from PO {po.po_number}",
            performed_by=user_id,
            metadata={
                "item_id": line.item_id,
                "item_name": item_name,
                "purchase_order_id": po.id,
                "quantity": qty,
            },
        )
        lines_posted += 1

    return lines_posted
