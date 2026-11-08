"""Work order program endpoints."""
from typing import List

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_active_user, get_current_workspace, get_db
from app.models.profile import Profile
from app.models.work_order import WorkOrder
from app.models.work_order_program import WorkOrderProgram
from app.models.workspace import Workspace
from app.schemas.work_order_program import (
    WorkOrderProgramCreate,
    WorkOrderProgramOccurrence,
    WorkOrderProgramResponse,
)
from app.services.work_order_service import work_order_service

router = APIRouter()


def _occurrence(order: WorkOrder) -> WorkOrderProgramOccurrence:
    return WorkOrderProgramOccurrence(
        work_order_id=order.id,
        work_order_number=order.work_order_number,
        status=order.status,
        planned_date=order.planned_date,
    )


def _program_response(
    program: WorkOrderProgram,
    work_order_count: int,
    occurrences: List[WorkOrderProgramOccurrence],
) -> WorkOrderProgramResponse:
    return WorkOrderProgramResponse(
        id=program.id,
        workspace_id=program.workspace_id,
        factory_id=program.factory_id,
        machine_id=program.machine_id,
        work_order_type_id=program.work_order_type_id,
        title=program.title,
        work_order_template_id=program.work_order_template_id,
        cadence=program.cadence,
        interval_days=program.interval_days,
        start_date=program.start_date,
        end_date=program.end_date,
        shift_id=program.shift_id,
        planned_start_time=program.planned_start_time,
        expected_duration_minutes=program.expected_duration_minutes,
        status=program.status,
        created_by=program.created_by,
        created_at=program.created_at,
        work_order_count=work_order_count,
        occurrences=occurrences,
    )


def _responses_with_orders(
    db: Session,
    workspace_id: int,
    programs: List[WorkOrderProgram],
) -> List[WorkOrderProgramResponse]:
    program_ids = [program.id for program in programs]
    counts = work_order_service.program_work_order_counts(
        db, program_ids=program_ids, workspace_id=workspace_id
    )
    grouped: dict[int, List[WorkOrderProgramOccurrence]] = {}
    for order in work_order_service.program_work_orders(
        db, program_ids=program_ids, workspace_id=workspace_id
    ):
        if order.program_id is None:
            continue
        grouped.setdefault(order.program_id, []).append(_occurrence(order))
    return [
        _program_response(program, counts.get(program.id, 0), grouped.get(program.id, []))
        for program in programs
    ]


@router.post(
    "/",
    response_model=WorkOrderProgramResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create work order program",
)
def create_program(
    program_in: WorkOrderProgramCreate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    program = work_order_service.create_work_order_program(
        db,
        data=program_in,
        workspace_id=workspace.id,
        user_id=current_user.id,
    )
    return _responses_with_orders(db, workspace.id, [program])[0]


@router.post(
    "/{program_id}/stop/",
    response_model=WorkOrderProgramResponse,
    status_code=status.HTTP_200_OK,
    summary="Stop work order program",
)
def stop_program(
    program_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    program = work_order_service.stop_work_order_program(
        db, program_id=program_id, workspace_id=workspace.id, user_id=current_user.id
    )
    return _responses_with_orders(db, workspace.id, [program])[0]


@router.get(
    "/",
    response_model=List[WorkOrderProgramResponse],
    status_code=status.HTTP_200_OK,
    summary="List work order programs",
)
def list_programs(
    factory_id: int = Query(..., description="Factory whose programs to list"),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    programs = work_order_service.get_work_order_programs(
        db, workspace_id=workspace.id, factory_id=factory_id
    )
    return _responses_with_orders(db, workspace.id, programs)
