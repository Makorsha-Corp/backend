"""Production route endpoints."""
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_active_user, get_current_workspace, get_db
from app.models.profile import Profile
from app.models.workspace import Workspace
from app.schemas.production_route import (
    ProductionRouteCreate,
    ProductionRouteResponse,
    ProductionRouteStepCreate,
    ProductionRouteStepResponse,
    ProductionRouteStepUpdate,
    ProductionRouteUpdate,
)
from app.services.production_route_service import production_route_service

router = APIRouter()


@router.get("/", response_model=List[ProductionRouteResponse])
def list_routes(
    factory_id: Optional[int] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    return production_route_service.get_routes(db, workspace.id, factory_id, skip, limit)


@router.post("/", response_model=ProductionRouteResponse, status_code=status.HTTP_201_CREATED)
def create_route(
    body: ProductionRouteCreate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return production_route_service.create_route(db, body, workspace.id, current_user.id)


@router.get("/{route_id}/", response_model=ProductionRouteResponse)
def get_route(
    route_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    return production_route_service.get_route(db, route_id, workspace.id)


@router.put("/{route_id}/", response_model=ProductionRouteResponse)
def update_route(
    route_id: int,
    body: ProductionRouteUpdate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return production_route_service.update_route(db, route_id, body, workspace.id, current_user.id)


@router.delete("/{route_id}/", response_model=ProductionRouteResponse)
def delete_route(
    route_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    return production_route_service.delete_route(db, route_id, workspace.id)


@router.get("/{route_id}/steps/", response_model=List[ProductionRouteStepResponse])
def list_steps(
    route_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    return production_route_service.get_steps(db, route_id, workspace.id)


@router.post("/{route_id}/steps/", response_model=ProductionRouteStepResponse, status_code=status.HTTP_201_CREATED)
def add_step(
    route_id: int,
    body: ProductionRouteStepCreate,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    return production_route_service.add_step(db, route_id, body, workspace.id)


@router.put("/steps/{step_id}/", response_model=ProductionRouteStepResponse)
def update_step(
    step_id: int,
    body: ProductionRouteStepUpdate,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    return production_route_service.update_step(db, step_id, body, workspace.id)


@router.delete("/steps/{step_id}/", response_model=ProductionRouteStepResponse)
def delete_step(
    step_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    return production_route_service.delete_step(db, step_id, workspace.id)
