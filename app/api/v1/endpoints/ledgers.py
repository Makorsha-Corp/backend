"""
Ledger endpoints

Provides read-only access to all 5 ledger types:
- Storage Item Ledger
- Machine Item Ledger
- Damaged Item Ledger
- Project Component Item Ledger
- Inventory Ledger (Finished Goods)

Also provides reconciliation and cross-ledger reporting endpoints.
"""
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, Query, status, Path
from sqlalchemy.orm import Session
from datetime import datetime

from app.core.deps import get_db, get_current_active_user, get_current_workspace
from app.models.profile import Profile
from app.models.workspace import Workspace
from app.schemas.storage_item_ledger import StorageItemLedgerResponse
from app.schemas.machine_item_ledger import MachineItemLedgerResponse
from app.schemas.damaged_item_ledger import DamagedItemLedgerResponse
from app.schemas.project_component_item_ledger import ProjectComponentItemLedgerResponse
from app.schemas.inventory_ledger import InventoryLedgerResponse
from app.schemas.response import ActionResponse
from app.services.ledger_service import ledger_service


router = APIRouter()


# ============================================================================
# STORAGE LEDGER ENDPOINTS
# ============================================================================

@router.get(
    "/storage",
    response_model=List[StorageItemLedgerResponse],
    status_code=status.HTTP_200_OK,
    summary="Get storage ledger entries",
    description="Query storage item ledger with filters (factory, item, date range, transaction type)"
)
def get_storage_ledger(
    factory_id: int = Query(..., description="Factory ID"),
    item_id: int = Query(..., description="Item ID"),
    start_date: Optional[datetime] = Query(None, description="Start date filter (ISO format)"),
    end_date: Optional[datetime] = Query(None, description="End date filter (ISO format)"),
    transaction_type: Optional[str] = Query(None, description="Transaction type filter"),
    skip: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(100, le=100, description="Pagination limit"),
    db: Session = Depends(get_db),
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user)
):
    """
    Get storage ledger entries with optional filters.

    Returns list of ledger transactions ordered by date (newest first).
    """
    entries = ledger_service.get_storage_ledger(
        db=db,
        factory_id=factory_id,
        item_id=item_id,
        workspace_id=workspace.id,
        start_date=start_date,
        end_date=end_date,
        transaction_type=transaction_type,
        skip=skip,
        limit=limit
    )
    return entries


@router.get(
    "/storage/balance",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Get storage balance",
    description="Calculate current storage balance from ledger (source of truth)"
)
def get_storage_balance(
    factory_id: int = Query(..., description="Factory ID"),
    item_id: int = Query(..., description="Item ID"),
    db: Session = Depends(get_db),
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user)
):
    """
    Calculate current storage balance from ledger.

    Returns: {factory_id, item_id, quantity, total_value}
    """
    balance = ledger_service.get_storage_balance(
        db=db,
        factory_id=factory_id,
        item_id=item_id,
        workspace_id=workspace.id
    )
    return balance


@router.post(
    "/storage/reconcile",
    response_model=ActionResponse[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Reconcile storage inventory",
    description="""
    Compare storage ledger (source of truth) vs snapshot table.
    If discrepancy found, creates adjustment transaction and updates snapshot.

    Returns reconciliation result with messages about what happened.
    """
)
def reconcile_storage_item(
    factory_id: int = Query(..., description="Factory ID"),
    item_id: int = Query(..., description="Item ID"),
    db: Session = Depends(get_db),
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user)
):
    """
    Reconcile storage inventory.

    Backend performs:
    1. Compare ledger balance vs storage_items snapshot
    2. If mismatch, create adjustment transaction
    3. Update snapshot to match ledger

    Returns result + messages about what happened.
    """
    result, messages = ledger_service.reconcile_storage_item(
        db=db,
        factory_id=factory_id,
        item_id=item_id,
        workspace_id=workspace.id,
        current_user=current_user
    )

    return ActionResponse(data=result, messages=messages)


# ============================================================================
# MACHINE LEDGER ENDPOINTS
# ============================================================================

@router.get(
    "/machine",
    response_model=List[MachineItemLedgerResponse],
    status_code=status.HTTP_200_OK,
    summary="Get machine ledger entries",
    description="Query machine item ledger with filters"
)
def get_machine_ledger(
    machine_id: int = Query(..., description="Machine ID"),
    item_id: int = Query(..., description="Item ID"),
    start_date: Optional[datetime] = Query(None, description="Start date filter"),
    end_date: Optional[datetime] = Query(None, description="End date filter"),
    transaction_type: Optional[str] = Query(None, description="Transaction type filter"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=100),
    db: Session = Depends(get_db),
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user)
):
    """Get machine ledger entries with optional filters."""
    entries = ledger_service.get_machine_ledger(
        db=db,
        machine_id=machine_id,
        item_id=item_id,
        workspace_id=workspace.id,
        start_date=start_date,
        end_date=end_date,
        transaction_type=transaction_type,
        skip=skip,
        limit=limit
    )
    return entries


