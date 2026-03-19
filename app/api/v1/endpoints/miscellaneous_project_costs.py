"""Miscellaneous project cost endpoints"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_workspace
from app.models.workspace import Workspace
from app.schemas.miscellaneous_project_cost import MiscellaneousProjectCostCreate, MiscellaneousProjectCostUpdate, MiscellaneousProjectCostResponse
from app.dao.miscellaneous_project_cost import miscellaneous_project_cost_dao
from app.services.miscellaneous_project_cost_service import miscellaneous_project_cost_service


router = APIRouter()


@router.get("/", response_model=List[MiscellaneousProjectCostResponse])
def get_miscellaneous_project_costs(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=100),
    project_id: int = Query(None),
    project_component_id: int = Query(None),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Get all miscellaneous costs, optionally filtered by project or component"""
    if project_id:
        costs = miscellaneous_project_cost_dao.get_by_project(
            db, project_id=project_id, workspace_id=workspace.id, skip=skip, limit=limit
        )
    elif project_component_id:
        costs = miscellaneous_project_cost_dao.get_by_component(
            db, project_component_id=project_component_id, workspace_id=workspace.id, skip=skip, limit=limit
        )
    else:
        costs = miscellaneous_project_cost_dao.get_by_workspace(
            db, workspace_id=workspace.id, skip=skip, limit=limit
        )
    return costs


@router.get("/{cost_id}", response_model=MiscellaneousProjectCostResponse)
def get_miscellaneous_project_cost(
    cost_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Get miscellaneous project cost by ID"""
    cost = miscellaneous_project_cost_dao.get_by_id_and_workspace(
        db, id=cost_id, workspace_id=workspace.id
    )
    if not cost:
        raise HTTPException(status_code=404, detail="Miscellaneous project cost not found")
    return cost


@router.post("/", response_model=MiscellaneousProjectCostResponse, status_code=201)
def create_miscellaneous_project_cost(
    cost_in: MiscellaneousProjectCostCreate,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Create new miscellaneous project cost"""
    cost = miscellaneous_project_cost_service.create_cost(db, cost_in, workspace.id)
    return cost


@router.put("/{cost_id}", response_model=MiscellaneousProjectCostResponse)
def update_miscellaneous_project_cost(
    cost_id: int,
    cost_in: MiscellaneousProjectCostUpdate,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Update miscellaneous project cost"""
    cost = miscellaneous_project_cost_service.update_cost(db, cost_id, cost_in, workspace.id)
    if not cost:
        raise HTTPException(status_code=404, detail="Miscellaneous project cost not found")
    return cost


@router.delete("/{cost_id}", status_code=204)
def delete_miscellaneous_project_cost(
    cost_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Delete miscellaneous project cost"""
    deleted = miscellaneous_project_cost_service.delete_cost(db, cost_id, workspace.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Miscellaneous project cost not found")
