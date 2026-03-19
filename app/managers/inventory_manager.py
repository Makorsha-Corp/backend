"""Inventory Manager - business logic for unified inventory"""
from typing import List, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.managers.base_manager import BaseManager
from app.models.inventory import Inventory
from app.models.enums import InventoryTypeEnum
from app.schemas.inventory import InventoryCreate, InventoryUpdate
from app.dao.inventory import inventory_dao
from app.dao.inventory_ledger import inventory_ledger_dao
from app.dao.factory import factory_dao


class InventoryManager(BaseManager[Inventory]):
    """Manager for unified inventory business logic."""

    def __init__(self):
        super().__init__(Inventory)
        self.inv_dao = inventory_dao
        self.ledger_dao = inventory_ledger_dao

    def create_inventory(
        self, session: Session, data: InventoryCreate,
        workspace_id: int, user_id: int
    ) -> Inventory:
        """Create inventory record. Validates factory exists."""
        factory = factory_dao.get_by_id_and_workspace(
            session, id=data.factory_id, workspace_id=workspace_id
        )
        if not factory:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Factory with ID {data.factory_id} not found"
            )

        # Check for duplicate
        existing = self.inv_dao.get_by_factory_item_type(
            session, factory_id=data.factory_id, item_id=data.item_id,
            inventory_type=data.inventory_type, workspace_id=workspace_id
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Inventory record already exists for this item/type/factory combination"
            )

        inv_dict = data.model_dump()
        inv_dict['workspace_id'] = workspace_id
        inv_dict['created_by'] = user_id

        record = self.inv_dao.create(session, obj_in=inv_dict)

        # Create initial ledger entry if qty > 0
        if data.qty > 0:
            ledger_dict = {
                'workspace_id': workspace_id,
                'inventory_type': data.inventory_type,
                'factory_id': data.factory_id,
                'item_id': data.item_id,
                'transaction_type': 'manual_add',
                'quantity': data.qty,
                'unit_cost': data.avg_price,
                'total_cost': (data.avg_price * data.qty) if data.avg_price else None,
                'qty_before': 0,
                'qty_after': data.qty,
                'avg_price_before': None,
                'avg_price_after': data.avg_price,
                'source_type': 'manual',
                'notes': 'Initial inventory record created',
                'performed_by': user_id,
            }
            self.ledger_dao.create(session, obj_in=ledger_dict)

        return record

    def update_inventory(
        self, session: Session, inv_id: int, data: InventoryUpdate,
        workspace_id: int, user_id: int
    ) -> Inventory:
        """Update inventory record. Creates ledger entry if qty changes."""
        record = self.inv_dao.get_by_id_and_workspace(
            session, id=inv_id, workspace_id=workspace_id
        )
        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Inventory record with ID {inv_id} not found"
            )
        if record.is_deleted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot update a deleted inventory record"
            )

        old_qty = record.qty
        old_avg = record.avg_price

        update_dict = data.model_dump(exclude_unset=True)
        update_dict['updated_by'] = user_id

        updated = self.inv_dao.update(session, db_obj=record, obj_in=update_dict)

        # If qty changed, create ledger entry
        new_qty = update_dict.get('qty')
        if new_qty is not None and new_qty != old_qty:
            new_avg = update_dict.get('avg_price', old_avg)
            ledger_dict = {
                'workspace_id': workspace_id,
                'inventory_type': record.inventory_type,
                'factory_id': record.factory_id,
                'item_id': record.item_id,
                'transaction_type': 'inventory_adjustment',
                'quantity': abs(new_qty - old_qty),
                'unit_cost': new_avg,
                'total_cost': (new_avg * abs(new_qty - old_qty)) if new_avg else None,
                'qty_before': old_qty,
                'qty_after': new_qty,
                'avg_price_before': old_avg,
                'avg_price_after': new_avg,
                'source_type': 'adjustment',
                'notes': f'Quantity adjusted from {old_qty} to {new_qty}',
                'performed_by': user_id,
            }
            self.ledger_dao.create(session, obj_in=ledger_dict)

        return updated

    def get_inventory(self, session: Session, inv_id: int, workspace_id: int) -> Inventory:
        """Get inventory record by ID."""
        record = self.inv_dao.get_by_id_and_workspace(session, id=inv_id, workspace_id=workspace_id)
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Inventory record with ID {inv_id} not found")
        return record

    def list_inventory(
        self, session: Session, workspace_id: int,
        inventory_type: Optional[InventoryTypeEnum] = None,
        factory_id: Optional[int] = None,
        skip: int = 0, limit: int = 100
    ) -> List[Inventory]:
        """List inventory records with optional filters."""
        return self.inv_dao.get_by_workspace(
            session, workspace_id=workspace_id,
            inventory_type=inventory_type, factory_id=factory_id,
            skip=skip, limit=limit
        )

    def delete_inventory(self, session: Session, inv_id: int, workspace_id: int, user_id: int) -> Inventory:
        """Soft delete inventory record."""
        record = self.inv_dao.get_by_id_and_workspace(session, id=inv_id, workspace_id=workspace_id)
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Inventory record with ID {inv_id} not found")
        if record.is_deleted:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inventory record is already deleted")
        return self.inv_dao.soft_delete(session, db_obj=record, deleted_by=user_id)


inventory_manager = InventoryManager()
