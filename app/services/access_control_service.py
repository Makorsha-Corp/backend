"""Access control service for business orchestration"""
from sqlalchemy.orm import Session
from app.dao.access_control import access_control_dao
from app.schemas.access_control import AccessControlCreate, AccessControlUpdate
from app.models.enums import RoleEnum, AccessControlTypeEnum


class AccessControlService:
    """Service for access control workflows - handles transactions"""

    def get_controls(self, db: Session, workspace_id: int, role: RoleEnum = None, access_type: AccessControlTypeEnum = None, skip: int = 0, limit: int = 100):
        """Get access controls with optional filtering"""
        if role:
            return access_control_dao.get_by_role(db, role=role, workspace_id=workspace_id, skip=skip, limit=limit)
        elif access_type:
            return access_control_dao.get_by_type(db, access_type=access_type, workspace_id=workspace_id, skip=skip, limit=limit)
        else:
            return access_control_dao.get_by_workspace(db, workspace_id=workspace_id, skip=skip, limit=limit)

    def get_by_id(self, db: Session, control_id: int, workspace_id: int):
        """Get access control by ID"""
        return access_control_dao.get_by_id_and_workspace(db, id=control_id, workspace_id=workspace_id)

    def create_control(self, db: Session, control_in: AccessControlCreate, workspace_id: int):
        """Create access control with transaction management"""
        try:
            control_dict = control_in.model_dump()
            control_dict['workspace_id'] = workspace_id
            control = access_control_dao.create(db, obj_in=control_dict)
            db.commit()
            db.refresh(control)
            return control
        except Exception:
            db.rollback()
            raise

    def update_control(self, db: Session, control_id: int, control_in: AccessControlUpdate, workspace_id: int):
        """Update access control with transaction management"""
        try:
            control = access_control_dao.get_by_id_and_workspace(db, id=control_id, workspace_id=workspace_id)
            if not control:
                return None
            control = access_control_dao.update(db, db_obj=control, obj_in=control_in)
            db.commit()
            db.refresh(control)
            return control
        except Exception:
            db.rollback()
            raise

    def delete_control(self, db: Session, control_id: int, workspace_id: int):
        """Delete access control with transaction management"""
        try:
            control = access_control_dao.get_by_id_and_workspace(db, id=control_id, workspace_id=workspace_id)
            if not control:
                return False
            access_control_dao.remove(db, id=control_id)
            db.commit()
            return True
        except Exception:
            db.rollback()
            raise


access_control_service = AccessControlService()
