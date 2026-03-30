"""Miscellaneous project cost service for business orchestration"""
from sqlalchemy.orm import Session
from app.dao.miscellaneous_project_cost import miscellaneous_project_cost_dao
from app.schemas.miscellaneous_project_cost import MiscellaneousProjectCostCreate, MiscellaneousProjectCostUpdate


class MiscellaneousProjectCostService:
    """Service for miscellaneous project cost workflows - handles transactions"""

    def get_costs(self, db: Session, workspace_id: int, project_id: int = None, project_component_id: int = None, skip: int = 0, limit: int = 100):
        """Get miscellaneous project costs with optional filtering"""
        if project_id:
            return miscellaneous_project_cost_dao.get_by_project(db, project_id=project_id, workspace_id=workspace_id, skip=skip, limit=limit)
        elif project_component_id:
            return miscellaneous_project_cost_dao.get_by_component(db, project_component_id=project_component_id, workspace_id=workspace_id, skip=skip, limit=limit)
        else:
            return miscellaneous_project_cost_dao.get_by_workspace(db, workspace_id=workspace_id, skip=skip, limit=limit)

    def get_by_id(self, db: Session, cost_id: int, workspace_id: int):
        """Get miscellaneous project cost by ID"""
        return miscellaneous_project_cost_dao.get_by_id_and_workspace(db, id=cost_id, workspace_id=workspace_id)

    def create_cost(self, db: Session, cost_in: MiscellaneousProjectCostCreate, workspace_id: int):
        """Create miscellaneous project cost with transaction management"""
        try:
            cost_dict = cost_in.model_dump()
            cost_dict['workspace_id'] = workspace_id
            cost = miscellaneous_project_cost_dao.create(db, obj_in=cost_dict)
            db.commit()
            db.refresh(cost)
            return cost
        except Exception as e:
            db.rollback()
            raise

    def update_cost(self, db: Session, cost_id: int, cost_in: MiscellaneousProjectCostUpdate, workspace_id: int):
        """Update miscellaneous project cost with transaction management"""
        try:
            cost = miscellaneous_project_cost_dao.get_by_id_and_workspace(
                db, id=cost_id, workspace_id=workspace_id
            )
            if not cost:
                return None
            cost = miscellaneous_project_cost_dao.update(db, db_obj=cost, obj_in=cost_in)
            db.commit()
            db.refresh(cost)
            return cost
        except Exception as e:
            db.rollback()
            raise

    def delete_cost(self, db: Session, cost_id: int, workspace_id: int):
        """Delete miscellaneous project cost with transaction management"""
        try:
            cost = miscellaneous_project_cost_dao.get_by_id_and_workspace(
                db, id=cost_id, workspace_id=workspace_id
            )
            if not cost:
                return False
            miscellaneous_project_cost_dao.remove(db, id=cost_id)
            db.commit()
            return True
        except Exception as e:
            db.rollback()
            raise


miscellaneous_project_cost_service = MiscellaneousProjectCostService()
