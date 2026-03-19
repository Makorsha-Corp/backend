"""
Account Invoice API endpoints

Provides operations for managing account invoices (payables and receivables).
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_active_user, get_current_workspace
from app.models.profile import Profile
from app.models.workspace import Workspace
from app.schemas.account_invoice import AccountInvoiceCreate, AccountInvoiceUpdate, AccountInvoiceResponse
from app.services.account_invoice_service import account_invoice_service


router = APIRouter()


@router.get(
    "",
    response_model=List[AccountInvoiceResponse],
    status_code=status.HTTP_200_OK,
    summary="List all invoices",
    description="Get all invoices in the workspace with optional filters"
)
def get_invoices(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    account_id: Optional[int] = Query(None, description="Filter by account ID"),
    invoice_type: Optional[str] = Query(None, description="Filter by type (payable/receivable)"),
    payment_status: Optional[str] = Query(None, description="Filter by payment status"),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Get all invoices in workspace with optional filters"""
    invoices = account_invoice_service.list_invoices(
        db,
        workspace_id=workspace.id,
        account_id=account_id,
        invoice_type=invoice_type,
        payment_status=payment_status,
        skip=skip,
        limit=limit
    )
    return invoices


@router.get(
    "/{invoice_id}",
    response_model=AccountInvoiceResponse,
    status_code=status.HTTP_200_OK,
    summary="Get invoice by ID",
    description="Get a specific invoice by ID"
)
def get_invoice(
    invoice_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Get a specific invoice"""
    invoice = account_invoice_service.get_invoice(
        db,
        invoice_id=invoice_id,
        workspace_id=workspace.id
    )
    return invoice


@router.post(
    "",
    response_model=AccountInvoiceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new invoice",
    description="Create a new invoice (payable or receivable)"
)
def create_invoice(
    invoice_in: AccountInvoiceCreate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a new invoice"""
    invoice = account_invoice_service.create_invoice(
        db,
        invoice_in=invoice_in,
        workspace_id=workspace.id,
        user_id=current_user.id
    )
    return invoice


@router.put(
    "/{invoice_id}",
    response_model=AccountInvoiceResponse,
    status_code=status.HTTP_200_OK,
    summary="Update invoice",
    description="Update an existing invoice"
)
def update_invoice(
    invoice_id: int,
    invoice_in: AccountInvoiceUpdate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update an invoice"""
    invoice = account_invoice_service.update_invoice(
        db,
        invoice_id=invoice_id,
        invoice_in=invoice_in,
        workspace_id=workspace.id,
        user_id=current_user.id
    )
    return invoice


@router.delete(
    "/{invoice_id}",
    response_model=AccountInvoiceResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete invoice",
    description="Delete an invoice (only if no payments exist)"
)
def delete_invoice(
    invoice_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Delete an invoice (only if no payments exist)"""
    invoice = account_invoice_service.delete_invoice(
        db,
        invoice_id=invoice_id,
        workspace_id=workspace.id
    )
    return invoice
