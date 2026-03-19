"""Attachment DAO operations

SECURITY NOTICE:
This DAO handles workspace-scoped data. All query methods MUST filter by workspace_id
to prevent unauthorized cross-workspace data access.
"""
from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.dao.base import BaseDAO
from app.models.attachment import Attachment
from app.schemas.attachment import AttachmentCreate, AttachmentUpdate


class AttachmentDAO(BaseDAO[Attachment, AttachmentCreate, AttachmentUpdate]):
    """DAO for Attachment model (workspace-scoped)"""

    def get_active(
        self, db: Session, id: int, workspace_id: int
    ) -> Optional[Attachment]:
        """
        Get a single non-deleted attachment by ID (SECURITY-CRITICAL: workspace-filtered)

        Args:
            db: Database session
            id: Attachment ID
            workspace_id: Workspace ID to filter by

        Returns:
            Attachment instance or None
        """
        return db.query(Attachment).filter(
            and_(
                Attachment.workspace_id == workspace_id,  # SECURITY: workspace isolation
                Attachment.id == id,
                Attachment.is_deleted == False
            )
        ).first()

    def get_multi_active(
        self, db: Session, *, workspace_id: int, skip: int = 0, limit: int = 100
    ) -> List[Attachment]:
        """
        Get multiple non-deleted attachments with pagination (SECURITY-CRITICAL: workspace-filtered)

        Args:
            db: Database session
            workspace_id: Workspace ID to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of attachment instances belonging to the workspace
        """
        return db.query(Attachment).filter(
            and_(
                Attachment.workspace_id == workspace_id,  # SECURITY: workspace isolation
                Attachment.is_deleted == False
            )
        ).offset(skip).limit(limit).all()

    def get_by_uploader(
        self, db: Session, uploader_id: int, *, workspace_id: int, skip: int = 0, limit: int = 100
    ) -> List[Attachment]:
        """
        Get attachments uploaded by a specific user (SECURITY-CRITICAL: workspace-filtered)

        Args:
            db: Database session
            uploader_id: Profile ID of uploader
            workspace_id: Workspace ID to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of attachment instances belonging to the workspace
        """
        return db.query(Attachment).filter(
            and_(
                Attachment.workspace_id == workspace_id,  # SECURITY: workspace isolation
                Attachment.uploaded_by == uploader_id,
                Attachment.is_deleted == False
            )
        ).offset(skip).limit(limit).all()

    def soft_delete(
        self, db: Session, *, id: int, workspace_id: int, deleted_by: int
    ) -> Optional[Attachment]:
        """
        Soft delete an attachment (does NOT commit) (SECURITY-CRITICAL: workspace-filtered)

        Args:
            db: Database session
            id: Attachment ID
            workspace_id: Workspace ID to filter by
            deleted_by: Profile ID of user deleting the attachment

        Returns:
            Soft-deleted attachment instance (not yet committed)
        """
        # Use workspace-filtered get
        attachment = db.query(Attachment).filter(
            and_(
                Attachment.workspace_id == workspace_id,  # SECURITY: workspace isolation
                Attachment.id == id
            )
        ).first()

        if not attachment:
            return None

        attachment.is_deleted = True
        attachment.deleted_at = datetime.utcnow()
        attachment.deleted_by = deleted_by

        db.add(attachment)
        db.flush()
        return attachment

    def restore(
        self, db: Session, *, id: int, workspace_id: int
    ) -> Optional[Attachment]:
        """
        Restore a soft-deleted attachment (does NOT commit) (SECURITY-CRITICAL: workspace-filtered)

        Args:
            db: Database session
            id: Attachment ID
            workspace_id: Workspace ID to filter by

        Returns:
            Restored attachment instance (not yet committed)
        """
        # Use workspace-filtered get
        attachment = db.query(Attachment).filter(
            and_(
                Attachment.workspace_id == workspace_id,  # SECURITY: workspace isolation
                Attachment.id == id
            )
        ).first()

        if not attachment:
            return None

        attachment.is_deleted = False
        attachment.deleted_at = None
        attachment.deleted_by = None

        db.add(attachment)
        db.flush()
        return attachment


# Singleton instance
attachment_dao = AttachmentDAO(Attachment)
