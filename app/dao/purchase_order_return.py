"""Purchase order return DAO operations"""
from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session
from app.dao.base import BaseDAO
from app.models.purchase_order_return import PurchaseOrderReturn, PurchaseOrderReturnItem
from app.schemas.purchase_order_return import PurchaseOrderReturnCreate


class DAOPurchaseOrderReturn(BaseDAO[PurchaseOrderReturn, PurchaseOrderReturnCreate, PurchaseOrderReturnCreate]):
    """DAO operations for PurchaseOrderReturn model"""

    def generate_return_number(self, db: Session, *, workspace_id: int, year: int) -> str:
        """Format: PR-{year}-{sequence}"""
        prefix = f"PR-{year}-"
        count = (
            db.query(PurchaseOrderReturn)
            .filter(
                PurchaseOrderReturn.workspace_id == workspace_id,
                PurchaseOrderReturn.return_number.like(f"{prefix}%"),
            )
            .count()
        )
        return f"{prefix}{count + 1:03d}"

    def create_with_user(
        self, db: Session, *, workspace_id: int, purchase_order_id: int, user_id: int,
        return_type: str, reason: Optional[str] = None, notes: Optional[str] = None,
    ) -> PurchaseOrderReturn:
        return_number = self.generate_return_number(
            db, workspace_id=workspace_id, year=datetime.now().year
        )
        db_obj = PurchaseOrderReturn(
            workspace_id=workspace_id,
            purchase_order_id=purchase_order_id,
            return_number=return_number,
            status='pending',
            return_type=return_type,
            reason=reason,
            notes=notes,
            created_by=user_id,
        )
        db.add(db_obj)
        db.flush()
        return db_obj

    def get_by_purchase_order(
        self, db: Session, *, purchase_order_id: int, workspace_id: int
    ) -> List[PurchaseOrderReturn]:
        return (
            db.query(PurchaseOrderReturn)
            .filter(
                PurchaseOrderReturn.purchase_order_id == purchase_order_id,
                PurchaseOrderReturn.workspace_id == workspace_id,
            )
            .order_by(PurchaseOrderReturn.created_at.desc())
            .all()
        )

    def get_open_by_purchase_order(
        self, db: Session, *, purchase_order_id: int, workspace_id: int
    ) -> List[PurchaseOrderReturn]:
        return (
            db.query(PurchaseOrderReturn)
            .filter(
                PurchaseOrderReturn.purchase_order_id == purchase_order_id,
                PurchaseOrderReturn.workspace_id == workspace_id,
                PurchaseOrderReturn.status == 'pending',
            )
            .all()
        )

    def get_by_invoice_id(
        self, db: Session, *, invoice_id: int, workspace_id: int
    ) -> Optional[PurchaseOrderReturn]:
        return (
            db.query(PurchaseOrderReturn)
            .filter(
                PurchaseOrderReturn.invoice_id == invoice_id,
                PurchaseOrderReturn.workspace_id == workspace_id,
            )
            .first()
        )


class DAOPurchaseOrderReturnItem(BaseDAO[PurchaseOrderReturnItem, PurchaseOrderReturnCreate, PurchaseOrderReturnCreate]):
    """DAO operations for PurchaseOrderReturnItem model"""

    def get_by_return(
        self, db: Session, *, return_id: int, workspace_id: int
    ) -> List[PurchaseOrderReturnItem]:
        return (
            db.query(PurchaseOrderReturnItem)
            .filter(
                PurchaseOrderReturnItem.return_id == return_id,
                PurchaseOrderReturnItem.workspace_id == workspace_id,
            )
            .all()
        )


purchase_order_return_dao = DAOPurchaseOrderReturn(PurchaseOrderReturn)
purchase_order_return_item_dao = DAOPurchaseOrderReturnItem(PurchaseOrderReturnItem)
