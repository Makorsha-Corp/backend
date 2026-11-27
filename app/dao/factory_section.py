"""DAO operations for FactorySection model

SECURITY NOTICE:
This DAO handles workspace-scoped data. All query methods MUST filter by workspace_id
to prevent unauthorized cross-workspace data access.
"""

from sqlalchemy import exists, func
from sqlalchemy.orm import Session

from app.dao.base import BaseDAO
from app.models.factory import Factory
from app.models.factory_section import FactorySection
from app.schemas.factory_section import FactorySectionCreate, FactorySectionUpdate
from app.utils.time import utcnow


class DAOFactorySection(BaseDAO[FactorySection, FactorySectionCreate, FactorySectionUpdate]):
    """DAO operations for FactorySection model (workspace-scoped)"""

    def get_by_factory(
        self, db: Session, *, factory_id: int, workspace_id: int, skip: int = 0, limit: int = 100,
        include_deleted: bool = False
    ) -> list[FactorySection]:
        """
        Get factory sections by factory ID (SECURITY-CRITICAL: workspace-filtered)

        Args:
            db: Database session
            factory_id: Factory ID to filter by
            workspace_id: Workspace ID to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return
            include_deleted: Also return soft-deleted sections and sections of a
                soft-deleted factory

        Returns:
            List of factory sections belonging to the workspace
        """
        query = db.query(FactorySection).filter(
            FactorySection.workspace_id == workspace_id,  # SECURITY: workspace isolation
            FactorySection.factory_id == factory_id
        )
        if not include_deleted:
            # BUG-905: hide soft-deleted sections.
            # BUG-904: hide sections of a soft-deleted factory (only the factory's
            # is_deleted is read; its workspace_id / is_active are not compared).
            query = query.filter(
                FactorySection.is_deleted == False,
                exists().where(
                    Factory.id == FactorySection.factory_id,
                    Factory.is_deleted == False,
                ),
            )
        # BUG-903: stable order before paging (HR-6).
        return (
            query.order_by(func.lower(FactorySection.name).asc(), FactorySection.id.asc())
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
        db_obj.deleted_at = utcnow()
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
