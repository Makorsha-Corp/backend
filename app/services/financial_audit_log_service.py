"""Financial audit log service"""
from datetime import datetime
from sqlalchemy.orm import Session
from app.dao.financial_audit_log import financial_audit_log_dao


class FinancialAuditLogService:
    """Service for financial audit log - read-only"""

    def get_recent_logs(self, db: Session, workspace_id: int, limit: int = 50):
        """Get recent audit logs"""
        return financial_audit_log_dao.get_recent_logs(db, workspace_id=workspace_id, limit=limit)

    def get_by_entity(self, db: Session, entity_type: str, entity_id: int, workspace_id: int, skip: int = 0, limit: int = 100):
        """Get audit logs by entity"""
        return financial_audit_log_dao.get_by_entity(db, entity_type=entity_type, entity_id=entity_id, workspace_id=workspace_id, skip=skip, limit=limit)

    def get_related_logs(self, db: Session, entity_type: str, entity_id: int, workspace_id: int, skip: int = 0, limit: int = 100):
        """Get related audit logs"""
        return financial_audit_log_dao.get_related_logs(db, entity_type=entity_type, entity_id=entity_id, workspace_id=workspace_id, skip=skip, limit=limit)

    def get_by_action_type(self, db: Session, action_type: str, workspace_id: int, skip: int = 0, limit: int = 100):
        """Get audit logs by action type"""
        return financial_audit_log_dao.get_by_action_type(db, action_type=action_type, workspace_id=workspace_id, skip=skip, limit=limit)

    def get_by_user(self, db: Session, user_id: int, workspace_id: int, skip: int = 0, limit: int = 100):
        """Get audit logs by user"""
        return financial_audit_log_dao.get_by_user(db, user_id=user_id, workspace_id=workspace_id, skip=skip, limit=limit)

    def get_by_date_range(self, db: Session, start_date: datetime, end_date: datetime, workspace_id: int, skip: int = 0, limit: int = 100):
        """Get audit logs by date range"""
        return financial_audit_log_dao.get_by_date_range(db, start_date=start_date, end_date=end_date, workspace_id=workspace_id, skip=skip, limit=limit)


financial_audit_log_service = FinancialAuditLogService()
