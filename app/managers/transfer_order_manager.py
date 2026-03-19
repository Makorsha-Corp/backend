"""Transfer Order Manager - business logic for transfer orders"""
from typing import List
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.managers.base_manager import BaseManager
from app.models.transfer_order import TransferOrder
from app.models.transfer_order_item import TransferOrderItem
from app.schemas.transfer_order import (
    TransferOrderCreate, TransferOrderUpdate,
    TransferOrderItemCreate, TransferOrderItemUpdate,
)
from app.dao.transfer_order import transfer_order_dao, transfer_order_item_dao


class TransferOrderManager(BaseManager[TransferOrder]):
    """Manager for transfer order business logic."""

    def __init__(self):
        super().__init__(TransferOrder)
        self.to_dao = transfer_order_dao
        self.item_dao = transfer_order_item_dao

    def create_transfer_order(
        self, session: Session, data: TransferOrderCreate,
        workspace_id: int, user_id: int
    ) -> TransferOrder:
        """Create transfer order with auto-generated number and nested items."""
        tr_number = self.to_dao.get_next_number(session, workspace_id=workspace_id)

        items_data = data.items or []
        to_dict = data.model_dump(exclude={'items'})
        to_dict['workspace_id'] = workspace_id
        to_dict['transfer_number'] = tr_number
        to_dict['created_by'] = user_id

        to = self.to_dao.create(session, obj_in=to_dict)

        for idx, item_data in enumerate(items_data, start=1):
            item_dict = item_data.model_dump()
            item_dict['workspace_id'] = workspace_id
            item_dict['transfer_order_id'] = to.id
            item_dict['line_number'] = idx
            self.item_dao.create(session, obj_in=item_dict)

        return to

    def update_transfer_order(
        self, session: Session, to_id: int, data: TransferOrderUpdate,
        workspace_id: int, user_id: int
    ) -> TransferOrder:
        """Update transfer order."""
        record = self.to_dao.get_by_id_and_workspace(session, id=to_id, workspace_id=workspace_id)
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Transfer order with ID {to_id} not found")

        update_dict = data.model_dump(exclude_unset=True)
        update_dict['updated_by'] = user_id
        return self.to_dao.update(session, db_obj=record, obj_in=update_dict)

    def get_transfer_order(self, session: Session, to_id: int, workspace_id: int) -> TransferOrder:
        record = self.to_dao.get_by_id_and_workspace(session, id=to_id, workspace_id=workspace_id)
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Transfer order with ID {to_id} not found")
        return record

    def list_transfer_orders(
        self, session: Session, workspace_id: int,
        skip: int = 0, limit: int = 100
    ) -> List[TransferOrder]:
        return self.to_dao.get_by_workspace(
            session, workspace_id=workspace_id,
            skip=skip, limit=limit
        )

    def delete_transfer_order(self, session: Session, to_id: int, workspace_id: int) -> None:
        record = self.to_dao.get_by_id_and_workspace(session, id=to_id, workspace_id=workspace_id)
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Transfer order with ID {to_id} not found")
        session.delete(record)
        session.flush()

    # ─── Transfer Order Items ──────────────────────────────────
    def add_item(
        self, session: Session, to_id: int, data: TransferOrderItemCreate,
        workspace_id: int
    ) -> TransferOrderItem:
        """Add item to transfer order."""
        to = self.to_dao.get_by_id_and_workspace(session, id=to_id, workspace_id=workspace_id)
        if not to:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transfer order not found")

        existing = self.item_dao.get_by_order(session, transfer_order_id=to_id, workspace_id=workspace_id)
        next_line = max((i.line_number for i in existing), default=0) + 1

        item_dict = data.model_dump()
        item_dict['workspace_id'] = workspace_id
        item_dict['transfer_order_id'] = to_id
        item_dict['line_number'] = next_line
        return self.item_dao.create(session, obj_in=item_dict)

    def update_item(
        self, session: Session, item_id: int, data: TransferOrderItemUpdate,
        workspace_id: int, user_id: int
    ) -> TransferOrderItem:
        """Update transfer order item. Stamps approval."""
        record = self.item_dao.get_by_id_and_workspace(session, id=item_id, workspace_id=workspace_id)
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transfer order item not found")

        update_dict = data.model_dump(exclude_unset=True)

        if 'approved' in update_dict and update_dict['approved'] and not record.approved:
            from sqlalchemy.sql import func
            update_dict['approved_by'] = user_id
            update_dict['approved_at'] = func.now()

        return self.item_dao.update(session, db_obj=record, obj_in=update_dict)

    def remove_item(self, session: Session, item_id: int, workspace_id: int) -> TransferOrderItem:
        """Remove item from transfer order."""
        record = self.item_dao.get_by_id_and_workspace(session, id=item_id, workspace_id=workspace_id)
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transfer order item not found")
        session.delete(record)
        session.flush()
        return record

    def get_items(self, session: Session, to_id: int, workspace_id: int) -> List[TransferOrderItem]:
        return self.item_dao.get_by_order(session, transfer_order_id=to_id, workspace_id=workspace_id)


transfer_order_manager = TransferOrderManager()
