"""Work Order Template Service - transaction orchestration"""
from typing import List, Optional
from sqlalchemy.orm import Session

from app.services.base_service import BaseService
from app.managers.work_order_template_manager import work_order_template_manager
from app.models.work_order_template import WorkOrderTemplate
from app.models.work_order_template_item import WorkOrderTemplateItem
from app.models.work_order_template_approver import WorkOrderTemplateApprover
from app.models.work_order import WorkOrder
from app.schemas.work_order_template import (
    WorkOrderTemplateCreate, WorkOrderTemplateUpdate,
    WorkOrderTemplateItemCreate, WorkOrderTemplateItemUpdate,
    GenerateWorkOrderDraftsRequest,
)


class WorkOrderTemplateService(BaseService):
    """Service for work order template workflows. Handles commit/rollback."""

    def __init__(self):
        super().__init__()
        self.manager = work_order_template_manager

    def create_template(
        self, db: Session, tpl_in: WorkOrderTemplateCreate,
        workspace_id: int, user_id: int
    ) -> WorkOrderTemplate:
        try:
            record = self.manager.create_template(db, data=tpl_in, workspace_id=workspace_id, user_id=user_id)
            self._commit_transaction(db)
            db.refresh(record)
            return record
        except Exception:
            self._rollback_transaction(db)
            raise

    def update_template(
        self, db: Session, tpl_id: int, tpl_in: WorkOrderTemplateUpdate,
        workspace_id: int, user_id: int
    ) -> WorkOrderTemplate:
        try:
            record = self.manager.update_template(db, tpl_id=tpl_id, data=tpl_in, workspace_id=workspace_id, user_id=user_id)
            self._commit_transaction(db)
            db.refresh(record)
            return record
        except Exception:
            self._rollback_transaction(db)
            raise

    def get_template(self, db: Session, tpl_id: int, workspace_id: int) -> WorkOrderTemplate:
        return self.manager.get_template(db, tpl_id, workspace_id)

    def list_templates(
        self, db: Session, workspace_id: int,
        is_active: Optional[bool] = None,
        work_order_type_id: Optional[int] = None,
        skip: int = 0, limit: int = 100
    ) -> List[WorkOrderTemplate]:
        return self.manager.list_templates(
            db, workspace_id=workspace_id,
            is_active=is_active, work_order_type_id=work_order_type_id,
            skip=skip, limit=limit
        )

    def delete_template(self, db: Session, tpl_id: int, workspace_id: int, user_id: int) -> None:
        try:
            self.manager.delete_template(db, tpl_id=tpl_id, workspace_id=workspace_id, user_id=user_id)
            self._commit_transaction(db)
        except Exception:
            self._rollback_transaction(db)
            raise

    def restore_template(self, db: Session, tpl_id: int, workspace_id: int, user_id: int) -> WorkOrderTemplate:
        try:
            record = self.manager.restore_template(db, tpl_id=tpl_id, workspace_id=workspace_id, user_id=user_id)
            self._commit_transaction(db)
            db.refresh(record)
            return record
        except Exception:
            self._rollback_transaction(db)
            raise

    # ─── Items ─────────────────────────────────────────────────
    def add_item(
        self, db: Session, tpl_id: int, item_in: WorkOrderTemplateItemCreate, workspace_id: int
    ) -> WorkOrderTemplateItem:
        try:
            record = self.manager.add_item(db, tpl_id=tpl_id, data=item_in, workspace_id=workspace_id)
            self._commit_transaction(db)
            db.refresh(record)
            return record
        except Exception:
            self._rollback_transaction(db)
            raise

    def update_item(
        self, db: Session, item_id: int, item_in: WorkOrderTemplateItemUpdate, workspace_id: int
    ) -> WorkOrderTemplateItem:
        try:
            record = self.manager.update_item(db, item_id=item_id, data=item_in, workspace_id=workspace_id)
            self._commit_transaction(db)
            db.refresh(record)
            return record
        except Exception:
            self._rollback_transaction(db)
            raise

    def remove_item(self, db: Session, item_id: int, workspace_id: int) -> WorkOrderTemplateItem:
        try:
            record = self.manager.remove_item(db, item_id=item_id, workspace_id=workspace_id)
            self._commit_transaction(db)
            return record
        except Exception:
            self._rollback_transaction(db)
            raise

    def get_items(self, db: Session, tpl_id: int, workspace_id: int) -> List[WorkOrderTemplateItem]:
        return self.manager.get_items(db, tpl_id, workspace_id)

    def get_approvers(self, db: Session, tpl_id: int, workspace_id: int) -> List[WorkOrderTemplateApprover]:
        return self.manager.get_approvers(db, tpl_id, workspace_id)

    def generate_drafts(
        self, db: Session, body: GenerateWorkOrderDraftsRequest,
        workspace_id: int, user_id: int,
    ) -> List[WorkOrder]:
        try:
            records = self.manager.generate_drafts(
                db, workspace_id=workspace_id, user_id=user_id,
                target_date=body.target_date,
                factory_section_id=body.factory_section_id,
                factory_id=body.factory_id,
            )
            self._commit_transaction(db)
            for r in records:
                db.refresh(r)
            return records
        except Exception:
            self._rollback_transaction(db)
            raise


work_order_template_service = WorkOrderTemplateService()
