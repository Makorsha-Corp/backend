"""Invoice item DAO"""
from typing import List, Optional
from sqlalchemy.orm import Session

from app.dao.base import BaseDAO
from app.models.invoice_item import InvoiceItem
from app.schemas.invoice_item import InvoiceItemCreate, InvoiceItemUpdate


class InvoiceItemDAO(BaseDAO[InvoiceItem, InvoiceItemCreate, InvoiceItemUpdate]):

    def get_by_invoice(self, db: Session, *, invoice_id: int, workspace_id: int) -> List[InvoiceItem]:
        return (
            db.query(InvoiceItem)
            .filter(InvoiceItem.invoice_id == invoice_id, InvoiceItem.workspace_id == workspace_id)
            .order_by(InvoiceItem.line_number)
            .all()
        )

    def get_by_id_and_workspace(self, db: Session, *, id: int, workspace_id: int) -> Optional[InvoiceItem]:
        return (
            db.query(InvoiceItem)
            .filter(InvoiceItem.id == id, InvoiceItem.workspace_id == workspace_id)
            .first()
        )

    def delete_all_for_invoice(self, db: Session, invoice_id: int) -> None:
        db.query(InvoiceItem).filter(InvoiceItem.invoice_id == invoice_id).delete(synchronize_session=False)
        db.flush()


invoice_item_dao = InvoiceItemDAO(InvoiceItem)
