"""
Account Invoice API endpoints

Provides operations for managing account invoices (payables and receivables).
"""
from typing import List, Optional
from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_active_user, get_current_workspace
from app.models.profile import Profile
from app.models.workspace import Workspace
from app.schemas.account_invoice import AccountInvoiceCreate, AccountInvoiceUpdate, AccountInvoiceResponse, VoidInvoiceRequest, InvoiceStatusEntryResponse
from app.services.account_invoice_service import account_invoice_service


router = APIRouter()


@router.get(
    "/",
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
    invoice_number_search: Optional[str] = Query(None, description="Search invoice_number or vendor_invoice_number"),
    account_name_search: Optional[str] = Query(None, description="Search by account name"),
    invoice_date_from: Optional[date] = Query(None, description="Invoice date range start (YYYY-MM-DD)"),
    invoice_date_to: Optional[date] = Query(None, description="Invoice date range end (YYYY-MM-DD)"),
    due_date_from: Optional[date] = Query(None, description="Due date range start (YYYY-MM-DD)"),
    due_date_to: Optional[date] = Query(None, description="Due date range end (YYYY-MM-DD)"),
    amount_min: Optional[Decimal] = Query(None, description="Minimum invoice amount"),
    amount_max: Optional[Decimal] = Query(None, description="Maximum invoice amount"),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Get all invoices in workspace with optional filters. Excludes invoices from deleted accounts."""
    return account_invoice_service.list_invoices(
        db,
        workspace_id=workspace.id,
        account_id=account_id,
        invoice_type=invoice_type,
        payment_status=payment_status,
        invoice_number_search=invoice_number_search,
        account_name_search=account_name_search,
        invoice_date_from=invoice_date_from,
        invoice_date_to=invoice_date_to,
        due_date_from=due_date_from,
        due_date_to=due_date_to,
        amount_min=amount_min,
        amount_max=amount_max,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{invoice_id}/",
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
    return account_invoice_service.get_invoice(
        db,
        invoice_id=invoice_id,
        workspace_id=workspace.id
    )


@router.post(
    "/",
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
    return account_invoice_service.create_invoice(
        db,
        invoice_in=invoice_in,
        workspace_id=workspace.id,
        user_id=current_user.id
    )


@router.put(
    "/{invoice_id}/",
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
    return account_invoice_service.update_invoice(
        db,
        invoice_id=invoice_id,
        invoice_in=invoice_in,
        workspace_id=workspace.id,
        user_id=current_user.id
    )


@router.get(
    "/{invoice_id}/status-history/",
    response_model=List[InvoiceStatusEntryResponse],
    status_code=status.HTTP_200_OK,
    summary="Get invoice status history",
    description="Returns all status transitions for an invoice, oldest first"
)
def get_invoice_status_history(
    invoice_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    return account_invoice_service.get_status_history(
        db, invoice_id=invoice_id, workspace_id=workspace.id
    )


@router.post(
    "/{invoice_id}/confirm/",
    response_model=AccountInvoiceResponse,
    status_code=status.HTTP_200_OK,
    summary="Confirm invoice",
    description="Move invoice from draft to confirmed, enabling payments"
)
def confirm_invoice(
    invoice_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Confirm a draft invoice — enables payment recording"""
    return account_invoice_service.confirm_invoice(
        db, invoice_id=invoice_id, workspace_id=workspace.id, user_id=current_user.id
    )


@router.post(
    "/{invoice_id}/void/",
    response_model=AccountInvoiceResponse,
    status_code=status.HTTP_200_OK,
    summary="Void invoice",
    description="Void a confirmed invoice, auto-voiding all active payments. Irreversible."
)
def void_invoice(
    invoice_id: int,
    void_request: VoidInvoiceRequest,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Void a confirmed invoice and all its active payments"""
    return account_invoice_service.void_invoice(
        db, invoice_id=invoice_id, workspace_id=workspace.id,
        user_id=current_user.id, void_note=void_request.void_note
    )


@router.delete(
    "/{invoice_id}/",
    response_model=AccountInvoiceResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete invoice",
    description="Delete a draft invoice (only while no payments have been recorded)"
)
def delete_invoice(
    invoice_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete an invoice (only if no payments exist)"""
    return account_invoice_service.delete_invoice(
        db,
        invoice_id=invoice_id,
        workspace_id=workspace.id,
        user_id=current_user.id
    )
