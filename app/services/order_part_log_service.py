"""Order part log service for business orchestration"""
from sqlalchemy.orm import Session
from app.dao.order_part_log import order_part_log_dao
from app.schemas.order_part_log import OrderPartLogCreate


class OrderPartLogService:
    """Service for order part log workflows - handles transactions"""

    def get_logs(self, db: Session, workspace_id: int, order_part_id: int = None, skip: int = 0, limit: int = 100):
        """Get order part logs with optional filtering"""
        if order_part_id:
            return order_part_log_dao.get_by_order_part(db, order_part_id=order_part_id, workspace_id=workspace_id, skip=skip, limit=limit)
        else:
            return order_part_log_dao.get_by_workspace(db, workspace_id=workspace_id, skip=skip, limit=limit)

    def get_by_id(self, db: Session, log_id: int, workspace_id: int):
        """Get order part log by ID"""
        return order_part_log_dao.get_by_id_and_workspace(db, id=log_id, workspace_id=workspace_id)

    def create_log(self, db: Session, log_in: OrderPartLogCreate, workspace_id: int):
        """Create order part log with transaction management"""
        try:
            log_dict = log_in.model_dump()
            log_dict['workspace_id'] = workspace_id
            log = order_part_log_dao.create(db, obj_in=log_dict)
            db.commit()
            db.refresh(log)
            return log
        except Exception:
            db.rollback()
            raise


order_part_log_service = OrderPartLogService()
