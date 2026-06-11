"""Project component task endpoints"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_workspace, get_current_active_user
from app.models.profile import Profile
from app.models.workspace import Workspace
from app.schemas.project_component_task import ProjectComponentTaskCreate, ProjectComponentTaskUpdate, ProjectComponentTaskResponse
from app.services.project_component_task_service import project_component_task_service


router = APIRouter()


@router.get("/", response_model=List[ProjectComponentTaskResponse])
def get_project_component_tasks(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=100),
    project_component_id: int = Query(None),
    incomplete_only: bool = Query(False),
    is_note: bool | None = Query(None, description="Filter by note vs task; omit to return both"),
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return project_component_task_service.get_tasks(
        db,
        workspace_id=workspace.id,
        user_id=current_user.id,
        project_component_id=project_component_id,
        incomplete_only=incomplete_only,
        is_note=is_note,
        skip=skip,
        limit=limit,
    )


@router.get("/{task_id}/", response_model=ProjectComponentTaskResponse)
def get_project_component_task(
    task_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    task = project_component_task_service.get_by_id(
        db, task_id=task_id, workspace_id=workspace.id, user_id=current_user.id
    )
    if not task:
        raise HTTPException(status_code=404, detail="Project component task not found")
    return task


@router.post("/", response_model=ProjectComponentTaskResponse, status_code=201)
def create_project_component_task(
    task_in: ProjectComponentTaskCreate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return project_component_task_service.create_task(
        db, task_in, workspace.id, current_user.id
    )


@router.put("/{task_id}/", response_model=ProjectComponentTaskResponse)
def update_project_component_task(
    task_id: int,
    task_in: ProjectComponentTaskUpdate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    task = project_component_task_service.update_task(
        db, task_id, task_in, workspace.id, current_user.id
    )
    if not task:
        raise HTTPException(status_code=404, detail="Project component task not found")
    return task


@router.delete("/{task_id}/", status_code=204)
def delete_project_component_task(
    task_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    deleted = project_component_task_service.delete_task(
        db, task_id, workspace.id, current_user.id
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Project component task not found")
