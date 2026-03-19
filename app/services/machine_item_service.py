"""Machine item service - transaction orchestration"""
from typing import List, Optional
from sqlalchemy.orm import Session

from app.services.base_service import BaseService
from app.models.machine_item import MachineItem
from app.schemas.machine_item import MachineItemCreate, MachineItemUpdate
from app.managers.machine_item_manager import machine_item_manager


class MachineItemService(BaseService):
    """Service for machine item operations"""

    def __init__(self):
        super().__init__()
        self.machine_item_manager = machine_item_manager

    def get_machine_item(
        self, db: Session, machine_item_id: int, workspace_id: int
    ) -> MachineItem:
        """Get a single machine item"""
        return self.machine_item_manager.get_machine_item(
            db, machine_item_id, workspace_id
        )

    def get_machine_items(
        self, db: Session, workspace_id: int,
        machine_id: Optional[int] = None,
        skip: int = 0, limit: int = 100
    ) -> List[MachineItem]:
        """List machine items"""
        return self.machine_item_manager.list_machine_items(
            db, workspace_id=workspace_id,
            machine_id=machine_id, skip=skip, limit=limit
        )

    def create_machine_item(
        self, db: Session,
        item_in: MachineItemCreate,
        workspace_id: int
    ) -> MachineItem:
        """Create a machine item with transaction management"""
        try:
            item = self.machine_item_manager.create_machine_item(
                session=db, item_data=item_in, workspace_id=workspace_id
            )
            self._commit_transaction(db)
            db.refresh(item)
            return item
        except Exception:
            self._rollback_transaction(db)
            raise

    def update_machine_item(
        self, db: Session,
        machine_item_id: int,
        item_in: MachineItemUpdate,
        workspace_id: int
    ) -> MachineItem:
        """Update a machine item with transaction management"""
        try:
            item = self.machine_item_manager.update_machine_item(
                session=db, machine_item_id=machine_item_id,
                item_data=item_in, workspace_id=workspace_id
            )
            self._commit_transaction(db)
            db.refresh(item)
            return item
        except Exception:
            self._rollback_transaction(db)
            raise

    def delete_machine_item(
        self, db: Session,
        machine_item_id: int,
        workspace_id: int
    ) -> None:
        """Delete a machine item with transaction management"""
        try:
            self.machine_item_manager.delete_machine_item(
                session=db, machine_item_id=machine_item_id,
                workspace_id=workspace_id
            )
            self._commit_transaction(db)
        except Exception:
            self._rollback_transaction(db)
            raise


machine_item_service = MachineItemService()
