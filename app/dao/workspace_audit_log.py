"""WorkspaceAuditLog DAO"""
from typing import List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.dao.base import BaseDAO
from app.models.workspace_audit_log import WorkspaceAuditLog
from app.schemas.workspace_audit_log import WorkspaceAuditLogCreate
from app.utils.time import utcnow


class WorkspaceAuditLogDAO(BaseDAO[WorkspaceAuditLog, WorkspaceAuditLogCreate, dict]):
    """DAO for workspace audit log operations"""

    def log_action(
        self,
        db: Session,
        *,
        workspace_id: int | None,
        user_id: int | None,
        action: str,
        resource_type: str | None = None,
        resource_id: int | None = None,
        metadata: dict | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None
    ) -> WorkspaceAuditLog:
        """
        Create audit log entry (convenience method)

        Args:
            workspace_id: Workspace ID
            user_id: User ID
            action: Action name (e.g., 'member_added', 'role_changed')
            resource_type: Resource type (e.g., 'member', 'order')
            resource_id: Resource ID
            metadata: Additional context data
            ip_address: Request IP address
            user_agent: Request user agent
        """
        log_entry = WorkspaceAuditLog(
            workspace_id=workspace_id,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            metadata_json=metadata,
            ip_address=ip_address,
            user_agent=user_agent
        )
        db.add(log_entry)
        db.flush()
        return log_entry


workspace_audit_log_dao = WorkspaceAuditLogDAO(WorkspaceAuditLog)
