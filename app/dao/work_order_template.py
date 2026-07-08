"""Work order template DAO. SECURITY: All queries MUST filter by workspace_id."""
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.dao.base import BaseDAO
from app.models.work_order_template import WorkOrderTemplate
from app.models.work_order_template_item import WorkOrderTemplateItem
from app.models.work_order_template_approver import WorkOrderTemplateApprover
from app.schemas.work_order_template import (
    WorkOrderTemplateCreate, WorkOrderTemplateUpdate,
    WorkOrderTemplateItemCreate, WorkOrderTemplateItemUpdate,
    WorkOrderTemplateApproverCreate,
)


class WorkOrderTemplateDAO(BaseDAO[WorkOrderTemplate, WorkOrderTemplateCreate, WorkOrderTemplateUpdate]):
    def get_by_workspace(
        self, db: Session, *, workspace_id: int,
        is_active: Optional[bool] = None,
        work_order_type_id: Optional[int] = None,
        skip: int = 0, limit: int = 100
    ) -> List[WorkOrderTemplate]:
        query = db.query(WorkOrderTemplate).filter(WorkOrderTemplate.workspace_id == workspace_id)
        if is_active is not None:
            query = query.filter(WorkOrderTemplate.is_active == is_active)
        if work_order_type_id:
            query = query.filter(WorkOrderTemplate.work_order_type_id == work_order_type_id)
        return query.order_by(desc(WorkOrderTemplate.created_at)).offset(skip).limit(limit).all()

    def get_by_id_and_workspace(self, db: Session, *, id: int, workspace_id: int) -> Optional[WorkOrderTemplate]:
        return db.query(WorkOrderTemplate).filter(
            WorkOrderTemplate.id == id, WorkOrderTemplate.workspace_id == workspace_id,
        ).first()


class WorkOrderTemplateItemDAO(BaseDAO[WorkOrderTemplateItem, WorkOrderTemplateItemCreate, WorkOrderTemplateItemUpdate]):
    def get_by_template(self, db: Session, *, work_order_template_id: int, workspace_id: int) -> List[WorkOrderTemplateItem]:
        return db.query(WorkOrderTemplateItem).filter(
            WorkOrderTemplateItem.work_order_template_id == work_order_template_id,
            WorkOrderTemplateItem.workspace_id == workspace_id,
        ).order_by(WorkOrderTemplateItem.id).all()

    def get_by_id_and_workspace(self, db: Session, *, id: int, workspace_id: int) -> Optional[WorkOrderTemplateItem]:
        return db.query(WorkOrderTemplateItem).filter(
            WorkOrderTemplateItem.id == id, WorkOrderTemplateItem.workspace_id == workspace_id,
        ).first()


class WorkOrderTemplateApproverDAO(BaseDAO[WorkOrderTemplateApprover, WorkOrderTemplateApproverCreate, WorkOrderTemplateApproverCreate]):
    def get_by_template(self, db: Session, *, work_order_template_id: int, workspace_id: int) -> List[WorkOrderTemplateApprover]:
        return db.query(WorkOrderTemplateApprover).filter(
            WorkOrderTemplateApprover.work_order_template_id == work_order_template_id,
            WorkOrderTemplateApprover.workspace_id == workspace_id,
        ).all()

    def delete_all_for_template(self, db: Session, *, work_order_template_id: int, workspace_id: int) -> None:
        db.query(WorkOrderTemplateApprover).filter(
            WorkOrderTemplateApprover.work_order_template_id == work_order_template_id,
            WorkOrderTemplateApprover.workspace_id == workspace_id,
        ).delete()


work_order_template_dao = WorkOrderTemplateDAO(WorkOrderTemplate)
work_order_template_item_dao = WorkOrderTemplateItemDAO(WorkOrderTemplateItem)
work_order_template_approver_dao = WorkOrderTemplateApproverDAO(WorkOrderTemplateApprover)
