"""
Production Formula endpoints

Provides CRUD operations for production formulas and their items.
Formulas define the recipe/BOM (Bill of Materials) for production,
specifying inputs, outputs, waste, and byproducts.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_active_user, get_current_workspace
from app.models.profile import Profile
from app.models.workspace import Workspace
from app.schemas.production_formula import (
    ProductionFormulaCreate,
    ProductionFormulaCopy,
    ProductionFormulaUpdate,
    ProductionFormulaResponse,
)
from app.schemas.production_formula_stage import (
    RecipeRouteStepAdd,
    ProductionFormulaStageCreate,
    ProductionFormulaStageUpdate,
    ProductionFormulaStageResponse,
)
from app.schemas.production_formula_stage_item import (
    ProductionFormulaStageItemAddBody,
    ProductionFormulaStageItemCreate,
    ProductionFormulaStageItemUpdate,
    ProductionFormulaStageItemResponse,
)
from app.schemas.production_formula_stage_parameter import (
    ProductionFormulaStageParameterAddBody,
    ProductionFormulaStageParameterCreate,
    ProductionFormulaStageParameterUpdate,
    ProductionFormulaStageParameterResponse,
)
from app.services.production_formula_service import production_formula_service


router = APIRouter()


# ─── Formula Endpoints ──────────────────────────────────────────────


@router.get(
    "/",
    response_model=List[ProductionFormulaResponse],
    status_code=status.HTTP_200_OK,
    summary="List production formulas",
    description="""
    Get all production formulas with optional filtering by active status.
    Supports pagination with skip/limit.
    """,
)
def get_formulas(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, le=100, description="Maximum number of records to return"),
    active_only: bool = Query(False, description="Only return active formulas"),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    """Get all production formulas with optional filters"""
    return production_formula_service.get_formulas(
        db,
        workspace_id=workspace.id,
        active_only=active_only,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{formula_id}/",
    response_model=ProductionFormulaResponse,
    status_code=status.HTTP_200_OK,
    summary="Get production formula by ID",
    description="Retrieve a single production formula by its ID. Raises 404 if not found.",
)
def get_formula(
    formula_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    """Get production formula by ID"""
    return production_formula_service.get_formula(
        db, formula_id, workspace_id=workspace.id
    )


@router.post(
    "/",
    response_model=ProductionFormulaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create production formula",
    description="""
    Create a new production formula (recipe/BOM).
    Requires a unique formula_code within the workspace.
    If is_default=True, clears default flag on other formulas.
    Add formula items (input, output, waste, byproduct) after creation.
    """,
)
def create_formula(
    formula_in: ProductionFormulaCreate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Create new production formula"""
    return production_formula_service.create_formula(
        db, formula_in, workspace.id, current_user.id
    )


