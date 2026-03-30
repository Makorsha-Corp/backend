"""Project component note endpoints"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_workspace
from app.models.workspace import Workspace
from app.schemas.project_component_note import ProjectComponentNoteCreate, ProjectComponentNoteUpdate, ProjectComponentNoteResponse
from app.services.project_component_note_service import project_component_note_service


router = APIRouter()


@router.get("/", response_model=List[ProjectComponentNoteResponse])
def get_project_component_notes(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=100),
    project_component_id: int = Query(None),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Get all project component notes, optionally filtered by component"""
    return project_component_note_service.get_notes(
        db, project_component_id=project_component_id, workspace_id=workspace.id, skip=skip, limit=limit
    )


@router.get("/{note_id}/", response_model=ProjectComponentNoteResponse)
def get_project_component_note(
    note_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Get project component note by ID"""
    note = project_component_note_service.get_by_id_and_workspace(
        db, id=note_id, workspace_id=workspace.id
    )
    if not note:
        raise HTTPException(status_code=404, detail="Project component note not found")
    return note


@router.post("/", response_model=ProjectComponentNoteResponse, status_code=201)
def create_project_component_note(
    note_in: ProjectComponentNoteCreate,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Create new project component note"""
    note = project_component_note_service.create_note(db, note_in, workspace.id)
    return note


@router.put("/{note_id}/", response_model=ProjectComponentNoteResponse)
def update_project_component_note(
    note_id: int,
    note_in: ProjectComponentNoteUpdate,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Update project component note"""
    note = project_component_note_service.update_note(db, note_id, note_in, workspace.id)
    if not note:
        raise HTTPException(status_code=404, detail="Project component note not found")
    return note


@router.delete("/{note_id}/", status_code=204)
def delete_project_component_note(
    note_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Delete project component note"""
    deleted = project_component_note_service.delete_note(db, note_id, workspace.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Project component note not found")
