"""Invoice items CRUD endpoints — draft invoices only."""
from typing import List
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_active_user, get_current_workspace
from app.managers.account_invoice_manager import account_invoice_manager
from app.dao.invoice_item import invoice_item_dao
from app.schemas.invoice_item import InvoiceItemCreate, InvoiceItemUpdate, InvoiceItemResponse
from app.models.profile import Profile
from app.models.workspace import Workspace

router = APIRouter(tags=["invoice-items"])


def _get_draft_invoice(db: Session, invoice_id: int, workspace_id: int):
    invoice = account_invoice_manager.get_invoice(db, invoice_id, workspace_id)
    if invoice.invoice_status != "draft":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invoice items can only be modified on draft invoices (current status: '{invoice.invoice_status}').",
        )
    return invoice


@router.get("/", response_model=List[InvoiceItemResponse])
def list_invoice_items(
    invoice_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    account_invoice_manager.get_invoice(db, invoice_id, workspace.id)
    return invoice_item_dao.get_by_invoice(db, invoice_id=invoice_id, workspace_id=workspace.id)


@router.get("/{item_id}/", response_model=InvoiceItemResponse)
def get_invoice_item(
    item_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    item = invoice_item_dao.get_by_id_and_workspace(db, id=item_id, workspace_id=workspace.id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice item not found")
    return item


@router.post("/", response_model=InvoiceItemResponse, status_code=status.HTTP_201_CREATED)
def create_invoice_item(
    item_in: InvoiceItemCreate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    invoice = _get_draft_invoice(db, item_in.invoice_id, workspace.id)

    item_dict = item_in.model_dump()
    item_dict["workspace_id"] = workspace.id
    item_dict["created_by"] = current_user.id

    item = invoice_item_dao.create(db, obj_in=item_dict)
    db.flush()

    account_invoice_manager._recalculate_invoice_amount(db, invoice)
    account_invoice_manager._log_event(
        db, invoice, "item_manually_updated",
        f"Item '{item.description}' added manually to invoice",
        performed_by=current_user.id,
        metadata={"item_id": item.id, "line_subtotal": str(item.line_subtotal)},
    )
    db.commit()
    db.refresh(item)
    return item


@router.put("/{item_id}/", response_model=InvoiceItemResponse)
def update_invoice_item(
    item_id: int,
    item_in: InvoiceItemUpdate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    item = invoice_item_dao.get_by_id_and_workspace(db, id=item_id, workspace_id=workspace.id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice item not found")

    invoice = _get_draft_invoice(db, item.invoice_id, workspace.id)

    update_dict = item_in.model_dump(exclude_unset=True, exclude_none=True)

    if "quantity" in update_dict or "unit_price" in update_dict:
        qty = Decimal(str(update_dict.get("quantity", item.quantity)))
        price = Decimal(str(update_dict.get("unit_price", item.unit_price)))
        if "line_subtotal" not in update_dict:
            update_dict["line_subtotal"] = qty * price

    updated_item = invoice_item_dao.update(db, db_obj=item, obj_in=update_dict)
    db.flush()

    account_invoice_manager._recalculate_invoice_amount(db, invoice)
    account_invoice_manager._log_event(
        db, invoice, "item_manually_updated",
        f"Item '{updated_item.description}' updated manually on invoice",
        performed_by=current_user.id,
    )
    db.commit()
    db.refresh(updated_item)
    return updated_item


@router.delete("/{item_id}/", status_code=status.HTTP_204_NO_CONTENT)
def delete_invoice_item(
    item_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    item = invoice_item_dao.get_by_id_and_workspace(db, id=item_id, workspace_id=workspace.id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice item not found")

    invoice = _get_draft_invoice(db, item.invoice_id, workspace.id)
    desc = item.description

    invoice_item_dao.remove(db, id=item_id)
    db.flush()

    account_invoice_manager._recalculate_invoice_amount(db, invoice)
    account_invoice_manager._log_event(
        db, invoice, "item_manually_updated",
        f"Item '{desc}' removed manually from invoice",
        performed_by=current_user.id,
    )
    db.commit()