@router.post(
    "/{formula_id}/copy/",
    response_model=ProductionFormulaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Copy a recipe",
    description="Duplicate private path, stages, and stage materials into a new recipe.",
)
def copy_formula(
    formula_id: int,
    copy_in: ProductionFormulaCopy,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return production_formula_service.duplicate_formula(
        db, formula_id, copy_in, workspace.id, current_user.id
    )


@router.put(
    "/{formula_id}/",
    response_model=ProductionFormulaResponse,
    status_code=status.HTTP_200_OK,
    summary="Update production formula",
    description="Update an existing production formula. Returns the updated formula.",
)
def update_formula(
    formula_id: int,
    formula_in: ProductionFormulaUpdate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Update production formula"""
    return production_formula_service.update_formula(
        db, formula_id, formula_in, workspace.id, current_user.id
    )


@router.delete(
    "/{formula_id}/",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete production formula",
    description="Soft delete a production formula (sets is_active=False). Returns 204 on success.",
)
def delete_formula(
    formula_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Delete production formula (soft delete)"""
    production_formula_service.delete_formula(db, formula_id, workspace.id, current_user.id)


# ─── Formula Stage Endpoints ────────────────────────────────────────


@router.post(
    "/{formula_id}/route-steps/",
    response_model=ProductionFormulaStageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a line step on this recipe's route",
)
def add_recipe_route_step(
    formula_id: int,
    body: RecipeRouteStepAdd,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return production_formula_service.append_line_step(
        db,
        formula_id,
        body.production_line_id,
        workspace.id,
        current_user.id,
        name=body.name,
        factory_id=body.factory_id,
    )


@router.get(
    "/{formula_id}/stages/",
    response_model=List[ProductionFormulaStageResponse],
    status_code=status.HTTP_200_OK,
    summary="List formula production stages",
)
def get_formula_stages(
    formula_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    return production_formula_service.get_formula_stages(db, formula_id, workspace.id)


@router.post(
    "/{formula_id}/stages/",
    response_model=ProductionFormulaStageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add stage to formula",
)
def add_formula_stage(
    formula_id: int,
    stage_in: ProductionFormulaStageCreate,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    if stage_in.formula_id != formula_id:
        from app.core.exceptions import BusinessRuleError
        raise BusinessRuleError(
            f"Path formula_id ({formula_id}) does not match body formula_id ({stage_in.formula_id})"
        )
    return production_formula_service.add_formula_stage(db, stage_in, workspace.id)


@router.put(
    "/stages/{stage_id}/",
    response_model=ProductionFormulaStageResponse,
    status_code=status.HTTP_200_OK,
    summary="Update formula stage",
)
def update_formula_stage(
    stage_id: int,
    stage_in: ProductionFormulaStageUpdate,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    return production_formula_service.update_formula_stage(db, stage_id, stage_in, workspace.id)


@router.delete(
    "/stages/{stage_id}/",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove formula stage",
)
def remove_formula_stage(
    stage_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    production_formula_service.remove_formula_stage(db, stage_id, workspace.id)


# ─── Formula stage item endpoints ───────────────────────────────────


@router.get(
    "/{formula_id}/stage-items/",
    response_model=List[ProductionFormulaStageItemResponse],
    status_code=status.HTTP_200_OK,
    summary="List all stage items for a formula",
)
def get_all_formula_stage_items(
    formula_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    return production_formula_service.get_all_formula_stage_items(db, formula_id, workspace.id)


@router.get(
    "/{formula_id}/stages/{stage_id}/items/",
    response_model=List[ProductionFormulaStageItemResponse],
    status_code=status.HTTP_200_OK,
    summary="List items for a formula stage",
)
def get_formula_stage_items(
    formula_id: int,
    stage_id: int,
    item_role: Optional[str] = Query(
        None,
        pattern=r"^(input|output|waste|byproduct)$",
    ),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    return production_formula_service.get_formula_stage_items(
        db, formula_id, stage_id, workspace.id, item_role=item_role
    )


@router.post(
    "/{formula_id}/stages/{stage_id}/items/",
    response_model=ProductionFormulaStageItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add item to formula stage",
)
def add_formula_stage_item(
    formula_id: int,
    stage_id: int,
    item_in: ProductionFormulaStageItemAddBody,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    create_in = ProductionFormulaStageItemCreate(
        formula_stage_id=stage_id,
        **item_in.model_dump(),
    )
    return production_formula_service.add_formula_stage_item(
        db, formula_id, stage_id, create_in, workspace.id, user_id=current_user.id
    )


@router.post(
    "/{formula_id}/stages/{stage_id}/ensure-input-handoff/",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Copy previous step outputs into this step's inputs when missing",
)
def ensure_input_handoff_from_previous_stage(
    formula_id: int,
    stage_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    production_formula_service.ensure_input_handoff_from_previous_stage(
        db, formula_id, stage_id, workspace.id
    )


@router.put(
    "/stage-items/{stage_item_id}/",
    response_model=ProductionFormulaStageItemResponse,
    status_code=status.HTTP_200_OK,
    summary="Update formula stage item",
)
def update_formula_stage_item(
    stage_item_id: int,
    item_in: ProductionFormulaStageItemUpdate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return production_formula_service.update_formula_stage_item(
        db, stage_item_id, item_in, workspace.id
    )


@router.delete(
    "/stage-items/{stage_item_id}/",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove formula stage item",
)
def remove_formula_stage_item(
    stage_item_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    production_formula_service.remove_formula_stage_item(db, stage_item_id, workspace.id)


# ─── Formula stage parameter endpoints ──────────────────────────────


@router.get(
    "/{formula_id}/stage-parameters/",
    response_model=List[ProductionFormulaStageParameterResponse],
    status_code=status.HTTP_200_OK,
    summary="List all stage parameters for a formula",
)
def get_all_formula_stage_parameters(
    formula_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    return production_formula_service.get_all_formula_stage_parameters(
        db, formula_id, workspace.id
    )


@router.get(
    "/{formula_id}/stages/{stage_id}/parameters/",
    response_model=List[ProductionFormulaStageParameterResponse],
    status_code=status.HTTP_200_OK,
    summary="List conditions for a formula stage",
)
def get_formula_stage_parameters(
    formula_id: int,
    stage_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    return production_formula_service.get_formula_stage_parameters(
        db, formula_id, stage_id, workspace.id
    )


@router.post(
    "/{formula_id}/stages/{stage_id}/parameters/",
    response_model=ProductionFormulaStageParameterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add condition to formula stage",
)
def add_formula_stage_parameter(
    formula_id: int,
    stage_id: int,
    param_in: ProductionFormulaStageParameterAddBody,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    create_in = ProductionFormulaStageParameterCreate(
        formula_stage_id=stage_id,
        **param_in.model_dump(),
    )
    return production_formula_service.add_formula_stage_parameter(
        db, formula_id, stage_id, create_in, workspace.id
    )


@router.put(
    "/stage-parameters/{parameter_id}/",
    response_model=ProductionFormulaStageParameterResponse,
    status_code=status.HTTP_200_OK,
    summary="Update formula stage condition",
)
def update_formula_stage_parameter(
    parameter_id: int,
    param_in: ProductionFormulaStageParameterUpdate,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    return production_formula_service.update_formula_stage_parameter(
        db, parameter_id, param_in, workspace.id
    )


@router.delete(
    "/stage-parameters/{parameter_id}/",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove formula stage condition",
)
def remove_formula_stage_parameter(
    parameter_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    production_formula_service.remove_formula_stage_parameter(
        db, parameter_id, workspace.id
    )
