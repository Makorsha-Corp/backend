"""Project attachment DAO operations

SECURITY NOTICE:
This DAO handles workspace-scoped data. All query methods MUST filter by workspace_id
to prevent unauthorized cross-workspace data access.
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.dao.base import BaseDAO
from app.models.project_attachment import ProjectAttachment
from app.models.attachment import Attachment
from app.schemas.project_attachment import ProjectAttachmentCreate, ProjectAttachmentResponse


class ProjectAttachmentDAO(BaseDAO[ProjectAttachment, ProjectAttachmentCreate, ProjectAttachmentResponse]):
    """DAO for ProjectAttachment junction model (workspace-scoped)"""

    def get_by_project(
        self, db: Session, project_id: int, *, workspace_id: int, include_deleted: bool = False
    ) -> List[Attachment]:
        """
        Get all attachments for a specific project (SECURITY-CRITICAL: workspace-filtered)

        Args:
            db: Database session
            project_id: Project ID
            workspace_id: Workspace ID to filter by
            include_deleted: Whether to include soft-deleted attachments

        Returns:
            List of Attachment instances belonging to the workspace
        """
        query = db.query(Attachment).join(
            ProjectAttachment, ProjectAttachment.attachment_id == Attachment.id
        ).filter(
            ProjectAttachment.workspace_id == workspace_id,  # SECURITY: workspace isolation
            ProjectAttachment.project_id == project_id
        )

        if not include_deleted:
            query = query.filter(Attachment.is_deleted == False)

        return query.all()

    def get_by_attachment(
        self, db: Session, attachment_id: int, *, workspace_id: int
    ) -> List[ProjectAttachment]:
        """
        Get all project links for a specific attachment (SECURITY-CRITICAL: workspace-filtered)

        Args:
            db: Database session
            attachment_id: Attachment ID
            workspace_id: Workspace ID to filter by

        Returns:
            List of ProjectAttachment instances belonging to the workspace
        """
        return db.query(ProjectAttachment).filter(
            ProjectAttachment.workspace_id == workspace_id,  # SECURITY: workspace isolation
            ProjectAttachment.attachment_id == attachment_id
        ).all()

    def get_link(
        self, db: Session, project_id: int, attachment_id: int, *, workspace_id: int
    ) -> Optional[ProjectAttachment]:
        """
        Get a specific project-attachment link (SECURITY-CRITICAL: workspace-filtered)

        Args:
            db: Database session
            project_id: Project ID
            attachment_id: Attachment ID
            workspace_id: Workspace ID to filter by

        Returns:
            ProjectAttachment instance or None
        """
        return db.query(ProjectAttachment).filter(
            and_(
                ProjectAttachment.workspace_id == workspace_id,  # SECURITY: workspace isolation
                ProjectAttachment.project_id == project_id,
                ProjectAttachment.attachment_id == attachment_id
            )
        ).first()

    def link_exists(
        self, db: Session, project_id: int, attachment_id: int, *, workspace_id: int
    ) -> bool:
        """
        Check if an attachment is already linked to a project (SECURITY-CRITICAL: workspace-filtered)

        Args:
            db: Database session
            project_id: Project ID
            attachment_id: Attachment ID
            workspace_id: Workspace ID to filter by

        Returns:
            True if link exists, False otherwise
        """
        return self.get_link(db, project_id, attachment_id, workspace_id=workspace_id) is not None

    def unlink(
        self, db: Session, project_id: int, attachment_id: int, *, workspace_id: int
    ) -> Optional[ProjectAttachment]:
        """
        Remove the link between a project and attachment (does NOT commit) (SECURITY-CRITICAL: workspace-filtered)

        Args:
            db: Database session
            project_id: Project ID
            attachment_id: Attachment ID
            workspace_id: Workspace ID to filter by

        Returns:
            Deleted ProjectAttachment instance or None
        """
        link = self.get_link(db, project_id, attachment_id, workspace_id=workspace_id)
        if not link:
            return None

        db.delete(link)
        db.flush()
        return link

    def get_attachment_count(
        self, db: Session, project_id: int, *, workspace_id: int
    ) -> int:
        """
        Get the count of active attachments for a project (SECURITY-CRITICAL: workspace-filtered)

        Args:
            db: Database session
            project_id: Project ID
            workspace_id: Workspace ID to filter by

        Returns:
            Count of active attachments
        """
        return db.query(ProjectAttachment).join(
            Attachment, ProjectAttachment.attachment_id == Attachment.id
        ).filter(
            and_(
                ProjectAttachment.workspace_id == workspace_id,  # SECURITY: workspace isolation
                ProjectAttachment.project_id == project_id,
                Attachment.is_deleted == False
            )
        ).count()


# Singleton instance
project_attachment_dao = ProjectAttachmentDAO(ProjectAttachment)
