"""Order workflow service for business orchestration"""
from sqlalchemy.orm import Session
from app.dao.order_workflow import order_workflow_dao
from app.schemas.order_workflow import OrderWorkflowCreate, OrderWorkflowUpdate


class OrderWorkflowService:
    """Service for order workflow workflows - handles transactions"""

    def get_workflows(self, db: Session, workspace_id: int, skip: int = 0, limit: int = 100):
        """Get all order workflows"""
        return order_workflow_dao.get_by_workspace(db, workspace_id=workspace_id, skip=skip, limit=limit)

    def get_by_id(self, db: Session, workflow_id: int, workspace_id: int):
        """Get order workflow by ID"""
        return order_workflow_dao.get_by_id_and_workspace(db, id=workflow_id, workspace_id=workspace_id)

    def get_by_type(self, db: Session, workflow_type: str, workspace_id: int):
        """Get order workflow by type"""
        return order_workflow_dao.get_by_type(db, workflow_type=workflow_type, workspace_id=workspace_id)

    def create_workflow(self, db: Session, workflow_in: OrderWorkflowCreate, workspace_id: int):
        """Create order workflow with transaction management"""
        try:
            workflow_dict = workflow_in.model_dump()
            workflow_dict['workspace_id'] = workspace_id
            workflow = order_workflow_dao.create(db, obj_in=workflow_dict)
            db.commit()
            db.refresh(workflow)
            return workflow
        except Exception:
            db.rollback()
            raise

    def update_workflow(self, db: Session, workflow_id: int, workflow_in: OrderWorkflowUpdate, workspace_id: int):
        """Update order workflow with transaction management"""
        try:
            workflow = order_workflow_dao.get_by_id_and_workspace(db, id=workflow_id, workspace_id=workspace_id)
            if not workflow:
                return None
            workflow = order_workflow_dao.update(db, db_obj=workflow, obj_in=workflow_in)
            db.commit()
            db.refresh(workflow)
            return workflow
        except Exception:
            db.rollback()
            raise

    def delete_workflow(self, db: Session, workflow_id: int, workspace_id: int):
        """Delete order workflow with transaction management"""
        try:
            workflow = order_workflow_dao.get_by_id_and_workspace(db, id=workflow_id, workspace_id=workspace_id)
            if not workflow:
                return False
            order_workflow_dao.remove(db, id=workflow_id)
            db.commit()
            return True
        except Exception:
            db.rollback()
            raise


order_workflow_service = OrderWorkflowService()