@router.get(
    "/machine/balance",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Get machine balance",
    description="Calculate current machine balance from ledger"
)
def get_machine_balance(
    machine_id: int = Query(..., description="Machine ID"),
    item_id: int = Query(..., description="Item ID"),
    db: Session = Depends(get_db),
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user)
):
    """Calculate current machine balance from ledger."""
    balance = ledger_service.get_machine_balance(
        db=db,
        machine_id=machine_id,
        item_id=item_id,
        workspace_id=workspace.id
    )
    return balance


@router.post(
    "/machine/reconcile",
    response_model=ActionResponse[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Reconcile machine inventory",
    description="Compare machine ledger vs snapshot and fix discrepancies"
)
def reconcile_machine_item(
    machine_id: int = Query(..., description="Machine ID"),
    item_id: int = Query(..., description="Item ID"),
    db: Session = Depends(get_db),
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user)
):
    """Reconcile machine inventory."""
    result, messages = ledger_service.reconcile_machine_item(
        db=db,
        machine_id=machine_id,
        item_id=item_id,
        workspace_id=workspace.id,
        current_user=current_user
    )

    return ActionResponse(data=result, messages=messages)


# ============================================================================
# DAMAGED LEDGER ENDPOINTS
# ============================================================================

@router.get(
    "/damaged",
    response_model=List[DamagedItemLedgerResponse],
    status_code=status.HTTP_200_OK,
    summary="Get damaged items ledger entries",
    description="Query damaged items ledger with filters"
)
def get_damaged_ledger(
    factory_id: int = Query(..., description="Factory ID"),
    item_id: int = Query(..., description="Item ID"),
    start_date: Optional[datetime] = Query(None, description="Start date filter"),
    end_date: Optional[datetime] = Query(None, description="End date filter"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=100),
    db: Session = Depends(get_db),
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user)
):
    """Get damaged items ledger entries with optional filters."""
    entries = ledger_service.get_damaged_ledger(
        db=db,
        factory_id=factory_id,
        item_id=item_id,
        workspace_id=workspace.id,
        start_date=start_date,
        end_date=end_date,
        skip=skip,
        limit=limit
    )
    return entries


@router.get(
    "/damaged/balance",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Get damaged items balance",
    description="Calculate current damaged items balance from ledger"
)
def get_damaged_balance(
    factory_id: int = Query(..., description="Factory ID"),
    item_id: int = Query(..., description="Item ID"),
    db: Session = Depends(get_db),
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user)
):
    """Calculate current damaged items balance from ledger."""
    balance = ledger_service.get_damaged_balance(
        db=db,
        factory_id=factory_id,
        item_id=item_id,
        workspace_id=workspace.id
    )
    return balance


@router.post(
    "/damaged/reconcile",
    response_model=ActionResponse[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Reconcile damaged inventory",
    description="Compare damaged ledger vs snapshot and fix discrepancies"
)
def reconcile_damaged_item(
    factory_id: int = Query(..., description="Factory ID"),
    item_id: int = Query(..., description="Item ID"),
    db: Session = Depends(get_db),
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user)
):
    """Reconcile damaged inventory."""
    result, messages = ledger_service.reconcile_damaged_item(
        db=db,
        factory_id=factory_id,
        item_id=item_id,
        workspace_id=workspace.id,
        current_user=current_user
    )

    return ActionResponse(data=result, messages=messages)


# ============================================================================
# PROJECT COMPONENT LEDGER ENDPOINTS
# ============================================================================

@router.get(
    "/project-component",
    response_model=List[ProjectComponentItemLedgerResponse],
    status_code=status.HTTP_200_OK,
    summary="Get project component ledger entries",
    description="Query project component item consumption ledger"
)
def get_project_component_ledger(
    project_component_id: int = Query(..., description="Project component ID"),
    item_id: Optional[int] = Query(None, description="Optional item ID filter"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=100),
    db: Session = Depends(get_db),
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user)
):
    """Get project component consumption ledger entries."""
    entries = ledger_service.get_project_component_ledger(
        db=db,
        project_component_id=project_component_id,
        workspace_id=workspace.id,
        item_id=item_id,
        skip=skip,
        limit=limit
    )
    return entries


@router.get(
    "/project-component/{project_component_id}/total-cost",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Get project component total cost",
    description="Calculate total cost of all items consumed by project component"
)
def get_project_component_total_cost(
    project_component_id: int = Path(..., description="Project component ID"),
    db: Session = Depends(get_db),
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user)
):
    """
    Calculate total cost of all items consumed by project component.

    Used for project budgeting and cost tracking.
    """
    cost_data = ledger_service.get_project_component_total_cost(
        db=db,
        project_component_id=project_component_id,
        workspace_id=workspace.id
    )
    return cost_data


# ============================================================================
# INVENTORY LEDGER (Finished Goods) ENDPOINTS
# ============================================================================

