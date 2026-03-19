"""Machine item DAO operations"""
from typing import List, Optional
from sqlalchemy.orm import Session
from app.dao.base import BaseDAO
from app.models.machine_item import MachineItem
from app.schemas.machine_item import MachineItemCreate, MachineItemUpdate


class DAOMachineItem(BaseDAO[MachineItem, MachineItemCreate, MachineItemUpdate]):
    """DAO operations for MachineItem model"""

    def get_by_workspace(
        self, db: Session, *, workspace_id: int, skip: int = 0, limit: int = 100
    ) -> List[MachineItem]:
        """Get all machine items in workspace"""
        return (
            db.query(MachineItem)
            .filter(MachineItem.workspace_id == workspace_id)
            .offset(skip).limit(limit).all()
        )

    def get_by_id_and_workspace(
        self, db: Session, *, id: int, workspace_id: int
    ) -> Optional[MachineItem]:
        """Get machine item by ID with workspace isolation"""
        return (
            db.query(MachineItem)
            .filter(
                MachineItem.id == id,
                MachineItem.workspace_id == workspace_id,
            )
            .first()
        )

    def get_by_machine(
        self, db: Session, *, machine_id: int, workspace_id: int, skip: int = 0, limit: int = 100
    ) -> List[MachineItem]:
        """Get machine items by machine ID (workspace-filtered)"""
        return (
            db.query(MachineItem)
            .filter(
                MachineItem.workspace_id == workspace_id,
                MachineItem.machine_id == machine_id,
            )
            .offset(skip).limit(limit).all()
        )

    def get_by_machine_and_item(
        self, db: Session, *, machine_id: int, item_id: int, workspace_id: int
    ) -> Optional[MachineItem]:
        """Get machine item by machine and item ID (workspace-filtered)"""
        return (
            db.query(MachineItem)
            .filter(
                MachineItem.workspace_id == workspace_id,
                MachineItem.machine_id == machine_id,
                MachineItem.item_id == item_id,
            )
            .first()
        )


machine_item_dao = DAOMachineItem(MachineItem)
