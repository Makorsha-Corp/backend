"""DAO operations for AppSettings model

SECURITY NOTICE:
This DAO handles workspace-scoped data. All query methods MUST filter by workspace_id
to prevent unauthorized cross-workspace data access.
"""
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.dao.base import BaseDAO
from app.models.app_settings import AppSettings
from app.schemas.app_settings import AppSettingsCreate, AppSettingsUpdate


class DAOAppSettings(BaseDAO[AppSettings, AppSettingsCreate, AppSettingsUpdate]):
    """DAO operations for AppSettings model (workspace-scoped)"""

    def get_by_name(
        self, db: Session, *, name: str, workspace_id: int
    ) -> Optional[AppSettings]:
        """
        Get settings by name (SECURITY-CRITICAL: workspace-filtered)

        Args:
            db: Database session
            name: Setting name to find
            workspace_id: Workspace ID to filter by

        Returns:
            AppSettings instance or None
        """
        return db.query(AppSettings).filter(
            and_(
                AppSettings.workspace_id == workspace_id,  # SECURITY: workspace isolation
                AppSettings.name == name
            )
        ).first()


app_settings_dao = DAOAppSettings(AppSettings)