@router.get(
    "/inventory",
    response_model=List[InventoryLedgerResponse],
    status_code=status.HTTP_200_OK,
    summary="Get inventory ledger entries",
    description="Query finished goods inventory ledger with filters"
)
def get_inventory_ledger(
    factory_id: int = Query(..., description="Factory ID"),
    item_id: int = Query(..., description="Item ID"),
    start_date: Optional[datetime] = Query(None, description="Start date filter"),
    end_date: Optional[datetime] = Query(None, description="End date filter"),
    transaction_type: Optional[str] = Query(None, description="Transaction type filter"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=100),
    db: Session = Depends(get_db),
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user)
):
    """Get finished goods inventory ledger entries with optional filters."""
    entries = ledger_service.get_inventory_ledger(
        db=db,
        factory_id=factory_id,
        item_id=item_id,
        workspace_id=workspace.id,
        start_date=start_date,
        end_date=end_date,
        transaction_type=transaction_type,
        skip=skip,
        limit=limit
    )
    return entries


@router.get(
    "/inventory/balance",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Get inventory balance",
    description="Calculate current finished goods balance from ledger"
)
def get_inventory_balance(
    factory_id: int = Query(..., description="Factory ID"),
    item_id: int = Query(..., description="Item ID"),
    db: Session = Depends(get_db),
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user)
):
    """Calculate current finished goods balance from ledger."""
    balance = ledger_service.get_inventory_balance(
        db=db,
        factory_id=factory_id,
        item_id=item_id,
        workspace_id=workspace.id
    )
    return balance


@router.post(
    "/inventory/reconcile",
    response_model=ActionResponse[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Reconcile finished goods inventory",
    description="Compare inventory ledger vs snapshot and fix discrepancies"
)
def reconcile_inventory(
    factory_id: int = Query(..., description="Factory ID"),
    item_id: int = Query(..., description="Item ID"),
    db: Session = Depends(get_db),
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user)
):
    """Reconcile finished goods inventory."""
    result, messages = ledger_service.reconcile_inventory(
        db=db,
        factory_id=factory_id,
        item_id=item_id,
        workspace_id=workspace.id,
        current_user=current_user
    )

    return ActionResponse(data=result, messages=messages)


# ============================================================================
# CROSS-LEDGER REPORTING ENDPOINTS
# ============================================================================

@router.get(
    "/reports/item-movement/{item_id}",
    response_model=Dict[str, List],
    status_code=status.HTTP_200_OK,
    summary="Get item movement summary",
    description="""
    Track item movement across ALL ledgers.

    Shows item journey: Purchase -> Storage -> Machine -> Production -> Inventory -> Sales
    """
)
def get_item_movement_summary(
    item_id: int = Path(..., description="Item ID"),
    start_date: Optional[datetime] = Query(None, description="Start date filter"),
    end_date: Optional[datetime] = Query(None, description="End date filter"),
    db: Session = Depends(get_db),
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user)
):
    """
    Get item movement across all ledgers.

    Returns dictionary with entries from all 5 ledgers:
    {
        'storage': [...],
        'machine': [...],
        'damaged': [...],
        'project': [...],
        'inventory': [...]
    }
    """
    summary = ledger_service.get_item_movement_summary(
        db=db,
        item_id=item_id,
        workspace_id=workspace.id,
        start_date=start_date,
        end_date=end_date
    )
    return summary


@router.get(
    "/reports/user-transactions/{user_id}",
    response_model=Dict[str, List],
    status_code=status.HTTP_200_OK,
    summary="Get user transactions",
    description="Get all transactions performed by a user across all ledgers (audit trail)"
)
def get_transactions_by_user(
    user_id: int = Path(..., description="User ID"),
    start_date: Optional[datetime] = Query(None, description="Start date filter"),
    end_date: Optional[datetime] = Query(None, description="End date filter"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=100),
    db: Session = Depends(get_db),
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user)
):
    """
    Get all transactions performed by a user across all ledgers.

    Useful for:
    - User activity audit
    - Performance tracking
    - Error investigation
    """
    transactions = ledger_service.get_transactions_by_user(
        db=db,
        user_id=user_id,
        workspace_id=workspace.id,
        start_date=start_date,
        end_date=end_date,
        skip=skip,
        limit=limit
    )
    return transactions


@router.get(
    "/reports/order-transactions/{order_id}",
    response_model=Dict[str, List],
    status_code=status.HTTP_200_OK,
    summary="Get order transactions",
    description="Get all ledger entries related to an order across all ledgers"
)
def get_transactions_by_order(
    order_id: int = Path(..., description="Order ID"),
    db: Session = Depends(get_db),
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user)
):
    """
    Get all ledger entries related to an order.

    Shows complete inventory impact of an order across all ledgers.
    """
    transactions = ledger_service.get_transactions_by_order(
        db=db,
        order_id=order_id,
        workspace_id=workspace.id
    )
    return transactions
