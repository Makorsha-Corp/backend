"""
Product API endpoints (finished goods)

Provides operations for managing product records and querying ledger.
"""
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_workspace, get_current_active_user
from app.dao.product_ledger import product_ledger_dao
from app.models.production_batch import ProductionBatch as ProductionBatchModel
from app.models.workspace import Workspace
from app.models.profile import Profile
from app.schemas.product import ProductCreate, ProductUpdate, ProductResponse
from app.schemas.product_ledger import ProductLedgerResponse
from app.schemas.production_batch import ProductionBatchResponse
from app.services.product_service import product_service
from app.services.production_batch_service import production_batch_service


router = APIRouter()


class ReceiveFromProductionBatchBody(BaseModel):
    include_byproducts: bool = Field(
        True,
        description="Include byproduct lines when posting quantities.",
    )


def _production_batch_response_with_fg(
    db: Session, workspace_id: int, batch: ProductionBatchModel
) -> ProductionBatchResponse:
    posted = product_ledger_dao.exists_for_production_batch(
        db, workspace_id=workspace_id, batch_id=batch.id
    )
    return ProductionBatchResponse.model_validate(batch).model_copy(
        update={"finished_goods_posted": posted}
    )


@router.get(
    "/",
    response_model=List[ProductResponse],
    status_code=status.HTTP_200_OK,
    summary="List product records",
    description="Get all product records, optionally filtered by factory or availability"
)
def list_products(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    factory_id: Optional[int] = Query(None, description="Filter by factory ID"),
    is_available_for_sale: Optional[bool] = Query(None, description="Filter by sale availability"),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    return product_service.list_products(
        db, workspace_id=workspace.id,
        factory_id=factory_id,
        is_available_for_sale=is_available_for_sale,
        skip=skip, limit=limit
    )


@router.get(
    "/ledger/",
    response_model=List[ProductLedgerResponse],
    status_code=status.HTTP_200_OK,
    summary="List product ledger entries",
    description=(
        "Get ledger entries — all filters optional. Combine `factory_id`, `item_id`, "
        "`start_date`/`end_date`, and `transaction_type` to narrow the result."
    ),
)
def list_ledger(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    factory_id: Optional[int] = Query(None, description="Filter by factory ID"),
    item_id: Optional[int] = Query(None, description="Filter by item ID"),
    start_date: Optional[datetime] = Query(None, description="Start date filter (inclusive)"),
    end_date: Optional[datetime] = Query(None, description="End date filter (inclusive)"),
    transaction_type: Optional[str] = Query(
        None, description="Filter by transaction_type (e.g. 'production', 'manual_add', 'inventory_adjustment')"
    ),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    return product_service.list_ledger(
        db, workspace_id=workspace.id,
        factory_id=factory_id,
        item_id=item_id,
        start_date=start_date,
        end_date=end_date,
        transaction_type=transaction_type,
        skip=skip, limit=limit,
    )


@router.post(
    "/receive-from-batch/{batch_id}/",
    response_model=ProductionBatchResponse,
    status_code=status.HTTP_200_OK,
    summary="Receive production batch into finished goods",
    description=(
        "For a completed batch, post output and optional byproduct quantities to factory products "
        "(same as POST /production-batches/{batch_id}/post-finished-goods/)."
    ),
)
def receive_from_production_batch(
    batch_id: int,
    body: ReceiveFromProductionBatchBody = ReceiveFromProductionBatchBody(),
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    batch = production_batch_service.post_outputs_to_finished_goods(
        db,
        batch_id,
        workspace.id,
        current_user.id,
        include_byproducts=body.include_byproducts,
    )
    return _production_batch_response_with_fg(db, workspace.id, batch)


@router.get(
    "/{prod_id}/",
    response_model=ProductResponse,
    status_code=status.HTTP_200_OK,
    summary="Get product record by ID"
)
def get_product(
    prod_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    return product_service.get_product(db, prod_id=prod_id, workspace_id=workspace.id)


@router.post(
    "/",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create product record"
)
def create_product(
    prod_in: ProductCreate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    return product_service.create_product(
        db, prod_in=prod_in,
        workspace_id=workspace.id, user_id=current_user.id
    )


@router.put(
    "/{prod_id}/",
    response_model=ProductResponse,
    status_code=status.HTTP_200_OK,
    summary="Update product record"
)
def update_product(
    prod_id: int,
    prod_in: ProductUpdate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    return product_service.update_product(
        db, prod_id=prod_id, prod_in=prod_in,
        workspace_id=workspace.id, user_id=current_user.id
    )


@router.delete(
    "/{prod_id}/",
    response_model=ProductResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete product record"
)
def delete_product(
    prod_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    return product_service.delete_product(
        db, prod_id=prod_id,
        workspace_id=workspace.id, user_id=current_user.id
    )
