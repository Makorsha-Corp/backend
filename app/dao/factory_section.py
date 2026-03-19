"""DAO operations for FactorySection model

SECURITY NOTICE:
This DAO handles workspace-scoped data. All query methods MUST filter by workspace_id
to prevent unauthorized cross-workspace data access.
"""
from typing import List
from datetime import datetime
from sqlalchemy.orm import Session
from app.dao.base import BaseDAO
from app.models.factory_section import FactorySection
from app.schemas.factory_section import FactorySectionCreate, FactorySectionUpdate


class DAOFactorySection(BaseDAO[FactorySection, FactorySectionCreate, FactorySectionUpdate]):
    """DAO operations for FactorySection model (workspace-scoped)"""

    def get_by_factory(
        self, db: Session, *, factory_id: int, workspace_id: int, skip: int = 0, limit: int = 100
    ) -> List[FactorySection]:
        """
        Get factory sections by factory ID (SECURITY-CRITICAL: workspace-filtered)

        Args:
            db: Database session
            factory_id: Factory ID to filter by
            workspace_id: Workspace ID to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of factory sections belonging to the workspace
        """
        return (
            db.query(FactorySection)
            .filter(
                FactorySection.workspace_id == workspace_id,  # SECURITY: workspace isolation
                FactorySection.factory_id == factory_id
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    def soft_delete(
        self, db: Session, *, db_obj: FactorySection, deleted_by: int
    ) -> FactorySection:
        """
        Soft delete a factory section (does NOT commit)

        Args:
            db: Database session
            db_obj: FactorySection object to soft delete
            deleted_by: Profile ID of user deleting the section

        Returns:
            Soft-deleted factory section instance (not yet committed)
        """
        db_obj.is_deleted = True
        db_obj.deleted_at = datetime.utcnow()
        db_obj.deleted_by = deleted_by
        db.add(db_obj)
        db.flush()
        return db_obj

    def restore(
        self, db: Session, *, db_obj: FactorySection
    ) -> FactorySection:
        """
        Restore a soft-deleted factory section (does NOT commit)

        Args:
            db: Database session
            db_obj: FactorySection object to restore

        Returns:
            Restored factory section instance (not yet committed)
        """
        db_obj.is_deleted = False
        db_obj.deleted_at = None
        db_obj.deleted_by = None
        db.add(db_obj)
        db.flush()
        return db_obj


factory_section_dao = DAOFactorySection(FactorySection)
