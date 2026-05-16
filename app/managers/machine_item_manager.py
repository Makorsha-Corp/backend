"""Machine item manager - business logic for machine item operations"""
from typing import Any, Dict, List, Optional
from decimal import Decimal
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.machine_item import MachineItem
from app.schemas.machine_item import MachineItemCreate, MachineItemUpdate
from app.dao.machine_item import machine_item_dao
from app.dao.machine_item_ledger import machine_item_ledger_dao
from app.dao.machine import machine_dao


class MachineItemManager:
    """Manager for machine item business logic"""

    def __init__(self):
        self.machine_item_dao = machine_item_dao
        self.machine_item_ledger_dao = machine_item_ledger_dao
        self.machine_dao = machine_dao

    def get_machine_item(
        self, session: Session, machine_item_id: int, workspace_id: int
    ) -> MachineItem:
        """Get a single machine item by ID"""
        item = self.machine_item_dao.get_by_id_and_workspace(
            session, id=machine_item_id, workspace_id=workspace_id
        )
        if not item:
            raise HTTPException(status_code=404, detail="Machine item not found")
        return item

    def list_machine_items(
        self, session: Session, workspace_id: int,
        machine_id: Optional[int] = None,
        skip: int = 0, limit: int = 100
    ) -> List[MachineItem]:
        """List machine items with optional machine filter"""
        if machine_id:
            return self.machine_item_dao.get_by_machine(
                session, machine_id=machine_id,
                workspace_id=workspace_id, skip=skip, limit=limit
            )
        return self.machine_item_dao.get_by_workspace(
            session, workspace_id=workspace_id, skip=skip, limit=limit
        )

    def _write_ledger_entry(
        self,
        session: Session,
        *,
        workspace_id: int,
        machine_id: int,
        item_id: int,
        transaction_type: str,
        quantity: int,
        qty_before: int,
        qty_after: int,
        user_id: int,
        notes: str,
        source_type: str = "manual",
    ) -> None:
        """Append a `machine_item_ledger` row for a manual stock change.

        Builds the payload as a dict (bypassing the Pydantic schema) so
        `workspace_id` and `performed_by` actually persist — they're not part
        of `MachineItemLedgerCreate`.
        """
        zero = Decimal("0.00")
        ledger_payload: Dict[str, Any] = {
            "workspace_id": workspace_id,
            "machine_id": machine_id,
            "item_id": item_id,
            "transaction_type": transaction_type,
            "quantity": quantity,
            "unit_cost": zero,
            "total_cost": zero,
            "qty_before": qty_before,
            "qty_after": qty_after,
            "value_before": zero,
            "value_after": zero,
            "avg_price_before": zero,
            "avg_price_after": zero,
            "source_type": source_type,
            "notes": notes,
            "performed_by": user_id,
        }
        self.machine_item_ledger_dao.create(session, obj_in=ledger_payload)

    def create_machine_item(
        self, session: Session,
        item_data: MachineItemCreate,
        workspace_id: int,
        user_id: int,
    ) -> MachineItem:
        """Create a new machine item and log the initial stock as a ledger entry."""
        machine = self.machine_dao.get_by_id_and_workspace(
            session, id=item_data.machine_id, workspace_id=workspace_id
        )
        if not machine:
            raise HTTPException(status_code=404, detail="Machine not found in this workspace")
        if machine.is_deleted:
            raise HTTPException(status_code=400, detail="Cannot add items to a deleted machine")

        existing = self.machine_item_dao.get_by_machine_and_item(
            session, machine_id=item_data.machine_id,
            item_id=item_data.item_id, workspace_id=workspace_id
        )
        if existing:
            raise HTTPException(
                status_code=409,
                detail="This item already exists on this machine. Update the existing record instead."
            )

        item_dict = item_data.model_dump()
        item_dict['workspace_id'] = workspace_id
        record = self.machine_item_dao.create(session, obj_in=item_dict)

        # Log initial stock as a manual_add ledger entry when qty > 0
        if record.qty > 0:
            self._write_ledger_entry(
                session,
                workspace_id=workspace_id,
                machine_id=record.machine_id,
                item_id=record.item_id,
                transaction_type="manual_add",
                quantity=record.qty,
                qty_before=0,
                qty_after=record.qty,
                user_id=user_id,
                notes="Initial machine inventory record created",
            )

        return record

    def update_machine_item(
        self, session: Session,
        machine_item_id: int,
        item_data: MachineItemUpdate,
        workspace_id: int,
        user_id: int,
    ) -> MachineItem:
        """Update a machine item; log a ledger entry when `qty` changes."""
        item = self.machine_item_dao.get_by_id_and_workspace(
            session, id=machine_item_id, workspace_id=workspace_id
        )
        if not item:
            raise HTTPException(status_code=404, detail="Machine item not found")

        old_qty = item.qty
        update_data = item_data.model_dump(exclude_unset=True)
        updated = self.machine_item_dao.update(session, db_obj=item, obj_in=update_data)

        new_qty = update_data.get("qty")
        if new_qty is not None and new_qty != old_qty:
            self._write_ledger_entry(
                session,
                workspace_id=workspace_id,
                machine_id=updated.machine_id,
                item_id=updated.item_id,
                transaction_type="inventory_adjustment",
                quantity=abs(new_qty - old_qty),
                qty_before=old_qty,
                qty_after=new_qty,
                user_id=user_id,
                notes=f"Manual machine inventory adjustment: {old_qty} -> {new_qty}",
                source_type="adjustment",
            )

        return updated

    def delete_machine_item(
        self, session: Session,
        machine_item_id: int,
        workspace_id: int,
        user_id: int,
    ) -> None:
        """Delete a machine item; log a final adjustment entry when stock > 0."""
        item = self.machine_item_dao.get_by_id_and_workspace(
            session, id=machine_item_id, workspace_id=workspace_id
        )
        if not item:
            raise HTTPException(status_code=404, detail="Machine item not found")

        if item.qty > 0:
            self._write_ledger_entry(
                session,
                workspace_id=workspace_id,
                machine_id=item.machine_id,
                item_id=item.item_id,
                transaction_type="inventory_adjustment",
                quantity=item.qty,
                qty_before=item.qty,
                qty_after=0,
                user_id=user_id,
                notes="Machine inventory record deleted",
                source_type="adjustment",
            )

        self.machine_item_dao.remove(session, id=machine_item_id)


machine_item_manager = MachineItemManager()
