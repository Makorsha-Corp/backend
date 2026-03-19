"""
Invoice Payment API endpoints

Provides operations for managing invoice payments.
"""
from typing import List
from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_active_user, get_current_workspace
from app.models.profile import Profile
from app.models.workspace import Workspace
from app.schemas.invoice_payment import InvoicePaymentCreate, InvoicePaymentUpdate, InvoicePaymentResponse
from app.services.invoice_payment_service import invoice_payment_service


router = APIRouter()


@router.get(
    "/invoice/{invoice_id}",
    response_model=List[InvoicePaymentResponse],
    status_code=status.HTTP_200_OK,
    summary="List payments for an invoice",
    description="Get all payments for a specific invoice"
)
def get_payments_by_invoice(
    invoice_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Get all payments for an invoice"""
    payments = invoice_payment_service.list_payments_by_invoice(
        db,
        invoice_id=invoice_id,
        workspace_id=workspace.id,
        skip=skip,
        limit=limit
    )
    return payments


@router.get(
    "/{payment_id}",
    response_model=InvoicePaymentResponse,
    status_code=status.HTTP_200_OK,
    summary="Get payment by ID",
    description="Get a specific payment by ID"
)
def get_payment(
    payment_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Get a specific payment"""
    payment = invoice_payment_service.get_payment(
        db,
        payment_id=payment_id,
        workspace_id=workspace.id
    )
    return payment


@router.post(
    "/",
    response_model=InvoicePaymentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new payment",
    description="Create a new payment for an invoice (automatically updates invoice status)"
)
def create_payment(
    payment_in: InvoicePaymentCreate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a new payment (automatically updates invoice status)"""
    payment = invoice_payment_service.create_payment(
        db,
        payment_in=payment_in,
        workspace_id=workspace.id,
        user_id=current_user.id
    )
    return payment


@router.put(
    "/{payment_id}",
    response_model=InvoicePaymentResponse,
    status_code=status.HTTP_200_OK,
    summary="Update payment",
    description="Update payment metadata (cannot change payment amount)"
)
def update_payment(
    payment_id: int,
    payment_in: InvoicePaymentUpdate,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Update payment metadata (cannot change payment amount)"""
    payment = invoice_payment_service.update_payment(
        db,
        payment_id=payment_id,
        payment_in=payment_in,
        workspace_id=workspace.id
    )
    return payment


@router.delete(
    "/{payment_id}",
    response_model=InvoicePaymentResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete payment",
    description="Delete a payment (automatically recalculates invoice totals)"
)
def delete_payment(
    payment_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Delete a payment (automatically recalculates invoice totals)"""
    payment = invoice_payment_service.delete_payment(
        db,
        payment_id=payment_id,
        workspace_id=workspace.id
    )
    return payment
