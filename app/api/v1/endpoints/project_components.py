"""Project component endpoints"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_workspace
from app.models.workspace import Workspace
from app.schemas.project_component import ProjectComponentCreate, ProjectComponentUpdate, ProjectComponentResponse
from app.dao.project_component import project_component_dao
from app.services.project_component_service import project_component_service


router = APIRouter()


@router.get("/", response_model=List[ProjectComponentResponse])
def get_project_components(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=100),
    project_id: int = Query(None),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Get all project components, optionally filtered by project"""
    if project_id:
        components = project_component_dao.get_by_project(
            db, project_id=project_id, workspace_id=workspace.id, skip=skip, limit=limit
        )
    else:
        components = project_component_dao.get_by_workspace(
            db, workspace_id=workspace.id, skip=skip, limit=limit
        )
    return components


@router.get("/{component_id}", response_model=ProjectComponentResponse)
def get_project_component(
    component_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Get project component by ID"""
    component = project_component_dao.get_by_id_and_workspace(
        db, id=component_id, workspace_id=workspace.id
    )
    if not component:
        raise HTTPException(status_code=404, detail="Project component not found")
    return component


@router.post("/", response_model=ProjectComponentResponse, status_code=201)
def create_project_component(
    component_in: ProjectComponentCreate,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Create new project component"""
    component = project_component_service.create_component(db, component_in, workspace.id)
    return component


@router.put("/{component_id}", response_model=ProjectComponentResponse)
def update_project_component(
    component_id: int,
    component_in: ProjectComponentUpdate,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Update project component"""
    component = project_component_service.update_component(db, component_id, component_in, workspace.id)
    if not component:
        raise HTTPException(status_code=404, detail="Project component not found")
    return component


@router.delete("/{component_id}", status_code=204)
def delete_project_component(
    component_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Delete project component"""
    deleted = project_component_service.delete_component(db, component_id, workspace.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Project component not found")
