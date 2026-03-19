"""Machine item manager - business logic for machine item operations"""
from typing import List, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.machine_item import MachineItem
from app.schemas.machine_item import MachineItemCreate, MachineItemUpdate
from app.dao.machine_item import machine_item_dao
from app.dao.machine import machine_dao


class MachineItemManager:
    """Manager for machine item business logic"""

    def __init__(self):
        self.machine_item_dao = machine_item_dao
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

    def create_machine_item(
        self, session: Session,
        item_data: MachineItemCreate,
        workspace_id: int
    ) -> MachineItem:
        """Create a new machine item"""
        # Validate machine exists and belongs to workspace
        machine = self.machine_dao.get_by_id_and_workspace(
            session, id=item_data.machine_id, workspace_id=workspace_id
        )
        if not machine:
            raise HTTPException(status_code=404, detail="Machine not found in this workspace")
        if machine.is_deleted:
            raise HTTPException(status_code=400, detail="Cannot add items to a deleted machine")

        # Check if this item already exists on this machine
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
        return self.machine_item_dao.create(session, obj_in=item_dict)

    def update_machine_item(
        self, session: Session,
        machine_item_id: int,
        item_data: MachineItemUpdate,
        workspace_id: int
    ) -> MachineItem:
        """Update a machine item"""
        item = self.machine_item_dao.get_by_id_and_workspace(
            session, id=machine_item_id, workspace_id=workspace_id
        )
        if not item:
            raise HTTPException(status_code=404, detail="Machine item not found")

        update_data = item_data.model_dump(exclude_unset=True)
        return self.machine_item_dao.update(session, db_obj=item, obj_in=update_data)

    def delete_machine_item(
        self, session: Session,
        machine_item_id: int,
        workspace_id: int
    ) -> None:
        """Delete a machine item"""
        item = self.machine_item_dao.get_by_id_and_workspace(
            session, id=machine_item_id, workspace_id=workspace_id
        )
        if not item:
            raise HTTPException(status_code=404, detail="Machine item not found")

        self.machine_item_dao.remove(session, id=machine_item_id)


machine_item_manager = MachineItemManager()
