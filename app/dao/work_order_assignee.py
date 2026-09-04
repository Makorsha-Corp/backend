"""Work order assignee DAO."""
from typing import Dict, List

from sqlalchemy.orm import Session

from app.dao.base import BaseDAO
from app.models.work_order_assignee import WorkOrderAssignee


class WorkOrderAssigneeDAO(BaseDAO[WorkOrderAssignee, object, object]):
    def get_user_ids_by_orders(
        self,
        db: Session,
        *,
        work_order_ids: List[int],
        workspace_id: int,
    ) -> Dict[int, List[int]]:
        if not work_order_ids:
            return {}
        result: Dict[int, List[int]] = {wo_id: [] for wo_id in work_order_ids}
        rows = (
            db.query(WorkOrderAssignee)
            .filter(
                WorkOrderAssignee.work_order_id.in_(work_order_ids),
                WorkOrderAssignee.workspace_id == workspace_id,
            )
            .order_by(WorkOrderAssignee.id)
            .all()
        )
        for row in rows:
            result.setdefault(row.work_order_id, []).append(row.user_id)
        return result

    def get_user_ids_by_order(
        self, db: Session, *, work_order_id: int, workspace_id: int,
    ) -> List[int]:
        rows = (
            db.query(WorkOrderAssignee)
            .filter(
                WorkOrderAssignee.work_order_id == work_order_id,
                WorkOrderAssignee.workspace_id == workspace_id,
            )
            .order_by(WorkOrderAssignee.id)
            .all()
        )
        return [row.user_id for row in rows]

    def replace_for_order(
        self, db: Session, *, work_order_id: int, workspace_id: int, user_ids: List[int],
    ) -> None:
        (
            db.query(WorkOrderAssignee)
            .filter(
                WorkOrderAssignee.work_order_id == work_order_id,
                WorkOrderAssignee.workspace_id == workspace_id,
            )
            .delete(synchronize_session=False)
        )
        seen: set[int] = set()
        for user_id in user_ids:
            if user_id in seen:
                continue
            seen.add(user_id)
            db.add(
                WorkOrderAssignee(
                    workspace_id=workspace_id,
                    work_order_id=work_order_id,
                    user_id=user_id,
                )
            )
        db.flush()


work_order_assignee_dao = WorkOrderAssigneeDAO(WorkOrderAssignee)
