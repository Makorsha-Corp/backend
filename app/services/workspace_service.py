"""Workspace Service — owns transaction boundaries for all workspace operations."""
import logging
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, PermissionDeniedError, ValidationError
from app.dao.profile import profile_dao
from app.dao.workspace import workspace_dao
from app.dao.workspace_invitation import workspace_invitation_dao
from app.dao.workspace_member import workspace_member_dao
from app.managers.workspace_manager import workspace_manager
from app.models.profile import Profile
from app.models.workspace import Workspace
from app.models.workspace_invitation import WorkspaceInvitation
from app.models.workspace_member import WorkspaceMember
from app.schemas.workspace import WorkspaceCreate, WorkspaceUpdate
from app.services.base_service import BaseService

logger = logging.getLogger(__name__)


class WorkspaceService(BaseService):
    """
    Service for workspace workflows.

    Owns:
    - Authorization checks (membership and role requirements)
    - Transaction boundaries (commit/rollback)
    - Orchestration of the workspace_manager for business logic
    - Data enrichment for read operations

    Raises APIException subclasses (PermissionDeniedError, NotFoundError,
    ValidationError) so the global exception handler in main.py formats them
    correctly — endpoints do not need try/except for business errors.
    """

    def __init__(self):
        super().__init__()
        self.workspace_manager = workspace_manager
        self.workspace_dao = workspace_dao
        self.member_dao = workspace_member_dao
        self.invitation_dao = workspace_invitation_dao
        self.profile_dao = profile_dao

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    def _require_active_membership(
        self, db: Session, workspace_id: int, user_id: int
    ) -> WorkspaceMember:
        """Return active membership or raise PermissionDeniedError (403)."""
        membership = self.member_dao.get_by_workspace_and_user(
            db, workspace_id=workspace_id, user_id=user_id
        )
        if not membership or membership.status != 'active':
            raise PermissionDeniedError("You are not a member of this workspace")
        return membership

    def _require_owner(
        self, db: Session, workspace_id: int, user_id: int
    ) -> WorkspaceMember:
        """Return membership and assert owner role or raise PermissionDeniedError (403)."""
        membership = self._require_active_membership(db, workspace_id, user_id)
        if membership.role != 'owner':
            raise PermissionDeniedError("Only the workspace owner can perform this action")
        return membership

    # -------------------------------------------------------------------------
    # Workspace CRUD
    # -------------------------------------------------------------------------

    def list_user_workspaces(
        self, db: Session, user_id: int
    ) -> List[Tuple[Workspace, WorkspaceMember]]:
        """Return all active (workspace, membership) pairs for a user."""
        memberships = self.member_dao.get_by_user(db, user_id=user_id)
        result = []
        for m in memberships:
            if m.status != 'active':
                continue
            workspace = self.workspace_dao.get(db, id=m.workspace_id)
            if workspace:
                result.append((workspace, m))
        return result

    def create_workspace(
        self, db: Session, workspace_data: WorkspaceCreate, owner_user_id: int
    ) -> Workspace:
        """Create workspace with owner, seed defaults, and commit."""
        try:
            workspace = self.workspace_manager.create_workspace_with_owner(
                session=db,
                workspace_data=workspace_data,
                owner_user_id=owner_user_id,
                subscription_plan_id=workspace_data.subscription_plan_id,
                owner_position=workspace_data.owner_position,
            )
            self._commit_transaction(db)
            db.refresh(workspace)
            return workspace
        except ValueError as e:
            self._rollback_transaction(db)
            raise ValidationError(str(e))
        except Exception:
            self._rollback_transaction(db)
            raise

    def get_workspace_with_plan(
        self, db: Session, workspace_id: int, requesting_user_id: int
    ) -> Tuple[Workspace, Optional[object]]:
        """Return (workspace, plan) for a member — plan may be None."""
        self._require_active_membership(db, workspace_id, requesting_user_id)
        workspace = self.workspace_dao.get(db, id=workspace_id)
        if not workspace:
            raise NotFoundError("Workspace not found")
        plan = getattr(workspace, 'subscription_plan', None)
        return workspace, plan

    def update_workspace(
        self,
        db: Session,
        workspace_id: int,
        current_user_id: int,
        workspace_update: WorkspaceUpdate,
    ) -> Workspace:
        """Update workspace details (owner only)."""
        workspace = self.workspace_dao.get(db, id=workspace_id)
        if not workspace:
            raise NotFoundError("Workspace not found")
        if workspace.owner_user_id != current_user_id:
            raise PermissionDeniedError("Only workspace owner can update workspace")
        try:
            updated = self.workspace_dao.update(db, db_obj=workspace, obj_in=workspace_update)
            self._commit_transaction(db)
            db.refresh(updated)
            return updated
        except Exception:
            self._rollback_transaction(db)
            raise

    # -------------------------------------------------------------------------
    # Member management
    # -------------------------------------------------------------------------

    def list_members(
        self,
        db: Session,
        workspace_id: int,
        requesting_user_id: int,
        include_inactive: bool = False,
    ) -> List[Tuple[WorkspaceMember, Optional[Profile]]]:
        """Return enriched (member, user_profile) list."""
        self._require_active_membership(db, workspace_id, requesting_user_id)
        members = self.member_dao.get_by_workspace(db, workspace_id=workspace_id)
        if not include_inactive:
            members = [m for m in members if m.status == 'active']
        return [
            (m, self.profile_dao.get(db, id=m.user_id))
            for m in members
        ]

    def update_member_role(
        self,
        db: Session,
        workspace_id: int,
        owner_user_id: int,
        target_user_id: int,
        new_role: str,
        position: str | None = None,
    ) -> WorkspaceMember:
        """Update a member's role and/or position (owner only; cannot demote owner)."""
        workspace = self.workspace_dao.get(db, id=workspace_id)
        if not workspace:
            raise NotFoundError("Workspace not found")
        if workspace.owner_user_id != owner_user_id:
            raise PermissionDeniedError("Only workspace owner can change member roles")
        member = self.member_dao.get_by_workspace_and_user(
            db, workspace_id=workspace_id, user_id=target_user_id
        )
        if not member:
            raise NotFoundError("Member not found")
        if member.role == 'owner':
            raise PermissionDeniedError("Cannot change workspace owner's role")
        try:
            member.role = new_role
            if position is not None:
                member.position = position
            self._commit_transaction(db)
            db.refresh(member)
            return member
        except Exception:
            self._rollback_transaction(db)
            raise

    def remove_member(
        self,
        db: Session,
        workspace_id: int,
        remover_user_id: int,
        target_user_id: int,
    ) -> None:
        """Remove a member from workspace (business rules enforced by manager)."""
        current_membership = self._require_active_membership(db, workspace_id, remover_user_id)
        try:
            self.workspace_manager.remove_member_from_workspace(
                session=db,
                workspace_id=workspace_id,
                user_id=target_user_id,
                remover_id=remover_user_id,
                remover_role=current_membership.role,
            )
            self._commit_transaction(db)
        except ValueError as e:
            self._rollback_transaction(db)
            raise PermissionDeniedError(str(e))
        except Exception:
            self._rollback_transaction(db)
            raise

    # -------------------------------------------------------------------------
    # Invitation management
    # -------------------------------------------------------------------------

    def send_invitation(
        self,
        db: Session,
        workspace_id: int,
        inviter_user_id: int,
        email: str,
        role: str,
        position: str | None = None,
    ) -> WorkspaceInvitation:
        """Create and persist a workspace invitation (owner only)."""
        self._require_owner(db, workspace_id, inviter_user_id)
        try:
            invitation = self.workspace_manager.create_invitation(
                session=db,
                workspace_id=workspace_id,
                email=email,
                role=role,
                position=position,
                inviter_id=inviter_user_id,
            )
            self._commit_transaction(db)
            db.refresh(invitation)
            return invitation
        except ValueError as e:
            self._rollback_transaction(db)
            raise ValidationError(str(e))
        except Exception:
            self._rollback_transaction(db)
            raise

    def list_invitations(
        self,
        db: Session,
        workspace_id: int,
        requesting_user_id: int,
        include_expired: bool = False,
    ) -> List[Tuple[WorkspaceInvitation, Optional[Workspace], Optional[Profile]]]:
        """Return enriched (invitation, workspace, inviter) list (owner only)."""
        self._require_owner(db, workspace_id, requesting_user_id)
        if include_expired:
            invitations = self.invitation_dao.get_all_invitations(db, workspace_id=workspace_id)
        else:
            invitations = self.invitation_dao.get_pending_invitations(db, workspace_id=workspace_id)
        workspace = self.workspace_dao.get(db, id=workspace_id)
        return [
            (
                inv,
                workspace,
                self.profile_dao.get(db, id=inv.invited_by_user_id) if inv.invited_by_user_id else None,
            )
            for inv in invitations
        ]

    def accept_invitation(
        self,
        db: Session,
        workspace_id: int,
        token: str,
        current_user_id: int,
        current_user_email: str,
        position: str | None = None,
    ) -> WorkspaceMember:
        """Validate and accept an invitation for an existing authenticated user."""
        try:
            invitation = self.workspace_manager.validate_invitation_for_user(
                session=db,
                invitation_token=token,
                user_email=current_user_email,
            )
            if invitation.workspace_id != workspace_id:
                raise ValidationError("Invitation does not belong to this workspace")
            # User-entered position overrides inviter's pre-filled position
            if position is not None:
                invitation.position = position
                db.flush()
            member = self.workspace_manager.accept_invitation(
                session=db,
                invitation_id=invitation.id,
                user_id=current_user_id,
            )
            self._commit_transaction(db)
            db.refresh(member)
            return member
        except (ValidationError, PermissionDeniedError, NotFoundError):
            self._rollback_transaction(db)
            raise
        except ValueError as e:
            self._rollback_transaction(db)
            raise ValidationError(str(e))
        except Exception:
            self._rollback_transaction(db)
            raise

    def cancel_invitation(
        self,
        db: Session,
        workspace_id: int,
        invitation_id: int,
        canceller_user_id: int,
    ) -> None:
        """Cancel a pending invitation (owner only, business rules in manager)."""
        current_membership = self._require_active_membership(db, workspace_id, canceller_user_id)
        try:
            self.workspace_manager.cancel_invitation(
                session=db,
                invitation_id=invitation_id,
                canceller_id=canceller_user_id,
                canceller_role=current_membership.role,
                workspace_id=workspace_id,
            )
            self._commit_transaction(db)
        except ValueError as e:
            self._rollback_transaction(db)
            raise PermissionDeniedError(str(e))
        except Exception:
            self._rollback_transaction(db)
            raise

    def get_my_invitations(
        self, db: Session, user_email: str
    ) -> List[Tuple[WorkspaceInvitation, Optional[Workspace], Optional[Profile]]]:
        """Return enriched pending invitations for the current user's email."""
        invitations = self.invitation_dao.get_user_invitations(db, email=user_email)
        return [
            (
                inv,
                self.workspace_dao.get(db, id=inv.workspace_id),
                self.profile_dao.get(db, id=inv.invited_by_user_id) if inv.invited_by_user_id else None,
            )
            for inv in invitations
        ]


workspace_service = WorkspaceService()
