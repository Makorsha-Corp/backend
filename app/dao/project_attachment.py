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

# Singleton instance
project_attachment_dao = ProjectAttachmentDAO(ProjectAttachment)
