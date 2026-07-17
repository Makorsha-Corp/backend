"""Work order schedule API — staged maintenance before confirm."""
from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_workspace, get_current_active_user
from app.models.workspace import Workspace
from app.models.profile import Profile
from app.models.enums import WorkOrderScheduleStatusEnum
from app.schemas.work_order_schedule import (
    WorkOrderScheduleResponse,
    StageWorkOrderDayRequest,
)
from app.schemas.work_order import WorkOrderResponse
from app.services.work_order_schedule_service import work_order_schedule_service


router = APIRouter()


@router.get(
    "/",
    response_model=List[WorkOrderScheduleResponse],
    status_code=status.HTTP_200_OK,
    summary="List work order schedules for sheet view",
)
def list_work_order_schedules(
    factory_id: Optional[int] = Query(None),
    machine_id: Optional[int] = Query(None),
    start_date_from: Optional[date] = Query(None),
    start_date_to: Optional[date] = Query(None),
    schedule_status: Optional[WorkOrderScheduleStatusEnum] = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(1000, ge=1, le=1000),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    return work_order_schedule_service.list_schedules(
        db,
        workspace_id=workspace.id,
        factory_id=factory_id,
        machine_id=machine_id,
        start_date_from=start_date_from,
        start_date_to=start_date_to,
        status=schedule_status,
        skip=skip,
        limit=limit,
    )


@router.post(
    "/stage-day/",
    response_model=List[WorkOrderScheduleResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Stage recurring templates for a day (manual — no live work orders yet)",
)
def stage_work_order_day(
    body: StageWorkOrderDayRequest,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return work_order_schedule_service.stage_day(
        db, body=body, workspace_id=workspace.id, user_id=current_user.id,
    )


@router.post(
    "/{schedule_id}/confirm/",
    response_model=WorkOrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Confirm staged schedule — creates DRAFT work order",
)
def confirm_work_order_schedule(
    schedule_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    wo, _schedule = work_order_schedule_service.confirm_schedule(
        db, schedule_id=schedule_id, workspace_id=workspace.id, user_id=current_user.id,
    )
    return wo


@router.post(
    "/{schedule_id}/cancel/",
    response_model=WorkOrderScheduleResponse,
    status_code=status.HTTP_200_OK,
    summary="Cancel a staged schedule",
)
def cancel_work_order_schedule(
    schedule_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return work_order_schedule_service.cancel_schedule(
        db, schedule_id=schedule_id, workspace_id=workspace.id, user_id=current_user.id,
    )
