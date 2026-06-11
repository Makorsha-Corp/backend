"""Miscellaneous project cost service for business orchestration"""
from sqlalchemy.orm import Session
from app.dao.miscellaneous_project_cost import miscellaneous_project_cost_dao
from app.dao.project_component import project_component_dao
from app.managers.project_manager import project_manager
from app.schemas.miscellaneous_project_cost import (
    MiscellaneousProjectCostCreate,
    MiscellaneousProjectCostUpdate,
)


class MiscellaneousProjectCostService:
    """Service for miscellaneous project cost workflows - handles transactions"""

    def _log_cost_activity(
        self,
        db: Session,
        cost,
        workspace_id: int,
        user_id: int,
        event_type: str,
        description: str,
    ) -> None:
        metadata = {'cost_id': cost.id, 'cost_name': cost.name}
        if cost.project_component_id:
            project_manager.log_for_component(
                db,
                cost.project_component_id,
                workspace_id,
                event_type,
                description,
                user_id,
                metadata=metadata,
            )
            return
        if cost.project_id:
            metadata['component_id'] = None
            project_manager.log_event(
                db,
                cost.project_id,
                workspace_id,
                event_type,
                description,
                user_id,
                metadata=metadata,
            )

    def _filter_accessible_costs(self, db: Session, costs, workspace_id: int, user_id: int):
        accessible = []
        for cost in costs:
            project_id = cost.project_id
            if not project_id and cost.project_component_id:
                component = project_component_dao.get_by_id_and_workspace(
                    db, id=cost.project_component_id, workspace_id=workspace_id
                )
                project_id = component.project_id if component else None
            if not project_id:
                continue
            project = project_manager.project_dao.get_by_id_and_workspace(
                db, id=project_id, workspace_id=workspace_id
            )
            if project and project_manager.can_access_project(
                db, project, user_id, workspace_id
            ):
                accessible.append(cost)
        return accessible

    def get_costs(
        self,
        db: Session,
        workspace_id: int,
        user_id: int,
        project_id: int = None,
        project_component_id: int = None,
        skip: int = 0,
        limit: int = 100,
    ):
        if project_id:
            project_manager.require_project_access(
                db, project_id, workspace_id, user_id
            )
            return miscellaneous_project_cost_dao.get_by_project(
                db,
                project_id=project_id,
                workspace_id=workspace_id,
                skip=skip,
                limit=limit,
            )
        if project_component_id:
            project_manager.require_component_access(
                db, project_component_id, workspace_id, user_id
            )
            return miscellaneous_project_cost_dao.get_by_component(
                db,
                project_component_id=project_component_id,
                workspace_id=workspace_id,
                skip=skip,
                limit=limit,
            )

        all_costs = miscellaneous_project_cost_dao.get_by_workspace(
            db, workspace_id=workspace_id, skip=skip, limit=limit
        )
        return self._filter_accessible_costs(db, all_costs, workspace_id, user_id)

    def get_by_id(self, db: Session, cost_id: int, workspace_id: int, user_id: int):
        cost = miscellaneous_project_cost_dao.get_by_id_and_workspace(
            db, id=cost_id, workspace_id=workspace_id
        )
        if not cost:
            return None
        project_id = cost.project_id
        if not project_id and cost.project_component_id:
            component = project_component_dao.get_by_id_and_workspace(
                db, id=cost.project_component_id, workspace_id=workspace_id
            )
            project_id = component.project_id if component else None
        if project_id:
            project_manager.require_project_access(
                db, project_id, workspace_id, user_id
            )
        return cost

    def create_cost(
        self,
        db: Session,
        cost_in: MiscellaneousProjectCostCreate,
        workspace_id: int,
        user_id: int,
    ):
        try:
            if cost_in.project_id:
                project_manager.require_project_access(
                    db, cost_in.project_id, workspace_id, user_id
                )
            elif cost_in.project_component_id:
                project_manager.require_component_access(
                    db, cost_in.project_component_id, workspace_id, user_id
                )
            cost_dict = cost_in.model_dump()
            cost_dict['workspace_id'] = workspace_id
            cost = miscellaneous_project_cost_dao.create(db, obj_in=cost_dict)
            self._log_cost_activity(
                db,
                cost,
                workspace_id,
                user_id,
                'cost_added',
                f'Added cost "{cost.name}"',
            )
            db.commit()
            db.refresh(cost)
            return cost
        except Exception:
            db.rollback()
            raise

    def update_cost(
        self,
        db: Session,
        cost_id: int,
        cost_in: MiscellaneousProjectCostUpdate,
        workspace_id: int,
        user_id: int,
    ):
        try:
            cost = self.get_by_id(db, cost_id, workspace_id, user_id)
            if not cost:
                return None
            cost = miscellaneous_project_cost_dao.update(db, db_obj=cost, obj_in=cost_in)
            self._log_cost_activity(
                db,
                cost,
                workspace_id,
                user_id,
                'cost_updated',
                f'Updated cost "{cost.name}"',
            )
            db.commit()
            db.refresh(cost)
            return cost
        except Exception:
            db.rollback()
            raise

    def delete_cost(self, db: Session, cost_id: int, workspace_id: int, user_id: int):
        try:
            cost = self.get_by_id(db, cost_id, workspace_id, user_id)
            if not cost:
                return False
            self._log_cost_activity(
                db,
                cost,
                workspace_id,
                user_id,
                'cost_deleted',
                f'Deleted cost "{cost.name}"',
            )
            miscellaneous_project_cost_dao.remove(db, id=cost_id)
            db.commit()
            return True
        except Exception:
            db.rollback()
            raise


miscellaneous_project_cost_service = MiscellaneousProjectCostService()
