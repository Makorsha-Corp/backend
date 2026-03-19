"""Project component attachment DAO operations

SECURITY NOTICE:
This DAO handles workspace-scoped data. All query methods MUST filter by workspace_id
to prevent unauthorized cross-workspace data access.
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.dao.base import BaseDAO
from app.models.project_component_attachment import ProjectComponentAttachment
from app.models.attachment import Attachment
from app.schemas.project_component_attachment import ProjectComponentAttachmentCreate, ProjectComponentAttachmentResponse


class ProjectComponentAttachmentDAO(BaseDAO[ProjectComponentAttachment, ProjectComponentAttachmentCreate, ProjectComponentAttachmentResponse]):
    """DAO for ProjectComponentAttachment junction model (workspace-scoped)"""

    def get_by_project_component(
        self, db: Session, project_component_id: int, *, workspace_id: int, include_deleted: bool = False
    ) -> List[Attachment]:
        """
        Get all attachments for a specific project component (SECURITY-CRITICAL: workspace-filtered)

        Args:
            db: Database session
            project_component_id: ProjectComponent ID
            workspace_id: Workspace ID to filter by
            include_deleted: Whether to include soft-deleted attachments

        Returns:
            List of Attachment instances belonging to the workspace
        """
        query = db.query(Attachment).join(
            ProjectComponentAttachment,
            ProjectComponentAttachment.attachment_id == Attachment.id
        ).filter(
            ProjectComponentAttachment.workspace_id == workspace_id,  # SECURITY: workspace isolation
            ProjectComponentAttachment.project_component_id == project_component_id
        )

        if not include_deleted:
            query = query.filter(Attachment.is_deleted == False)

        return query.all()

    def get_by_attachment(
        self, db: Session, attachment_id: int, *, workspace_id: int
    ) -> List[ProjectComponentAttachment]:
        """
        Get all project component links for a specific attachment (SECURITY-CRITICAL: workspace-filtered)

        Args:
            db: Database session
            attachment_id: Attachment ID
            workspace_id: Workspace ID to filter by

        Returns:
            List of ProjectComponentAttachment instances belonging to the workspace
        """
        return db.query(ProjectComponentAttachment).filter(
            ProjectComponentAttachment.workspace_id == workspace_id,  # SECURITY: workspace isolation
            ProjectComponentAttachment.attachment_id == attachment_id
        ).all()

    def get_link(
        self, db: Session, project_component_id: int, attachment_id: int, *, workspace_id: int
    ) -> Optional[ProjectComponentAttachment]:
        """
        Get a specific project component-attachment link (SECURITY-CRITICAL: workspace-filtered)

        Args:
            db: Database session
            project_component_id: ProjectComponent ID
            attachment_id: Attachment ID
            workspace_id: Workspace ID to filter by

        Returns:
            ProjectComponentAttachment instance or None
        """
        return db.query(ProjectComponentAttachment).filter(
            and_(
                ProjectComponentAttachment.workspace_id == workspace_id,  # SECURITY: workspace isolation
                ProjectComponentAttachment.project_component_id == project_component_id,
                ProjectComponentAttachment.attachment_id == attachment_id
            )
        ).first()

    def link_exists(
        self, db: Session, project_component_id: int, attachment_id: int, *, workspace_id: int
    ) -> bool:
        """
        Check if an attachment is already linked to a project component (SECURITY-CRITICAL: workspace-filtered)

        Args:
            db: Database session
            project_component_id: ProjectComponent ID
            attachment_id: Attachment ID
            workspace_id: Workspace ID to filter by

        Returns:
            True if link exists, False otherwise
        """
        return self.get_link(db, project_component_id, attachment_id, workspace_id=workspace_id) is not None

    def unlink(
        self, db: Session, project_component_id: int, attachment_id: int, *, workspace_id: int
    ) -> Optional[ProjectComponentAttachment]:
        """
        Remove the link between a project component and attachment (does NOT commit) (SECURITY-CRITICAL: workspace-filtered)

        Args:
            db: Database session
            project_component_id: ProjectComponent ID
            attachment_id: Attachment ID
            workspace_id: Workspace ID to filter by

        Returns:
            Deleted ProjectComponentAttachment instance or None
        """
        link = self.get_link(db, project_component_id, attachment_id, workspace_id=workspace_id)
        if not link:
            return None

        db.delete(link)
        db.flush()
        return link

    def get_attachment_count(
        self, db: Session, project_component_id: int, *, workspace_id: int
    ) -> int:
        """
        Get the count of active attachments for a project component (SECURITY-CRITICAL: workspace-filtered)

        Args:
            db: Database session
            project_component_id: ProjectComponent ID
            workspace_id: Workspace ID to filter by

        Returns:
            Count of active attachments
        """
        return db.query(ProjectComponentAttachment).join(
            Attachment, ProjectComponentAttachment.attachment_id == Attachment.id
        ).filter(
            and_(
                ProjectComponentAttachment.workspace_id == workspace_id,  # SECURITY: workspace isolation
                ProjectComponentAttachment.project_component_id == project_component_id,
                Attachment.is_deleted == False
            )
        ).count()


# Singleton instance
project_component_attachment_dao = ProjectComponentAttachmentDAO(ProjectComponentAttachment)
