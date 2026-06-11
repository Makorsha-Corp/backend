"""Miscellaneous project cost endpoints"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_workspace, get_current_active_user
from app.models.profile import Profile
from app.models.workspace import Workspace
from app.schemas.miscellaneous_project_cost import MiscellaneousProjectCostCreate, MiscellaneousProjectCostUpdate, MiscellaneousProjectCostResponse
from app.services.miscellaneous_project_cost_service import miscellaneous_project_cost_service


router = APIRouter()


@router.get("/", response_model=List[MiscellaneousProjectCostResponse])
def get_miscellaneous_project_costs(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=100),
    project_id: int = Query(None),
    project_component_id: int = Query(None),
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return miscellaneous_project_cost_service.get_costs(
        db,
        workspace_id=workspace.id,
        user_id=current_user.id,
        project_id=project_id,
        project_component_id=project_component_id,
        skip=skip,
        limit=limit,
    )


@router.get("/{cost_id}/", response_model=MiscellaneousProjectCostResponse)
def get_miscellaneous_project_cost(
    cost_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    cost = miscellaneous_project_cost_service.get_by_id(
        db, cost_id=cost_id, workspace_id=workspace.id, user_id=current_user.id
    )
    if not cost:
        raise HTTPException(status_code=404, detail="Miscellaneous project cost not found")
    return cost


@router.post("/", response_model=MiscellaneousProjectCostResponse, status_code=201)
def create_miscellaneous_project_cost(
    cost_in: MiscellaneousProjectCostCreate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return miscellaneous_project_cost_service.create_cost(
        db, cost_in, workspace.id, current_user.id
    )


@router.put("/{cost_id}/", response_model=MiscellaneousProjectCostResponse)
def update_miscellaneous_project_cost(
    cost_id: int,
    cost_in: MiscellaneousProjectCostUpdate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    cost = miscellaneous_project_cost_service.update_cost(
        db, cost_id, cost_in, workspace.id, current_user.id
    )
    if not cost:
        raise HTTPException(status_code=404, detail="Miscellaneous project cost not found")
    return cost


@router.delete("/{cost_id}/", status_code=204)
def delete_miscellaneous_project_cost(
    cost_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    deleted = miscellaneous_project_cost_service.delete_cost(
        db, cost_id, workspace.id, current_user.id
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Miscellaneous project cost not found")
