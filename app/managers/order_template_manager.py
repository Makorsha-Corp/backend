"""Order Template Manager - business logic for expense order templates"""
from typing import List, Optional
from decimal import Decimal
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.managers.base_manager import BaseManager
from app.models.order_template import OrderTemplate
from app.models.order_template_item import OrderTemplateItem
from app.schemas.order_template import (
    OrderTemplateCreate, OrderTemplateUpdate,
    OrderTemplateItemCreate, OrderTemplateItemUpdate,
)
from app.dao.order_template import order_template_dao, order_template_item_dao


class OrderTemplateManager(BaseManager[OrderTemplate]):
    """Manager for order template business logic."""

    def __init__(self):
        super().__init__(OrderTemplate)
        self.tpl_dao = order_template_dao
        self.item_dao = order_template_item_dao

    def create_template(
        self, session: Session, data: OrderTemplateCreate,
        workspace_id: int, user_id: int
    ) -> OrderTemplate:
        """Create order template with nested items."""
        items_data = data.items or []
        tpl_dict = data.model_dump(exclude={'items'})
        tpl_dict['workspace_id'] = workspace_id
        tpl_dict['created_by'] = user_id

        tpl = self.tpl_dao.create(session, obj_in=tpl_dict)

        for idx, item_data in enumerate(items_data, start=1):
            item_dict = item_data.model_dump()
            item_dict['workspace_id'] = workspace_id
            item_dict['order_template_id'] = tpl.id
            item_dict['line_number'] = idx

            qty = Decimal(str(item_dict.get('quantity', 1)))
            price = Decimal(str(item_dict.get('unit_price') or 0))
            item_dict['line_subtotal'] = qty * price

            self.item_dao.create(session, obj_in=item_dict)

        return tpl

    def update_template(
        self, session: Session, tpl_id: int, data: OrderTemplateUpdate,
        workspace_id: int, user_id: int
    ) -> OrderTemplate:
        """Update order template."""
        record = self.tpl_dao.get_by_id_and_workspace(session, id=tpl_id, workspace_id=workspace_id)
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Order template with ID {tpl_id} not found")

        update_dict = data.model_dump(exclude_unset=True)
        update_dict['updated_by'] = user_id
        return self.tpl_dao.update(session, db_obj=record, obj_in=update_dict)

    def get_template(self, session: Session, tpl_id: int, workspace_id: int) -> OrderTemplate:
        record = self.tpl_dao.get_by_id_and_workspace(session, id=tpl_id, workspace_id=workspace_id)
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Order template with ID {tpl_id} not found")
        return record

    def list_templates(
        self, session: Session, workspace_id: int,
        is_active: Optional[bool] = None,
        expense_category: Optional[str] = None,
        skip: int = 0, limit: int = 100
    ) -> List[OrderTemplate]:
        return self.tpl_dao.get_by_workspace(
            session, workspace_id=workspace_id,
            is_active=is_active, expense_category=expense_category,
            skip=skip, limit=limit
        )

    def delete_template(self, session: Session, tpl_id: int, workspace_id: int, user_id: int) -> None:
        record = self.tpl_dao.get_by_id_and_workspace(session, id=tpl_id, workspace_id=workspace_id)
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Order template with ID {tpl_id} not found")
        if not record.is_active:
            return  # Already deleted — idempotent
        self.tpl_dao.update(session, db_obj=record, obj_in={'is_active': False, 'updated_by': user_id})

    # ─── Template Items ────────────────────────────────────────
    def add_item(
        self, session: Session, tpl_id: int, data: OrderTemplateItemCreate,
        workspace_id: int
    ) -> OrderTemplateItem:
        """Add item to template."""
        tpl = self.tpl_dao.get_by_id_and_workspace(session, id=tpl_id, workspace_id=workspace_id)
        if not tpl:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order template not found")

        existing = self.item_dao.get_by_template(session, order_template_id=tpl_id, workspace_id=workspace_id)
        next_line = max((i.line_number for i in existing), default=0) + 1

        item_dict = data.model_dump()
        item_dict['workspace_id'] = workspace_id
        item_dict['order_template_id'] = tpl_id
        item_dict['line_number'] = next_line

        qty = Decimal(str(item_dict.get('quantity', 1)))
        price = Decimal(str(item_dict.get('unit_price') or 0))
        item_dict['line_subtotal'] = qty * price

        return self.item_dao.create(session, obj_in=item_dict)

    def update_item(
        self, session: Session, item_id: int, data: OrderTemplateItemUpdate,
        workspace_id: int
    ) -> OrderTemplateItem:
        """Update template item."""
        record = self.item_dao.get_by_id_and_workspace(session, id=item_id, workspace_id=workspace_id)
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template item not found")
        update_dict = data.model_dump(exclude_unset=True)

        if 'quantity' in update_dict or 'unit_price' in update_dict:
            qty = Decimal(str(update_dict.get('quantity', record.quantity)))
            price = Decimal(str(update_dict.get('unit_price') or record.unit_price or 0))
            update_dict['line_subtotal'] = qty * price

        return self.item_dao.update(session, db_obj=record, obj_in=update_dict)

    def remove_item(self, session: Session, item_id: int, workspace_id: int) -> OrderTemplateItem:
        """Remove item from template."""
        record = self.item_dao.get_by_id_and_workspace(session, id=item_id, workspace_id=workspace_id)
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template item not found")
        session.delete(record)
        session.flush()
        return record

    def get_items(self, session: Session, tpl_id: int, workspace_id: int) -> List[OrderTemplateItem]:
        return self.item_dao.get_by_template(session, order_template_id=tpl_id, workspace_id=workspace_id)


order_template_manager = OrderTemplateManager()
