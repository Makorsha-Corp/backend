"""Workspace shift window business logic."""
from typing import List, Optional

from sqlalchemy.orm import Session

from app.dao.workspace_shift import workspace_shift_dao
from app.managers.base_manager import BaseManager
from app.models.workspace_shift import WorkspaceShift
from app.schemas.workspace_shift import WorkspaceShiftCreate, WorkspaceShiftUpdate
from app.utils.workspace_shift_windows import assert_no_overlap_with_siblings


class WorkspaceShiftManager(BaseManager[WorkspaceShift]):
    def __init__(self):
        super().__init__(WorkspaceShift)
        self.dao = workspace_shift_dao

    def list_shifts(self, session: Session, *, workspace_id: int, active_only: bool = False) -> List[WorkspaceShift]:
        if active_only:
            return self.dao.get_active_by_workspace(session, workspace_id=workspace_id)
        return self.dao.get_all_by_workspace(session, workspace_id=workspace_id)

    def get_shift(self, session: Session, *, shift_id: int, workspace_id: int) -> Optional[WorkspaceShift]:
        return self.dao.get_by_id_and_workspace(session, shift_id=shift_id, workspace_id=workspace_id)

    def create_shift(
        self,
        session: Session,
        *,
        workspace_id: int,
        user_id: int,
        data: WorkspaceShiftCreate,
    ) -> WorkspaceShift:
        siblings = self.dao.get_all_by_workspace(session, workspace_id=workspace_id)
        assert_no_overlap_with_siblings(data.start_time, data.end_time, siblings)
        payload = data.model_dump()
        payload["workspace_id"] = workspace_id
        payload["created_by"] = user_id
        payload["updated_by"] = user_id
        return self.dao.create(session, obj_in=payload)

    def update_shift(
        self,
        session: Session,
        *,
        shift_id: int,
        workspace_id: int,
        user_id: int,
        data: WorkspaceShiftUpdate,
    ) -> WorkspaceShift:
        row = self.dao.get_by_id_and_workspace(session, shift_id=shift_id, workspace_id=workspace_id)
        if not row:
            raise ValueError(f"Shift {shift_id} not found")
        siblings = self.dao.get_all_by_workspace(session, workspace_id=workspace_id)
        start = data.start_time if data.start_time is not None else row.start_time
        end = data.end_time if data.end_time is not None else row.end_time
        will_be_active = data.is_active if data.is_active is not None else row.is_active
        if will_be_active:
            assert_no_overlap_with_siblings(start, end, siblings, exclude_id=shift_id)
        update_dict = data.model_dump(exclude_unset=True)
        update_dict["updated_by"] = user_id
        return self.dao.update(session, db_obj=row, obj_in=update_dict)

    def delete_shift(self, session: Session, *, shift_id: int, workspace_id: int) -> None:
        row = self.dao.get_by_id_and_workspace(session, shift_id=shift_id, workspace_id=workspace_id)
        if not row:
            raise ValueError(f"Shift {shift_id} not found")
        session.delete(row)


workspace_shift_manager = WorkspaceShiftManager()
