"""Project component item endpoints"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_workspace, get_current_active_user
from app.models.profile import Profile
from app.models.workspace import Workspace
from app.schemas.project_component_item import ProjectComponentItemCreate, ProjectComponentItemUpdate, ProjectComponentItemResponse
from app.services.project_component_item_service import project_component_item_service


router = APIRouter()


@router.get("/", response_model=List[ProjectComponentItemResponse])
def get_project_component_items(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=100),
    project_component_id: int = Query(None),
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return project_component_item_service.get_items(
        db,
        workspace_id=workspace.id,
        user_id=current_user.id,
        project_component_id=project_component_id,
        skip=skip,
        limit=limit,
    )


@router.get("/{item_id}/", response_model=ProjectComponentItemResponse)
def get_project_component_item(
    item_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    item = project_component_item_service.get_by_id(
        db, item_id=item_id, workspace_id=workspace.id, user_id=current_user.id
    )
    if not item:
        raise HTTPException(status_code=404, detail="Project component item not found")
    return item


@router.post("/", response_model=ProjectComponentItemResponse, status_code=201)
def create_project_component_item(
    item_in: ProjectComponentItemCreate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return project_component_item_service.create_component_item(
        db, item_in, workspace.id, current_user.id
    )


@router.put("/{item_id}/", response_model=ProjectComponentItemResponse)
def update_project_component_item(
    item_id: int,
    item_in: ProjectComponentItemUpdate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    item = project_component_item_service.update_component_item(
        db, item_id, item_in, workspace.id, current_user.id
    )
    if not item:
        raise HTTPException(status_code=404, detail="Project component item not found")
    return item


@router.delete("/{item_id}/", status_code=204)
def delete_project_component_item(
    item_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    deleted = project_component_item_service.delete_component_item(
        db, item_id, workspace.id, current_user.id
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Project component item not found")
