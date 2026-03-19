"""Financial audit log API endpoints"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from datetime import datetime

from app.core.deps import get_db, get_current_active_user, get_current_workspace
from app.models.profile import Profile
from app.models.workspace import Workspace
from app.dao.financial_audit_log import financial_audit_log_dao
from app.schemas.financial_audit_log import FinancialAuditLogResponse

router = APIRouter()


@router.get("/", response_model=List[FinancialAuditLogResponse])
def get_recent_audit_logs(
    limit: int = Query(default=50, le=200, description="Maximum number of records to return"),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """
    Get recent audit logs for the workspace.

    Returns most recent audit logs up to the specified limit.
    """
    logs = financial_audit_log_dao.get_recent_logs(
        db,
        workspace_id=workspace.id,
        limit=limit
    )
    return logs


@router.get("/entity/{entity_type}/{entity_id}", response_model=List[FinancialAuditLogResponse])
def get_entity_audit_logs(
    entity_type: str,
    entity_id: int,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, le=200),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """
    Get all audit logs for a specific entity.

    Args:
        entity_type: Type of entity ('account', 'invoice', 'payment')
        entity_id: Entity ID
        skip: Number of records to skip
        limit: Maximum number of records to return

    Returns:
        List of audit logs for the entity
    """
    logs = financial_audit_log_dao.get_by_entity(
        db,
        entity_type=entity_type,
        entity_id=entity_id,
        workspace_id=workspace.id,
        skip=skip,
        limit=limit
    )
    return logs


@router.get("/related/{entity_type}/{entity_id}", response_model=List[FinancialAuditLogResponse])
def get_related_audit_logs(
    entity_type: str,
    entity_id: int,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, le=200),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """
    Get all audit logs related to an entity (direct and related).

    For example, for an account, this returns logs for:
    - The account itself
    - All invoices for that account
    - All payments for those invoices

    Args:
        entity_type: Type of entity ('account', 'invoice', 'payment')
        entity_id: Entity ID
        skip: Number of records to skip
        limit: Maximum number of records to return

    Returns:
        List of all related audit logs
    """
    logs = financial_audit_log_dao.get_related_logs(
        db,
        entity_type=entity_type,
        entity_id=entity_id,
        workspace_id=workspace.id,
        skip=skip,
        limit=limit
    )
    return logs


@router.get("/action/{action_type}", response_model=List[FinancialAuditLogResponse])
def get_audit_logs_by_action(
    action_type: str,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, le=200),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """
    Get audit logs by action type.

    Args:
        action_type: Action type ('created', 'updated', 'deleted', 'status_changed', etc.)
        skip: Number of records to skip
        limit: Maximum number of records to return

    Returns:
        List of audit logs with matching action type
    """
    logs = financial_audit_log_dao.get_by_action_type(
        db,
        action_type=action_type,
        workspace_id=workspace.id,
        skip=skip,
        limit=limit
    )
    return logs


@router.get("/user/{user_id}", response_model=List[FinancialAuditLogResponse])
def get_user_audit_logs(
    user_id: int,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, le=200),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """
    Get audit logs by user.

    Args:
        user_id: User ID who performed the action
        skip: Number of records to skip
        limit: Maximum number of records to return

    Returns:
        List of audit logs performed by the user
    """
    logs = financial_audit_log_dao.get_by_user(
        db,
        user_id=user_id,
        workspace_id=workspace.id,
        skip=skip,
        limit=limit
    )
    return logs


@router.get("/date-range", response_model=List[FinancialAuditLogResponse])
def get_audit_logs_by_date_range(
    start_date: datetime = Query(..., description="Start datetime (inclusive)"),
    end_date: datetime = Query(..., description="End datetime (inclusive)"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, le=200),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """
    Get audit logs within a date range.

    Args:
        start_date: Start datetime (inclusive)
        end_date: End datetime (inclusive)
        skip: Number of records to skip
        limit: Maximum number of records to return

    Returns:
        List of audit logs in the date range
    """
    logs = financial_audit_log_dao.get_by_date_range(
        db,
        start_date=start_date,
        end_date=end_date,
        workspace_id=workspace.id,
        skip=skip,
        limit=limit
    )
    return logs
