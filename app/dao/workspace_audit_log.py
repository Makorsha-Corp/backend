"""WorkspaceAuditLog DAO"""
from typing import List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.dao.base import BaseDAO
from app.models.workspace_audit_log import WorkspaceAuditLog
from app.schemas.workspace_audit_log import WorkspaceAuditLogCreate


class WorkspaceAuditLogDAO(BaseDAO[WorkspaceAuditLog, WorkspaceAuditLogCreate, dict]):
    """DAO for workspace audit log operations"""

    def get_workspace_logs(
        self,
        db: Session,
        *,
        workspace_id: int,
        skip: int = 0,
        limit: int = 100,
        days: int | None = None
    ) -> List[WorkspaceAuditLog]:
        """
        Get audit logs for workspace

        Args:
            workspace_id: Workspace ID
            skip: Number of records to skip
            limit: Maximum number of records to return
            days: Filter logs from last N days
        """
        query = (
            db.query(WorkspaceAuditLog)
            .filter(WorkspaceAuditLog.workspace_id == workspace_id)
            .order_by(WorkspaceAuditLog.created_at.desc())
        )

        if days:
            since = datetime.utcnow() - timedelta(days=days)
            query = query.filter(WorkspaceAuditLog.created_at >= since)

        return query.offset(skip).limit(limit).all()

    def get_user_logs(
        self,
        db: Session,
        *,
        user_id: int,
        workspace_id: int | None = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[WorkspaceAuditLog]:
        """Get audit logs for user"""
        query = (
            db.query(WorkspaceAuditLog)
            .filter(WorkspaceAuditLog.user_id == user_id)
            .order_by(WorkspaceAuditLog.created_at.desc())
        )

        if workspace_id:
            query = query.filter(WorkspaceAuditLog.workspace_id == workspace_id)

        return query.offset(skip).limit(limit).all()

    def get_logs_by_action(
        self,
        db: Session,
        *,
        workspace_id: int,
        action: str,
        skip: int = 0,
        limit: int = 100
    ) -> List[WorkspaceAuditLog]:
        """Get audit logs filtered by action"""
        return (
            db.query(WorkspaceAuditLog)
            .filter(
                WorkspaceAuditLog.workspace_id == workspace_id,
                WorkspaceAuditLog.action == action
            )
            .order_by(WorkspaceAuditLog.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

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
