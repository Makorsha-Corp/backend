"""Project component task endpoints"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_workspace
from app.models.workspace import Workspace
from app.schemas.project_component_task import ProjectComponentTaskCreate, ProjectComponentTaskUpdate, ProjectComponentTaskResponse
from app.dao.project_component_task import project_component_task_dao
from app.services.project_component_task_service import project_component_task_service


router = APIRouter()


@router.get("/", response_model=List[ProjectComponentTaskResponse])
def get_project_component_tasks(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=100),
    project_component_id: int = Query(None),
    incomplete_only: bool = Query(False),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Get all project component tasks, optionally filtered by component or completion status"""
    if project_component_id and incomplete_only:
        tasks = project_component_task_dao.get_incomplete_tasks(
            db, project_component_id=project_component_id, workspace_id=workspace.id, skip=skip, limit=limit
        )
    elif project_component_id:
        tasks = project_component_task_dao.get_by_component(
            db, project_component_id=project_component_id, workspace_id=workspace.id, skip=skip, limit=limit
        )
    else:
        tasks = project_component_task_dao.get_by_workspace(
            db, workspace_id=workspace.id, skip=skip, limit=limit
        )
    return tasks


@router.get("/{task_id}", response_model=ProjectComponentTaskResponse)
def get_project_component_task(
    task_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Get project component task by ID"""
    task = project_component_task_dao.get_by_id_and_workspace(
        db, id=task_id, workspace_id=workspace.id
    )
    if not task:
        raise HTTPException(status_code=404, detail="Project component task not found")
    return task


@router.post("/", response_model=ProjectComponentTaskResponse, status_code=201)
def create_project_component_task(
    task_in: ProjectComponentTaskCreate,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Create new project component task"""
    task = project_component_task_service.create_task(db, task_in, workspace.id)
    return task


@router.put("/{task_id}", response_model=ProjectComponentTaskResponse)
def update_project_component_task(
    task_id: int,
    task_in: ProjectComponentTaskUpdate,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Update project component task"""
    task = project_component_task_service.update_task(db, task_id, task_in, workspace.id)
    if not task:
        raise HTTPException(status_code=404, detail="Project component task not found")
    return task


@router.delete("/{task_id}", status_code=204)
def delete_project_component_task(
    task_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Delete project component task"""
    deleted = project_component_task_service.delete_task(db, task_id, workspace.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Project component task not found")
