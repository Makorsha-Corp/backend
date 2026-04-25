"""Order Template Service - transaction orchestration"""
from typing import List, Optional
from sqlalchemy.orm import Session

from app.services.base_service import BaseService
from app.managers.order_template_manager import order_template_manager
from app.models.order_template import OrderTemplate
from app.models.order_template_item import OrderTemplateItem
from app.schemas.order_template import (
    OrderTemplateCreate, OrderTemplateUpdate,
    OrderTemplateItemCreate, OrderTemplateItemUpdate,
)


class OrderTemplateService(BaseService):
    """Service for order template workflows. Handles commit/rollback."""

    def __init__(self):
        super().__init__()
        self.manager = order_template_manager

    def create_template(
        self, db: Session, tpl_in: OrderTemplateCreate,
        workspace_id: int, user_id: int
    ) -> OrderTemplate:
        try:
            record = self.manager.create_template(db, data=tpl_in, workspace_id=workspace_id, user_id=user_id)
            self._commit_transaction(db)
            db.refresh(record)
            return record
        except Exception:
            self._rollback_transaction(db)
            raise

    def update_template(
        self, db: Session, tpl_id: int, tpl_in: OrderTemplateUpdate,
        workspace_id: int, user_id: int
    ) -> OrderTemplate:
        try:
            record = self.manager.update_template(db, tpl_id=tpl_id, data=tpl_in, workspace_id=workspace_id, user_id=user_id)
            self._commit_transaction(db)
            db.refresh(record)
            return record
        except Exception:
            self._rollback_transaction(db)
            raise

    def get_template(self, db: Session, tpl_id: int, workspace_id: int) -> OrderTemplate:
        return self.manager.get_template(db, tpl_id, workspace_id)

    def list_templates(
        self, db: Session, workspace_id: int,
        is_active: Optional[bool] = None,
        expense_category: Optional[str] = None,
        skip: int = 0, limit: int = 100
    ) -> List[OrderTemplate]:
        return self.manager.list_templates(
            db, workspace_id=workspace_id,
            is_active=is_active, expense_category=expense_category,
            skip=skip, limit=limit
        )

    def delete_template(self, db: Session, tpl_id: int, workspace_id: int, user_id: int) -> None:
        try:
            self.manager.delete_template(db, tpl_id=tpl_id, workspace_id=workspace_id, user_id=user_id)
            self._commit_transaction(db)
        except Exception:
            self._rollback_transaction(db)
            raise

    # ─── Items ─────────────────────────────────────────────────
    def add_item(
        self, db: Session, tpl_id: int, item_in: OrderTemplateItemCreate,
        workspace_id: int
    ) -> OrderTemplateItem:
        try:
            record = self.manager.add_item(db, tpl_id=tpl_id, data=item_in, workspace_id=workspace_id)
            self._commit_transaction(db)
            db.refresh(record)
            return record
        except Exception:
            self._rollback_transaction(db)
            raise

    def update_item(
        self, db: Session, item_id: int, item_in: OrderTemplateItemUpdate,
        workspace_id: int
    ) -> OrderTemplateItem:
        try:
            record = self.manager.update_item(db, item_id=item_id, data=item_in, workspace_id=workspace_id)
            self._commit_transaction(db)
            db.refresh(record)
            return record
        except Exception:
            self._rollback_transaction(db)
            raise

    def remove_item(self, db: Session, item_id: int, workspace_id: int) -> OrderTemplateItem:
        try:
            record = self.manager.remove_item(db, item_id=item_id, workspace_id=workspace_id)
            self._commit_transaction(db)
            return record
        except Exception:
            self._rollback_transaction(db)
            raise

    def get_items(self, db: Session, tpl_id: int, workspace_id: int) -> List[OrderTemplateItem]:
        return self.manager.get_items(db, tpl_id, workspace_id)


order_template_service = OrderTemplateService()
