"""App settings service for business orchestration"""
from sqlalchemy.orm import Session
from app.dao.app_settings import app_settings_dao
from app.schemas.app_settings import AppSettingsCreate, AppSettingsUpdate


class AppSettingsService:
    """Service for app settings workflows - handles transactions"""

    def get_settings(self, db: Session, workspace_id: int, skip: int = 0, limit: int = 100):
        """Get all app settings"""
        return app_settings_dao.get_by_workspace(db, workspace_id=workspace_id, skip=skip, limit=limit)

    def get_by_id(self, db: Session, setting_id: int, workspace_id: int):
        """Get app setting by ID"""
        return app_settings_dao.get_by_id_and_workspace(db, id=setting_id, workspace_id=workspace_id)

    def get_by_name(self, db: Session, name: str, workspace_id: int):
        """Get app setting by name"""
        return app_settings_dao.get_by_name(db, name=name, workspace_id=workspace_id)

    def create_setting(self, db: Session, setting_in: AppSettingsCreate, workspace_id: int):
        """Create app setting with transaction management"""
        try:
            setting_dict = setting_in.model_dump()
            setting_dict['workspace_id'] = workspace_id
            setting = app_settings_dao.create(db, obj_in=setting_dict)
            db.commit()
            db.refresh(setting)
            return setting
        except Exception:
            db.rollback()
            raise

    def update_setting(self, db: Session, setting_id: int, setting_in: AppSettingsUpdate, workspace_id: int):
        """Update app setting with transaction management"""
        try:
            setting = app_settings_dao.get_by_id_and_workspace(db, id=setting_id, workspace_id=workspace_id)
            if not setting:
                return None
            setting = app_settings_dao.update(db, db_obj=setting, obj_in=setting_in)
            db.commit()
            db.refresh(setting)
            return setting
        except Exception:
            db.rollback()
            raise

    def delete_setting(self, db: Session, setting_id: int, workspace_id: int):
        """Delete app setting with transaction management"""
        try:
            setting = app_settings_dao.get_by_id_and_workspace(db, id=setting_id, workspace_id=workspace_id)
            if not setting:
                return False
            app_settings_dao.remove(db, id=setting_id)
            db.commit()
            return True
        except Exception:
            db.rollback()
            raise


app_settings_service = AppSettingsService()
