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
    ProductionFormulaUpdate,
    ProductionFormulaResponse,
)
from app.schemas.production_formula_item import (
    ProductionFormulaItemCreate,
    ProductionFormulaItemUpdate,
    ProductionFormulaItemResponse,
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
    "/{formula_id}",
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


@router.put(
    "/{formula_id}",
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
    "/{formula_id}",
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
    production_formula_service.delete_formula(db, formula_id, workspace.id)


# ─── Formula Item Endpoints ─────────────────────────────────────────


@router.get(
    "/{formula_id}/items",
    response_model=List[ProductionFormulaItemResponse],
    status_code=status.HTTP_200_OK,
    summary="List formula items",
    description="""
    Get all items for a production formula.
    Optionally filter by item_role (input, output, waste, byproduct).
    """,
)
def get_formula_items(
    formula_id: int,
    item_role: Optional[str] = Query(
        None,
        description="Filter by item role: input, output, waste, byproduct",
        pattern=r'^(input|output|waste|byproduct)$'
    ),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    """Get all items for a formula"""
    return production_formula_service.get_formula_items(
        db, formula_id, workspace_id=workspace.id, item_role=item_role
    )


@router.post(
    "/{formula_id}/items",
    response_model=ProductionFormulaItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add item to formula",
    description="""
    Add an item to a production formula.
    item_role must be one of: input, output, waste, byproduct.
    The item must exist and belong to the same workspace.
    """,
)
def add_formula_item(
    formula_id: int,
    item_in: ProductionFormulaItemCreate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Add an item to a formula"""
    # Ensure the formula_id in the path matches the body
    if item_in.formula_id != formula_id:
        from app.core.exceptions import BusinessRuleError
        raise BusinessRuleError(
            f"Path formula_id ({formula_id}) does not match body formula_id ({item_in.formula_id})"
        )
    return production_formula_service.add_formula_item(
        db, item_in, workspace.id
    )


@router.put(
    "/items/{formula_item_id}",
    response_model=ProductionFormulaItemResponse,
    status_code=status.HTTP_200_OK,
    summary="Update formula item",
    description="Update a formula item (quantity, role, tolerance, etc.).",
)
def update_formula_item(
    formula_item_id: int,
    item_in: ProductionFormulaItemUpdate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Update a formula item"""
    return production_formula_service.update_formula_item(
        db, formula_item_id, item_in, workspace.id
    )


@router.delete(
    "/items/{formula_item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove item from formula",
    description="Remove an item from a formula (hard delete). Returns 204 on success.",
)
def remove_formula_item(
    formula_item_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Remove an item from a formula"""
    production_formula_service.remove_formula_item(db, formula_item_id, workspace.id)
