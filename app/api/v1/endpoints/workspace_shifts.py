"""Workspace production shift windows."""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_active_user, get_current_workspace, get_db
from app.dao.workspace_member import workspace_member_dao
from app.models.profile import Profile
from app.models.workspace import Workspace
from app.schemas.workspace_shift import (
    WorkspaceShiftCreate,
    WorkspaceShiftResponse,
    WorkspaceShiftUpdate,
)
from app.services.workspace_shift_service import workspace_shift_service

router = APIRouter()


def _require_owner(db: Session, workspace: Workspace, user: Profile) -> None:
    member = workspace_member_dao.get_by_workspace_and_user(
        db, workspace_id=workspace.id, user_id=user.id
    )
    if member is None or member.role != "owner":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the workspace owner can manage shifts")


@router.get("/", response_model=List[WorkspaceShiftResponse])
def list_workspace_shifts(
    active_only: bool = Query(False),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    return workspace_shift_service.list_shifts(
        db, workspace_id=workspace.id, active_only=active_only
    )


@router.post("/", response_model=WorkspaceShiftResponse, status_code=status.HTTP_201_CREATED)
def create_workspace_shift(
    body: WorkspaceShiftCreate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    _require_owner(db, workspace, current_user)
    try:
        return workspace_shift_service.create_shift(
            db, workspace_id=workspace.id, user_id=current_user.id, data=body
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.patch("/{shift_id}/", response_model=WorkspaceShiftResponse)
def update_workspace_shift(
    shift_id: int,
    body: WorkspaceShiftUpdate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    _require_owner(db, workspace, current_user)
    try:
        return workspace_shift_service.update_shift(
            db,
            shift_id=shift_id,
            workspace_id=workspace.id,
            user_id=current_user.id,
            data=body,
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND if "not found" in str(e).lower() else status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.delete("/{shift_id}/", status_code=status.HTTP_204_NO_CONTENT)
def delete_workspace_shift(
    shift_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    _require_owner(db, workspace, current_user)
    try:
        workspace_shift_service.delete_shift(db, shift_id=shift_id, workspace_id=workspace.id)
    except ValueError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(e)) from e
