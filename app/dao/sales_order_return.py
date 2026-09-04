"""Sales order return DAO operations"""
from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session
from app.dao.base import BaseDAO
from app.models.sales_order_return import SalesOrderReturn, SalesOrderReturnItem
from app.schemas.sales_order_return import SalesOrderReturnCreate


class DAOSalesOrderReturn(BaseDAO[SalesOrderReturn, SalesOrderReturnCreate, SalesOrderReturnCreate]):
    """DAO operations for SalesOrderReturn model"""

    def generate_return_number(self, db: Session, *, workspace_id: int, year: int) -> str:
        """Format: SR-{year}-{sequence}"""
        prefix = f"SR-{year}-"
        count = (
            db.query(SalesOrderReturn)
            .filter(
                SalesOrderReturn.workspace_id == workspace_id,
                SalesOrderReturn.return_number.like(f"{prefix}%"),
            )
            .count()
        )
        return f"{prefix}{count + 1:03d}"

    def create_with_user(
        self, db: Session, *, workspace_id: int, sales_order_id: int, user_id: int,
        return_type: str, reason: Optional[str] = None, notes: Optional[str] = None,
    ) -> SalesOrderReturn:
        return_number = self.generate_return_number(
            db, workspace_id=workspace_id, year=datetime.now().year
        )
        db_obj = SalesOrderReturn(
            workspace_id=workspace_id,
            sales_order_id=sales_order_id,
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

    def get_by_sales_order(
        self, db: Session, *, sales_order_id: int, workspace_id: int
    ) -> List[SalesOrderReturn]:
        return (
            db.query(SalesOrderReturn)
            .filter(
                SalesOrderReturn.sales_order_id == sales_order_id,
                SalesOrderReturn.workspace_id == workspace_id,
            )
            .order_by(SalesOrderReturn.created_at.desc())
            .all()
        )

    def get_open_by_sales_order(
        self, db: Session, *, sales_order_id: int, workspace_id: int
    ) -> List[SalesOrderReturn]:
        return (
            db.query(SalesOrderReturn)
            .filter(
                SalesOrderReturn.sales_order_id == sales_order_id,
                SalesOrderReturn.workspace_id == workspace_id,
                SalesOrderReturn.status == 'pending',
            )
            .all()
        )

    def get_by_invoice_id(
        self, db: Session, *, invoice_id: int, workspace_id: int
    ) -> Optional[SalesOrderReturn]:
        return (
            db.query(SalesOrderReturn)
            .filter(
                SalesOrderReturn.invoice_id == invoice_id,
                SalesOrderReturn.workspace_id == workspace_id,
            )
            .first()
        )


class DAOSalesOrderReturnItem(BaseDAO[SalesOrderReturnItem, SalesOrderReturnCreate, SalesOrderReturnCreate]):
    """DAO operations for SalesOrderReturnItem model"""

    def get_by_return(
        self, db: Session, *, return_id: int, workspace_id: int
    ) -> List[SalesOrderReturnItem]:
        return (
            db.query(SalesOrderReturnItem)
            .filter(
                SalesOrderReturnItem.return_id == return_id,
                SalesOrderReturnItem.workspace_id == workspace_id,
            )
            .all()
        )


sales_order_return_dao = DAOSalesOrderReturn(SalesOrderReturn)
sales_order_return_item_dao = DAOSalesOrderReturnItem(SalesOrderReturnItem)
