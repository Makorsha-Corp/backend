"""Financial audit log DAO operations"""
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from typing import List, Optional
from datetime import datetime
from app.dao.base import BaseDAO
from app.models.financial_audit_log import FinancialAuditLog
from pydantic import BaseModel


class FinancialAuditLogCreate(BaseModel):
    """Schema for creating audit log entries"""
    entity_type: str
    entity_id: int
    action_type: str
    related_entity_type: Optional[str] = None
    related_entity_id: Optional[int] = None
    changes: Optional[dict] = None
    description: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


class FinancialAuditLogDAO(BaseDAO[FinancialAuditLog, FinancialAuditLogCreate, BaseModel]):
    """DAO operations for FinancialAuditLog model"""

    def get_by_entity(
        self,
        db: Session,
        *,
        entity_type: str,
        entity_id: int,
        workspace_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[FinancialAuditLog]:
        """
        Get all audit logs for a specific entity (SECURITY-CRITICAL)

        Args:
            db: Database session
            entity_type: Type of entity ('account', 'invoice', 'payment')
            entity_id: Entity ID
            workspace_id: Workspace ID to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of audit logs for the entity
        """
        return (
            db.query(FinancialAuditLog)
            .filter(
                FinancialAuditLog.workspace_id == workspace_id,
                FinancialAuditLog.entity_type == entity_type,
                FinancialAuditLog.entity_id == entity_id
            )
            .order_by(FinancialAuditLog.performed_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_related_logs(
        self,
        db: Session,
        *,
        entity_type: str,
        entity_id: int,
        workspace_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[FinancialAuditLog]:
        """
        Get all audit logs related to an entity (direct and related) (SECURITY-CRITICAL)

        For example, for an account, this returns logs for:
        - The account itself
        - All invoices for that account
        - All payments for those invoices

        Args:
            db: Database session
            entity_type: Type of entity ('account', 'invoice', 'payment')
            entity_id: Entity ID
            workspace_id: Workspace ID to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of all related audit logs
        """
        return (
            db.query(FinancialAuditLog)
            .filter(
                FinancialAuditLog.workspace_id == workspace_id,
                or_(
                    and_(
                        FinancialAuditLog.entity_type == entity_type,
                        FinancialAuditLog.entity_id == entity_id
                    ),
                    and_(
                        FinancialAuditLog.related_entity_type == entity_type,
                        FinancialAuditLog.related_entity_id == entity_id
                    )
                )
            )
            .order_by(FinancialAuditLog.performed_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_action_type(
        self,
        db: Session,
        *,
        action_type: str,
        workspace_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[FinancialAuditLog]:
        """
        Get audit logs by action type (SECURITY-CRITICAL)

        Args:
            db: Database session
            action_type: Action type ('created', 'updated', 'deleted', etc.)
            workspace_id: Workspace ID to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of audit logs with matching action type
        """
        return (
            db.query(FinancialAuditLog)
            .filter(
                FinancialAuditLog.workspace_id == workspace_id,
                FinancialAuditLog.action_type == action_type
            )
            .order_by(FinancialAuditLog.performed_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_user(
        self,
        db: Session,
        *,
        user_id: int,
        workspace_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[FinancialAuditLog]:
        """
        Get audit logs by user (SECURITY-CRITICAL)

        Args:
            db: Database session
            user_id: User ID who performed the action
            workspace_id: Workspace ID to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of audit logs performed by the user
        """
        return (
            db.query(FinancialAuditLog)
            .filter(
                FinancialAuditLog.workspace_id == workspace_id,
                FinancialAuditLog.performed_by == user_id
            )
            .order_by(FinancialAuditLog.performed_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_date_range(
        self,
        db: Session,
        *,
        start_date: datetime,
        end_date: datetime,
        workspace_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[FinancialAuditLog]:
        """
        Get audit logs within a date range (SECURITY-CRITICAL)

        Args:
            db: Database session
            start_date: Start datetime (inclusive)
            end_date: End datetime (inclusive)
            workspace_id: Workspace ID to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of audit logs in the date range
        """
        return (
            db.query(FinancialAuditLog)
            .filter(
                FinancialAuditLog.workspace_id == workspace_id,
                FinancialAuditLog.performed_at >= start_date,
                FinancialAuditLog.performed_at <= end_date
            )
            .order_by(FinancialAuditLog.performed_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_recent_logs(
        self,
        db: Session,
        *,
        workspace_id: int,
        limit: int = 50
    ) -> List[FinancialAuditLog]:
        """
        Get recent audit logs for a workspace (SECURITY-CRITICAL)

        Args:
            db: Database session
            workspace_id: Workspace ID to filter by
            limit: Maximum number of records to return

        Returns:
            List of recent audit logs
        """
        return (
            db.query(FinancialAuditLog)
            .filter(FinancialAuditLog.workspace_id == workspace_id)
            .order_by(FinancialAuditLog.performed_at.desc())
            .limit(limit)
            .all()
        )


# Singleton instance
financial_audit_log_dao = FinancialAuditLogDAO(FinancialAuditLog)
