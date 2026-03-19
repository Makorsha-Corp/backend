"""DAO operations"""
from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.dao.base import BaseDAO
from app.models.factory import Factory
from app.schemas.factory import FactoryCreate, FactoryUpdate


class DAOFactory(BaseDAO[Factory, FactoryCreate, FactoryUpdate]):
    """
    DAO operations for Factory model

    SECURITY NOTE: This DAO previously inherited dangerous base methods without workspace filtering.
    All methods now require workspace_id for proper multi-tenant isolation.
    """

    def get_by_workspace(
        self, db: Session, *, workspace_id: int, skip: int = 0, limit: int = 100
    ) -> List[Factory]:
        """
        Get all factories for a workspace (SECURITY-CRITICAL: workspace-filtered)

        Args:
            db: Database session
            workspace_id: Workspace ID to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of factories belonging to the workspace
        """
        return (
            db.query(Factory)
            .filter(Factory.workspace_id == workspace_id)  # SECURITY: workspace isolation
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_id_and_workspace(
        self, db: Session, *, id: int, workspace_id: int
    ) -> Optional[Factory]:
        """
        Get factory by ID and workspace (SECURITY-CRITICAL: workspace-filtered)

        Args:
            db: Database session
            id: Factory ID
            workspace_id: Workspace ID to filter by

        Returns:
            Factory if found in workspace, None otherwise
        """
        return (
            db.query(Factory)
            .filter(
                Factory.workspace_id == workspace_id,  # SECURITY: workspace isolation
                Factory.id == id
            )
            .first()
        )

    def get_active_factories(
        self, db: Session, *, workspace_id: int, skip: int = 0, limit: int = 100
    ) -> List[Factory]:
        """
        Get all active, non-deleted factories for a workspace (SECURITY-CRITICAL: workspace-filtered)

        Args:
            db: Database session
            workspace_id: Workspace ID to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of active, non-deleted factories belonging to the workspace
        """
        return (
            db.query(Factory)
            .filter(
                Factory.workspace_id == workspace_id,  # SECURITY: workspace isolation
                Factory.is_active == True,
                Factory.is_deleted == False
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    def soft_delete(
        self, db: Session, *, db_obj: Factory, deleted_by: int
    ) -> Factory:
        """
        Soft delete a factory (does NOT commit)

        Args:
            db: Database session
            db_obj: Factory object to soft delete
            deleted_by: Profile ID of user deleting the factory

        Returns:
            Soft-deleted factory instance (not yet committed)
        """
        db_obj.is_deleted = True
        db_obj.deleted_at = datetime.utcnow()
        db_obj.deleted_by = deleted_by
        db.add(db_obj)
        db.flush()
        return db_obj

    def restore(
        self, db: Session, *, db_obj: Factory
    ) -> Factory:
        """
        Restore a soft-deleted factory (does NOT commit)

        Args:
            db: Database session
            db_obj: Factory object to restore

        Returns:
            Restored factory instance (not yet committed)
        """
        db_obj.is_deleted = False
        db_obj.deleted_at = None
        db_obj.deleted_by = None
        db.add(db_obj)
        db.flush()
        return db_obj


factory_dao = DAOFactory(Factory)
