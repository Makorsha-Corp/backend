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

# Singleton instance
project_component_attachment_dao = ProjectComponentAttachmentDAO(ProjectComponentAttachment)
