"""Work order program DAO."""
from typing import List, Optional

from sqlalchemy.orm import Session

from app.dao.base import BaseDAO
from app.models.work_order_program import WorkOrderProgram
from app.schemas.work_order_program import WorkOrderProgramCreate


class WorkOrderProgramDAO(
    BaseDAO[WorkOrderProgram, WorkOrderProgramCreate, WorkOrderProgramCreate]
):
    def get_by_id_and_workspace(
        self, db: Session, *, id: int, workspace_id: int
    ) -> Optional[WorkOrderProgram]:
        return (
            db.query(WorkOrderProgram)
            .filter(
                WorkOrderProgram.id == id,
                WorkOrderProgram.workspace_id == workspace_id,
            )
            .first()
        )

    def get_by_factory(
        self, db: Session, *, factory_id: int, workspace_id: int
    ) -> List[WorkOrderProgram]:
        return (
            db.query(WorkOrderProgram)
            .filter(
                WorkOrderProgram.workspace_id == workspace_id,
                WorkOrderProgram.factory_id == factory_id,
            )
            .order_by(
                WorkOrderProgram.created_at.desc(),
                WorkOrderProgram.id.desc(),
            )
            .all()
        )


work_order_program_dao = WorkOrderProgramDAO(WorkOrderProgram)
