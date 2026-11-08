"""DAO for workspace shift windows."""
from typing import List, Optional

from sqlalchemy.orm import Session

from app.dao.base import BaseDAO
from app.models.workspace_shift import WorkspaceShift
from app.schemas.workspace_shift import WorkspaceShiftCreate, WorkspaceShiftUpdate


class WorkspaceShiftDAO(BaseDAO[WorkspaceShift, WorkspaceShiftCreate, WorkspaceShiftUpdate]):
    def get_active_by_workspace(
        self,
        db: Session,
        *,
        workspace_id: int,
    ) -> List[WorkspaceShift]:
        return (
            db.query(self.model)
            .filter(
                self.model.workspace_id == workspace_id,
                self.model.is_active.is_(True),
            )
            .order_by(self.model.sort_order.asc(), self.model.id.asc())
            .all()
        )

    def get_all_by_workspace(
        self,
        db: Session,
        *,
        workspace_id: int,
    ) -> List[WorkspaceShift]:
        return (
            db.query(self.model)
            .filter(self.model.workspace_id == workspace_id)
            .order_by(self.model.sort_order.asc(), self.model.id.asc())
            .all()
        )

    def get_by_id_and_workspace(
        self,
        db: Session,
        *,
        shift_id: int,
        workspace_id: int,
    ) -> Optional[WorkspaceShift]:
        return (
            db.query(self.model)
            .filter(self.model.id == shift_id, self.model.workspace_id == workspace_id)
            .first()
        )


workspace_shift_dao = WorkspaceShiftDAO(WorkspaceShift)
