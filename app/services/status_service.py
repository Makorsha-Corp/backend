"""Status service for business orchestration"""
from sqlalchemy.orm import Session
from app.dao.status import status_dao
from app.schemas.status import StatusCreate, StatusUpdate


class StatusService:
    """Service for status workflows - handles transactions"""

    def get_statuses(self, db: Session, skip: int = 0, limit: int = 100):
        """Get all statuses"""
        return status_dao.get_multi(db, skip=skip, limit=limit)

    def get_by_id(self, db: Session, status_id: int):
        """Get status by ID"""
        return status_dao.get(db, id=status_id)

    def create_status(self, db: Session, status_in: StatusCreate):
        """Create status with transaction management"""
        try:
            status = status_dao.create(db, obj_in=status_in)
            db.commit()
            db.refresh(status)
            return status
        except Exception:
            db.rollback()
            raise

    def update_status(self, db: Session, status_id: int, status_in: StatusUpdate):
        """Update status with transaction management"""
        try:
            status = status_dao.get(db, id=status_id)
            if not status:
                return None
            status = status_dao.update(db, db_obj=status, obj_in=status_in)
            db.commit()
            db.refresh(status)
            return status
        except Exception:
            db.rollback()
            raise

    def delete_status(self, db: Session, status_id: int):
        """Delete status with transaction management"""
        try:
            status = status_dao.get(db, id=status_id)
            if not status:
                return False
            status_dao.remove(db, id=status_id)
            db.commit()
            return True
        except Exception:
            db.rollback()
            raise


status_service = StatusService()
