"""Project component item endpoints"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_workspace
from app.models.workspace import Workspace
from app.schemas.project_component_item import ProjectComponentItemCreate, ProjectComponentItemUpdate, ProjectComponentItemResponse
from app.dao.project_component_item import project_component_item_dao
from app.services.project_component_item_service import project_component_item_service


router = APIRouter()


@router.get("/", response_model=List[ProjectComponentItemResponse])
def get_project_component_items(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=100),
    project_component_id: int = Query(None),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Get all project component items, optionally filtered by component"""
    if project_component_id:
        items = project_component_item_dao.get_by_component(
            db, project_component_id=project_component_id, workspace_id=workspace.id, skip=skip, limit=limit
        )
    else:
        items = project_component_item_dao.get_by_workspace(
            db, workspace_id=workspace.id, skip=skip, limit=limit
        )
    return items


@router.get("/{item_id}", response_model=ProjectComponentItemResponse)
def get_project_component_item(
    item_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Get project component item by ID"""
    item = project_component_item_dao.get_by_id_and_workspace(
        db, id=item_id, workspace_id=workspace.id
    )
    if not item:
        raise HTTPException(status_code=404, detail="Project component item not found")
    return item


@router.post("/", response_model=ProjectComponentItemResponse, status_code=201)
def create_project_component_item(
    item_in: ProjectComponentItemCreate,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Create new project component item"""
    item = project_component_item_service.create_component_item(db, item_in, workspace.id)
    return item


@router.put("/{item_id}", response_model=ProjectComponentItemResponse)
def update_project_component_item(
    item_id: int,
    item_in: ProjectComponentItemUpdate,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Update project component item"""
    item = project_component_item_service.update_component_item(db, item_id, item_in, workspace.id)
    if not item:
        raise HTTPException(status_code=404, detail="Project component item not found")
    return item


@router.delete("/{item_id}", status_code=204)
def delete_project_component_item(
    item_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Delete project component item"""
    deleted = project_component_item_service.delete_component_item(db, item_id, workspace.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Project component item not found")
