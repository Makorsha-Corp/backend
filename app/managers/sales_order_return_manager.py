"""Sales Order Return Manager - business logic for accepting returned SO goods"""
from typing import List
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.managers.base_manager import BaseManager
from app.models.sales_order_return import SalesOrderReturn
from app.dao.sales_order_return import sales_order_return_dao, sales_order_return_item_dao
from app.dao.sales_order_item import sales_order_item_dao
from app.dao.account_invoice import account_invoice_dao
from app.schemas.sales_order_return import SalesOrderReturnCreate


class SalesOrderReturnManager(BaseManager[SalesOrderReturn]):
    """Manager for sales order return business logic."""

    def __init__(self):
        super().__init__(SalesOrderReturn)
        self.return_dao = sales_order_return_dao
        self.return_item_dao = sales_order_return_item_dao
        self.item_dao = sales_order_item_dao

    def has_open_return(self, session: Session, sales_order_id: int, workspace_id: int) -> bool:
        return bool(self.return_dao.get_open_by_sales_order(
            session, sales_order_id=sales_order_id, workspace_id=workspace_id
        ))

    def validate_and_build_items(
        self,
        session: Session,
        *,
        sales_order_id: int,
        workspace_id: int,
        data: SalesOrderReturnCreate,
    ) -> List[dict]:
        """Validate requested return quantities against quantity_available_to_return."""
        item_map = {
            it.id: it
            for it in self.item_dao.get_by_sales_order(
                session, sales_order_id=sales_order_id, workspace_id=workspace_id
            )
        }
        built: List[dict] = []
        for line in data.items:
            so_line = item_map.get(line.so_item_id)
            if so_line is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f'Item {line.so_item_id} does not belong to this sales order',
                )
            available = so_line.quantity_available_to_return
            if line.quantity_returned > available:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f'Cannot return {line.quantity_returned} of "{so_line.item_name}" — '
                        f'only {available} available to return'
                    ),
                )
            unit_price = line.unit_price if line.unit_price is not None else so_line.unit_price
            built.append({
                'so_item_id': so_line.id,
                'item_id': so_line.item_id,
                'quantity_returned': line.quantity_returned,
                'unit_price': unit_price,
                'notes': line.notes,
            })
        return built

    def get_return(
        self, session: Session, return_id: int, sales_order_id: int, workspace_id: int
    ) -> SalesOrderReturn:
        ret = self.return_dao.get_by_id_and_workspace(session, id=return_id, workspace_id=workspace_id)
        if not ret or ret.sales_order_id != sales_order_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f'Return with ID {return_id} not found'
            )
        return ret

    def list_returns(
        self, session: Session, sales_order_id: int, workspace_id: int
    ) -> List[SalesOrderReturn]:
        return self.return_dao.get_by_sales_order(
            session, sales_order_id=sales_order_id, workspace_id=workspace_id
        )

    def sync_return_paid(self, session: Session, ret: SalesOrderReturn, workspace_id: int) -> bool:
        """Sync denormalized paid flag from the return's linked credit-note invoice."""
        new_paid = False
        if ret.invoice_id is not None:
            invoice = account_invoice_dao.get_by_id_and_workspace(
                session, id=ret.invoice_id, workspace_id=workspace_id
            )
            new_paid = bool(invoice and invoice.payment_status == 'paid')
        if ret.paid == new_paid:
            return False
        ret.paid = new_paid
        session.flush()
        return True


sales_order_return_manager = SalesOrderReturnManager()
