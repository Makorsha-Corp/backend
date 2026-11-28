"""Machine item DAO operations"""

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.dao.base import BaseDAO
from app.models.factory import Factory
from app.models.item import Item
from app.models.machine import Machine
from app.models.machine_item import MachineItem
from app.schemas.machine_item import MachineItemCreate, MachineItemUpdate


class DAOMachineItem(BaseDAO[MachineItem, MachineItemCreate, MachineItemUpdate]):
    """DAO operations for MachineItem model"""

    def get_by_workspace(
        self, db: Session, *, workspace_id: int, skip: int = 0, limit: int = 100
    ) -> list[MachineItem]:
        """Get all machine items in workspace"""
        return (
            db.query(MachineItem)
            .filter(MachineItem.workspace_id == workspace_id)
            .offset(skip).limit(limit).all()
        )

    def get_by_id_and_workspace(
        self, db: Session, *, id: int, workspace_id: int
    ) -> MachineItem | None:
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
    ) -> list[MachineItem]:
        """Get machine items by machine ID (workspace-filtered)"""
        # Stock of a soft-deleted machine or factory, and of a removed item, is
        # hidden by the parent's state alone; the stock rows are left untouched.
        return (
            db.query(MachineItem)
            .join(Machine, Machine.id == MachineItem.machine_id)
            .join(Factory, Factory.id == Machine.factory_id)
            .join(Item, Item.id == MachineItem.item_id)
            .filter(
                MachineItem.workspace_id == workspace_id,
                MachineItem.machine_id == machine_id,
                Machine.is_deleted == False,
                Factory.is_deleted == False,
                Item.is_active == True,
            )
            .order_by(func.lower(Item.name).asc(), MachineItem.id.asc())
            .offset(skip).limit(limit).all()
        )

    def get_by_machine_and_item(
        self, db: Session, *, machine_id: int, item_id: int, workspace_id: int
    ) -> MachineItem | None:
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

    def get_by_item(
        self, db: Session, *, item_id: int, workspace_id: int
    ) -> list[MachineItem]:
        """Get all machine placements for a catalog item."""
        # Uncapped so the summary's placement count is complete. The item's own
        # state is the caller's concern; only deleted machines/factories hide rows.
        return (
            db.query(MachineItem)
            .join(Machine, Machine.id == MachineItem.machine_id)
            .join(Factory, Factory.id == Machine.factory_id)
            .filter(
                MachineItem.workspace_id == workspace_id,
                MachineItem.item_id == item_id,
                Machine.is_deleted == False,
                Factory.is_deleted == False,
            )
            .order_by(MachineItem.id.asc())
            .all()
        )


machine_item_dao = DAOMachineItem(MachineItem)
