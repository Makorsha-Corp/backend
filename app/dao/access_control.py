"""DAO operations for AccessControl model (workspace-scoped RBAC)"""
from typing import List
from sqlalchemy.orm import Session
from app.dao.base import BaseDAO
from app.models.access_control import AccessControl
from app.schemas.access_control import AccessControlCreate, AccessControlUpdate
from app.models.enums import RoleEnum, AccessControlTypeEnum


class DAOAccessControl(BaseDAO[AccessControl, AccessControlCreate, AccessControlUpdate]):
    """
    DAO operations for AccessControl model (RBAC permissions).

    CRITICAL SECURITY: All methods MUST filter by workspace_id.
    Without workspace filtering, users could view/modify permissions from other workspaces!
    """

    def get_by_role(
        self, db: Session, *, role: RoleEnum, workspace_id: int, skip: int = 0, limit: int = 100
    ) -> List[AccessControl]:
        """
        Get access controls by role (SECURITY-CRITICAL: workspace-filtered)

        Args:
            db: Database session
            role: Role to filter by
            workspace_id: Workspace ID to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of access controls for the role in the workspace

        Security Note:
            WITHOUT workspace filter, this would expose RBAC configuration from ALL workspaces!
            This is a CRITICAL vulnerability that would allow privilege escalation.
        """
        return (
            db.query(AccessControl)
            .filter(
                AccessControl.workspace_id == workspace_id,  # SECURITY: CRITICAL filter
                AccessControl.role == role
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_type(
        self, db: Session, *, access_type: AccessControlTypeEnum, workspace_id: int, skip: int = 0, limit: int = 100
    ) -> List[AccessControl]:
        """
        Get access controls by type (SECURITY-CRITICAL: workspace-filtered)

        Args:
            db: Database session
            access_type: Access control type (page, manage-order-status, feature)
            workspace_id: Workspace ID to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of access controls of the type in the workspace

        Security Note:
            WITHOUT workspace filter, this would expose RBAC configuration from ALL workspaces!
        """
        return (
            db.query(AccessControl)
            .filter(
                AccessControl.workspace_id == workspace_id,  # SECURITY: CRITICAL filter
                AccessControl.type == access_type
            )
            .offset(skip)
            .limit(limit)
            .all()
        )


access_control_dao = DAOAccessControl(AccessControl)
