"""Work Order Template Manager - business logic for reusable work order presets"""
from typing import List, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.managers.base_manager import BaseManager
from app.models.work_order_template import WorkOrderTemplate
from app.models.work_order_template_item import WorkOrderTemplateItem
from app.models.work_order_template_approver import WorkOrderTemplateApprover
from app.schemas.work_order_template import (
    WorkOrderTemplateCreate, WorkOrderTemplateUpdate,
    WorkOrderTemplateItemCreate, WorkOrderTemplateItemUpdate,
)
from app.dao.work_order_template import (
    work_order_template_dao, work_order_template_item_dao, work_order_template_approver_dao,
)
from app.dao.work_order_type import work_order_type_dao
from app.dao.workspace_member import workspace_member_dao


class WorkOrderTemplateManager(BaseManager[WorkOrderTemplate]):
    """Manager for work order template business logic."""

    def __init__(self):
        super().__init__(WorkOrderTemplate)
        self.tpl_dao = work_order_template_dao
        self.item_dao = work_order_template_item_dao
        self.approver_dao = work_order_template_approver_dao

    def _replace_approvers(
        self, session: Session, tpl_id: int, workspace_id: int, approver_user_ids: List[int]
    ) -> None:
        self.approver_dao.delete_all_for_template(session, work_order_template_id=tpl_id, workspace_id=workspace_id)
        session.flush()
        for user_id in dict.fromkeys(approver_user_ids):  # de-dupe, keep order
            member = workspace_member_dao.get_by_workspace_and_user(session, workspace_id=workspace_id, user_id=user_id)
            if not member or member.status != 'active':
                continue
            obj = WorkOrderTemplateApprover(workspace_id=workspace_id, work_order_template_id=tpl_id, user_id=user_id)
            session.add(obj)
        session.flush()

    def create_template(
        self, session: Session, data: WorkOrderTemplateCreate,
        workspace_id: int, user_id: int
    ) -> WorkOrderTemplate:
        wo_type = work_order_type_dao.get_by_id_and_workspace(
            session, id=data.work_order_type_id, workspace_id=workspace_id
        )
        if not wo_type:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Work order type with ID {data.work_order_type_id} not found")

        items_data = data.items or []
        approver_ids = data.approver_user_ids or []
        tpl_dict = data.model_dump(exclude={'items', 'approver_user_ids'})
        tpl_dict['workspace_id'] = workspace_id
        tpl_dict['created_by'] = user_id

        tpl = self.tpl_dao.create(session, obj_in=tpl_dict)

        for item_data in items_data:
            item_dict = item_data.model_dump()
            item_dict['workspace_id'] = workspace_id
            item_dict['work_order_template_id'] = tpl.id
            self.item_dao.create(session, obj_in=item_dict)

        if approver_ids:
            self._replace_approvers(session, tpl.id, workspace_id, approver_ids)

        return tpl

    def update_template(
        self, session: Session, tpl_id: int, data: WorkOrderTemplateUpdate,
        workspace_id: int, user_id: int
    ) -> WorkOrderTemplate:
        record = self.tpl_dao.get_by_id_and_workspace(session, id=tpl_id, workspace_id=workspace_id)
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Work order template with ID {tpl_id} not found")

        if data.work_order_type_id is not None:
            wo_type = work_order_type_dao.get_by_id_and_workspace(
                session, id=data.work_order_type_id, workspace_id=workspace_id
            )
            if not wo_type:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Work order type with ID {data.work_order_type_id} not found")

        update_dict = data.model_dump(exclude_unset=True, exclude_none=True, exclude={'approver_user_ids'})
        update_dict['updated_by'] = user_id
        result = self.tpl_dao.update(session, db_obj=record, obj_in=update_dict)

        if 'approver_user_ids' in data.model_fields_set:
            self._replace_approvers(session, tpl_id, workspace_id, data.approver_user_ids or [])

        return result

    def get_template(self, session: Session, tpl_id: int, workspace_id: int) -> WorkOrderTemplate:
        record = self.tpl_dao.get_by_id_and_workspace(session, id=tpl_id, workspace_id=workspace_id)
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Work order template with ID {tpl_id} not found")
        return record

    def list_templates(
        self, session: Session, workspace_id: int,
        is_active: Optional[bool] = None,
        work_order_type_id: Optional[int] = None,
        skip: int = 0, limit: int = 100
    ) -> List[WorkOrderTemplate]:
        return self.tpl_dao.get_by_workspace(
            session, workspace_id=workspace_id,
            is_active=is_active, work_order_type_id=work_order_type_id,
            skip=skip, limit=limit
        )

    def delete_template(self, session: Session, tpl_id: int, workspace_id: int, user_id: int) -> None:
        record = self.tpl_dao.get_by_id_and_workspace(session, id=tpl_id, workspace_id=workspace_id)
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Work order template with ID {tpl_id} not found")
        if not record.is_active:
            return  # Already deactivated — idempotent
        self.tpl_dao.update(session, db_obj=record, obj_in={'is_active': False, 'updated_by': user_id})

    def restore_template(self, session: Session, tpl_id: int, workspace_id: int, user_id: int) -> WorkOrderTemplate:
        record = self.tpl_dao.get_by_id_and_workspace(session, id=tpl_id, workspace_id=workspace_id)
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Work order template with ID {tpl_id} not found")
        return self.tpl_dao.update(session, db_obj=record, obj_in={'is_active': True, 'updated_by': user_id})

    # ─── Template Items ────────────────────────────────────────
    def add_item(
        self, session: Session, tpl_id: int, data: WorkOrderTemplateItemCreate, workspace_id: int
    ) -> WorkOrderTemplateItem:
        tpl = self.tpl_dao.get_by_id_and_workspace(session, id=tpl_id, workspace_id=workspace_id)
        if not tpl:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work order template not found")
        if data.action_type == 'REPLACE' and data.replaced_item_id is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Select the item being replaced')

        item_dict = data.model_dump()
        item_dict['workspace_id'] = workspace_id
        item_dict['work_order_template_id'] = tpl_id
        return self.item_dao.create(session, obj_in=item_dict)

    def update_item(
        self, session: Session, item_id: int, data: WorkOrderTemplateItemUpdate, workspace_id: int
    ) -> WorkOrderTemplateItem:
        record = self.item_dao.get_by_id_and_workspace(session, id=item_id, workspace_id=workspace_id)
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template item not found")
        update_dict = data.model_dump(exclude_unset=True, exclude_none=True)
        return self.item_dao.update(session, db_obj=record, obj_in=update_dict)

    def remove_item(self, session: Session, item_id: int, workspace_id: int) -> WorkOrderTemplateItem:
        record = self.item_dao.get_by_id_and_workspace(session, id=item_id, workspace_id=workspace_id)
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template item not found")
        session.delete(record)
        session.flush()
        return record

    def get_items(self, session: Session, tpl_id: int, workspace_id: int) -> List[WorkOrderTemplateItem]:
        return self.item_dao.get_by_template(session, work_order_template_id=tpl_id, workspace_id=workspace_id)

    def get_approvers(self, session: Session, tpl_id: int, workspace_id: int) -> List[WorkOrderTemplateApprover]:
        return self.approver_dao.get_by_template(session, work_order_template_id=tpl_id, workspace_id=workspace_id)


work_order_template_manager = WorkOrderTemplateManager()
