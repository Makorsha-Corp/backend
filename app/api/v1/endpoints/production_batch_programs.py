"""
Production batch program endpoints.

Create a recurring program, stop one, and list programs for a factory.
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_active_user, get_current_workspace
from app.models.profile import Profile
from app.models.production_batch_program import ProductionBatchProgram
from app.models.workspace import Workspace
from app.models.production_batch import ProductionBatch
from app.schemas.production_batch_program import (
    ProductionBatchProgramCreate,
    ProductionBatchProgramOccurrence,
    ProductionBatchProgramResponse,
)
from app.services.production_batch_service import production_batch_service


router = APIRouter()


def _occurrence(batch: ProductionBatch) -> ProductionBatchProgramOccurrence:
    return ProductionBatchProgramOccurrence(
        batch_id=batch.id,
        batch_number=batch.batch_number,
        status=batch.status,
        planned_start_at=batch.planned_start_at,
    )


def _program_response(
    program: ProductionBatchProgram,
    batch_count: int,
    occurrences: List[ProductionBatchProgramOccurrence],
) -> ProductionBatchProgramResponse:
    return ProductionBatchProgramResponse(
        id=program.id,
        workspace_id=program.workspace_id,
        factory_id=program.factory_id,
        formula_id=program.formula_id,
        first_start_at=program.first_start_at,
        cadence=program.cadence,
        interval_days=program.interval_days,
        end_date=program.end_date,
        status=program.status,
        created_by=program.created_by,
        created_at=program.created_at,
        batch_count=batch_count,
        occurrences=occurrences,
    )


def _responses_with_counts(
    db: Session,
    workspace_id: int,
    programs: List[ProductionBatchProgram],
) -> List[ProductionBatchProgramResponse]:
    program_ids = [program.id for program in programs]
    counts = production_batch_service.program_batch_counts(
        db,
        program_ids=program_ids,
        workspace_id=workspace_id,
    )
    grouped: dict[int, List[ProductionBatchProgramOccurrence]] = {}
    for batch in production_batch_service.program_batches(
        db,
        program_ids=program_ids,
        workspace_id=workspace_id,
    ):
        if batch.program_id is None:
            continue
        grouped.setdefault(batch.program_id, []).append(_occurrence(batch))
    return [
        _program_response(program, counts.get(program.id, 0), grouped.get(program.id, []))
        for program in programs
    ]


@router.post(
    "/",
    response_model=ProductionBatchProgramResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create production batch program",
    description="""
    Create a recurring program and one draft batch per occurrence.
    Returns the program plus batch_count.
    """,
)
def create_program(
    program_in: ProductionBatchProgramCreate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Create a program and its draft batches."""
    program = production_batch_service.create_program(
        db,
        factory_id=program_in.factory_id,
        formula_id=program_in.formula_id,
        first_start_at=program_in.first_start_at,
        cadence=program_in.cadence,
        interval_days=program_in.interval_days,
        end_date=program_in.end_date,
        workspace_id=workspace.id,
        user_id=current_user.id,
    )
    return _responses_with_counts(db, workspace.id, [program])[0]


@router.post(
    "/{program_id}/stop/",
    response_model=ProductionBatchProgramResponse,
    status_code=status.HTTP_200_OK,
    summary="Stop production batch program",
    description="Stop a program and cancel its draft batches.",
)
def stop_program(
    program_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Stop a program."""
    program = production_batch_service.stop_program(
        db, program_id, workspace.id, current_user.id
    )
    return _responses_with_counts(db, workspace.id, [program])[0]


@router.get(
    "/",
    response_model=List[ProductionBatchProgramResponse],
    status_code=status.HTTP_200_OK,
    summary="List production batch programs",
    description="Programs for one factory in the current workspace.",
)
def get_programs(
    factory_id: Optional[int] = Query(None, description="Optional factory scope"),
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """List programs for a factory in this workspace."""
    programs = production_batch_service.get_programs(
        db, workspace_id=workspace.id, factory_id=factory_id
    )
    return _responses_with_counts(db, workspace.id, programs)
