"""Sales Service for orchestrating sales workflows"""
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.services.base_service import BaseService
from app.managers.sales_manager import sales_manager
from app.managers.account_invoice_manager import account_invoice_manager
from app.dao.account import account_dao
from app.models.sales_order import SalesOrder
from app.models.sales_order_approver import SalesOrderApprover
from app.models.sales_order_event import SalesOrderEvent
from app.models.sales_delivery import SalesDelivery
from app.models.profile import Profile
from app.schemas.sales_order import SalesOrderCreate, SalesOrderUpdate
from app.schemas.sales_delivery import SalesDeliveryCreate, SalesDeliveryUpdate
from app.schemas.account_invoice import AccountInvoiceCreate
from app.schemas.response import ActionMessage, success_message, info_message
from app.core.exceptions import NotFoundError
from app.utils.time import utcnow


class SalesService(BaseService):
    """
    Service for Sales Order workflows.

    Handles:
    - Transaction boundaries (commit/rollback)
    - Sales order and delivery orchestration
    - Error handling and exception translation
    """

    def __init__(self):
        super().__init__()
        self.sales_manager = sales_manager
        self.account_invoice_manager = account_invoice_manager

    def _attach_receivable_invoice_to_sales_order(
        self,
        db: Session,
        order: SalesOrder,
        workspace_id: int,
        user_id: int,
    ) -> None:
        """
        Create one receivable invoice for the sales order and link it (no commit).
        Caller must ensure the order is not already invoiced.
        """
        if order.account_id is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Cannot create invoice: sales order has no customer account",
            )

        account = account_dao.get_by_id_and_workspace(
            db, id=order.account_id, workspace_id=workspace_id
        )
        if not account:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Cannot create invoice: customer account was not found in this workspace",
            )
        if not account.allow_invoices:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Cannot create invoice: invoicing is disabled for this account",
            )

        invoice_in = AccountInvoiceCreate(
            account_id=order.account_id,
            order_id=order.id,
            order_type="sales_order",
            invoice_type="receivable",
            invoice_amount=Decimal("0.00"),  # recalculated after items sync
            invoice_number=None,
            vendor_invoice_number=None,
            invoice_date=date.today(),
            due_date=None,
            description=f"Auto-created from sales order {order.sales_order_number}",
            notes=order.description,
            allow_payments=True,
            payment_locked_reason=None,
        )

        try:
            invoice = self.account_invoice_manager.create_invoice(
                session=db,
                invoice_data=invoice_in,
                workspace_id=workspace_id,
                user_id=user_id,
            )
        except HTTPException as exc:
            if exc.status_code == status.HTTP_404_NOT_FOUND:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Cannot create invoice: customer account was not found in this workspace",
                ) from exc
            raise

        order.invoice_id = invoice.id
        order.is_invoiced = True
        db.flush()

        # Sync items from SO (draft — user must confirm)
        so_items = getattr(order, 'items', []) or []
        invoice_item_dicts = [
            {
                "line_number": i + 1,
                "description": item.item_name or f"Item {item.item_id}",
                "item_id": item.item_id,
                "source_order_item_id": item.id,
                "source_order_item_type": "so_item",
                "quantity": item.quantity_ordered,
                "unit": item.item_unit,
                "unit_price": item.unit_price,
                "line_subtotal": item.line_total,
            }
            for i, item in enumerate(so_items)
        ]
        self.account_invoice_manager.sync_items_from_list(
            db, invoice, invoice_item_dicts, user_id
        )
        order.items_updated_at = utcnow()

    def create_invoice_for_sales_order(
        self,
        db: Session,
        order_id: int,
        workspace_id: int,
        user_id: int,
    ) -> SalesOrder:
        """
        Create exactly one receivable account invoice from a sales order (manual retry / explicit API).
        """
        try:
            order = self.get_sales_order(db, order_id, workspace_id)

            if order.invoice_id is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Invoice already exists for this sales order",
                )
            if order.is_invoiced:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Invoice already exists for this sales order",
                )

            self._attach_receivable_invoice_to_sales_order(
                db, order, workspace_id, user_id
            )
            self._commit_transaction(db)
            db.refresh(order)
            return order
        except Exception:
            self._rollback_transaction(db)
            raise

    def finalize_sales_order_invoice(
        self,
        db: Session,
        order_id: int,
        workspace_id: int,
        user_id: int,
    ) -> SalesOrder:
        """
        Finalize the sales order's invoice: creates the draft invoice if one
        doesn't exist yet, confirms it, and flips all section-confirm flags
        as a side effect (mirrors Purchase Order's finalize-invoice step).

        Requires customer/details/items all confirmed and approvals met.
        """
        try:
            order = self.get_sales_order(db, order_id, workspace_id)

            if not self.sales_manager._base_sections_confirmed(order):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Confirm customer, order details, and items before finalizing",
                )
            approved_count, required, met = self.sales_manager.approval_summary(db, order)
            if not met:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Requires {required} approval(s); {approved_count} so far",
                )
            if order.invoice_confirmed:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Invoice is already finalized",
                )

            if order.invoice_id is None:
                self._attach_receivable_invoice_to_sales_order(db, order, workspace_id, user_id)

            self.account_invoice_manager.confirm_invoice(
                session=db, invoice_id=order.invoice_id, workspace_id=workspace_id, user_id=user_id,
            )
            self.sales_manager.apply_post_invoice_confirms(db, order, workspace_id, user_id)
            self.sales_manager.log_event(
                db, order.id, workspace_id, 'invoice_confirmed',
                f'Invoice #{order.invoice_id} confirmed — order locked', user_id,
                metadata={'invoice_id': order.invoice_id},
            )

            self._commit_transaction(db)
            db.refresh(order)
            self._attach_invoice_payment_status(db, [order])
            return order
        except Exception:
            self._rollback_transaction(db)
            raise

    def create_sales_order(
        self,
        db: Session,
        order_in: SalesOrderCreate,
        items_data: List[dict],
        workspace_id: int,
        current_user: Profile
    ) -> SalesOrder:
        """
        Create a new sales order with items.

        Args:
            db: Database session
            order_in: Sales order creation data
            items_data: List of items to sell
            workspace_id: Workspace ID
            current_user: Current authenticated user

        Returns:
            Created sales order

        Raises:
            Exception: If creation fails
        """
        order_data = order_in.model_dump()
        return self.create_sales_order_from_dict(db, order_data, items_data, workspace_id, current_user)

    def create_sales_order_from_dict(
        self,
        db: Session,
        order_data: dict,
        items_data: List[dict],
        workspace_id: int,
        current_user: Profile
    ) -> SalesOrder:
        """
        Create a new sales order with items from dict data.

        Args:
            db: Database session
            order_data: Sales order creation data (dict with total_amount)
            items_data: List of items to sell
            workspace_id: Workspace ID
            current_user: Current authenticated user

        Returns:
            Created sales order

        Raises:
            Exception: If creation fails
        """
        try:
            # Create sales order with items using manager
            sales_order = self.sales_manager.create_sales_order_with_items(
                session=db,
                order_data=order_data,
                items_data=items_data,
                workspace_id=workspace_id,
                user_id=current_user.id
            )

            # Commit transaction
            self._commit_transaction(db)
            db.refresh(sales_order)

            return sales_order

        except Exception as e:
            self._rollback_transaction(db)
            raise

    def get_sales_order(
        self,
        db: Session,
        order_id: int,
        workspace_id: int
    ) -> SalesOrder:
        """
        Get sales order by ID.

        Args:
            db: Database session
            order_id: Sales order ID
            workspace_id: Workspace ID

        Returns:
            Sales order

        Raises:
            ValueError: If order not found
        """
        order = self.sales_manager.sales_order_dao.get_by_id_and_workspace(
            db, id=order_id, workspace_id=workspace_id
        )
        if not order:
            raise ValueError(f"Sales order {order_id} not found")
        self._attach_invoice_payment_status(db, [order])
        return order

    def get_sales_orders(
        self,
        db: Session,
        workspace_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[SalesOrder]:
        """
        Get list of sales orders for workspace.

        Args:
            db: Database session
            workspace_id: Workspace ID
            skip: Number of records to skip
            limit: Maximum records to return

        Returns:
            List of sales orders
        """
        orders = self.sales_manager.sales_order_dao.get_by_workspace(
            db, workspace_id=workspace_id, skip=skip, limit=limit
        )
        self._attach_invoice_payment_status(db, orders)
        return orders

    @staticmethod
    def _attach_invoice_payment_status(db: Session, orders: List[SalesOrder]) -> None:
        """Batch-fetch invoice payment_status and attach as a transient attribute."""
        from app.models.account_invoice import AccountInvoice
        invoice_ids = [o.invoice_id for o in orders if o.invoice_id is not None]
        if not invoice_ids:
            for o in orders:
                o.invoice_payment_status = None
            return
        rows = db.query(AccountInvoice.id, AccountInvoice.payment_status).filter(
            AccountInvoice.id.in_(invoice_ids)
        ).all()
        status_map = {inv_id: ps for inv_id, ps in rows}
        for o in orders:
            o.invoice_payment_status = status_map.get(o.invoice_id)

    def update_sales_order(
        self,
        db: Session,
        order_id: int,
        workspace_id: int,
        order_update: SalesOrderUpdate,
        user_id: int,
    ) -> SalesOrder:
        """
        Update sales order (dates, description, delivery/invoice flags).

        Invoice creation no longer happens implicitly here — use
        finalize_sales_order_invoice or the manual create_invoice_for_sales_order
        path instead.

        Args:
            db: Database session
            order_id: Sales order ID
            workspace_id: Workspace ID
            order_update: Update data
            user_id: User performing the update

        Returns:
            Updated sales order

        Raises:
            ValueError: If order not found
        """
        try:
            order = self.get_sales_order(db, order_id, workspace_id)

            updated_order = self.sales_manager.sales_order_dao.update(
                db, db_obj=order, obj_in=order_update
            )

            self._commit_transaction(db)
            db.refresh(updated_order)

            return updated_order

        except Exception:
            self._rollback_transaction(db)
            raise

    def create_delivery(
        self,
        db: Session,
        delivery_in: SalesDeliveryCreate,
        delivery_items_data: List[dict],
        workspace_id: int,
        current_user: Profile
    ) -> tuple[SalesDelivery, SalesOrder]:
        """
        Create a delivery for a sales order.

        Args:
            db: Database session
            delivery_in: Delivery creation data
            delivery_items_data: Items in this delivery
            workspace_id: Workspace ID
            current_user: Current authenticated user

        Returns:
            Tuple of (delivery, sales_order)

        Raises:
            Exception: If creation fails
        """
        try:
            delivery_data = delivery_in.model_dump()

            # Create delivery with items using manager
            delivery, sales_order = self.sales_manager.create_delivery_with_items(
                session=db,
                delivery_data=delivery_data,
                delivery_items_data=delivery_items_data,
                workspace_id=workspace_id,
                user_id=current_user.id
            )

            # Commit transaction
            self._commit_transaction(db)
            db.refresh(delivery)
            db.refresh(sales_order)

            return delivery, sales_order

        except ValueError as e:
            self._rollback_transaction(db)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        except Exception:
            self._rollback_transaction(db)
            raise

    def complete_delivery(
        self,
        db: Session,
        delivery_id: int,
        workspace_id: int,
        current_user: Profile
    ) -> Tuple[SalesOrder, List[ActionMessage]]:
        """
        Mark delivery as completed and update inventory.

        This endpoint performs multiple backend actions:
        1. Mark delivery as delivered
        2. Update sales order item quantities
        3. Update inventory ledger (transfer_out)
        4. Update inventory snapshot
        5. Check if order fully delivered

        Args:
            db: Database session
            delivery_id: Delivery ID
            workspace_id: Workspace ID
            current_user: Current authenticated user

        Returns:
            Tuple of (updated sales order, list of action messages)

        Raises:
            NotFoundError: If delivery not found
            Exception: If completion fails
        """
        messages = []

        try:
            # Get delivery
            delivery = self.sales_manager.sales_delivery_dao.get_by_id_and_workspace(
                db, id=delivery_id, workspace_id=workspace_id
            )
            if not delivery:
                raise NotFoundError(f"Delivery with ID {delivery_id} not found")

            # Complete delivery (updates inventory, order items, etc.)
            sales_order = self.sales_manager.complete_delivery(
                session=db,
                delivery_id=delivery_id,
                workspace_id=workspace_id,
                user_id=current_user.id
            )

            messages.append(success_message(
                f"Delivery {delivery.delivery_number} marked as completed"
            ))

            # Count updated items
            delivery_items = self.sales_manager.sales_delivery_item_dao.get_by_delivery(
                db, delivery_id=delivery_id, workspace_id=workspace_id
            )
            total_qty = sum(item.quantity_delivered for item in delivery_items)
            messages.append(info_message(
                f"Inventory updated: {len(delivery_items)} items, {total_qty} units deducted",
                details={
                    "item_count": len(delivery_items),
                    "total_quantity": total_qty
                }
            ))

            # Check if order fully delivered
            if sales_order.is_fully_delivered:
                messages.append(success_message(
                    f"Sales order {sales_order.sales_order_number} is now fully delivered"
                ))
            else:
                # Calculate remaining quantity
                all_items = self.sales_manager.sales_order_item_dao.get_by_sales_order(
                    db, sales_order_id=sales_order.id, workspace_id=workspace_id
                )
                remaining = sum(
                    item.quantity_ordered - item.quantity_delivered
                    for item in all_items
                )
                messages.append(info_message(
                    f"{remaining} units remaining to be delivered"
                ))

            # Commit transaction
            self._commit_transaction(db)
            db.refresh(sales_order)

            return sales_order, messages

        except Exception as e:
            self._rollback_transaction(db)
            raise

    def cancel_delivery(
        self,
        db: Session,
        delivery_id: int,
        workspace_id: int,
    ) -> SalesDelivery:
        """
        Cancel a planned delivery so its committed quantity becomes available
        to plan into a new delivery.

        Raises:
            NotFoundError: If delivery not found
            HTTPException: If delivery is not in 'planned' status
        """
        try:
            delivery = self.sales_manager.sales_delivery_dao.get_by_id_and_workspace(
                db, id=delivery_id, workspace_id=workspace_id
            )
            if not delivery:
                raise NotFoundError(f"Delivery with ID {delivery_id} not found")

            try:
                updated = self.sales_manager.cancel_delivery(
                    session=db, delivery_id=delivery_id, workspace_id=workspace_id
                )
            except ValueError as e:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

            self._commit_transaction(db)
            db.refresh(updated)
            return updated

        except Exception:
            self._rollback_transaction(db)
            raise

    def fulfill_service_item(
        self,
        db: Session,
        order_id: int,
        order_item_id: int,
        workspace_id: int,
        current_user: Profile,
    ) -> Tuple[SalesOrder, List[ActionMessage]]:
        """
        Mark a sales order line that doesn't require delivery as fulfilled directly
        (no delivery, no inventory/product movement).
        """
        messages = []

        try:
            order_item = self.sales_manager.sales_order_item_dao.get_by_id_and_workspace(
                db, id=order_item_id, workspace_id=workspace_id
            )
            if not order_item:
                raise NotFoundError(f"Sales order item {order_item_id} not found")
            if order_item.sales_order_id != order_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Sales order item {order_item_id} does not belong to sales order {order_id}",
                )
            if order_item.requires_delivery:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="This line requires delivery — use the delivery workflow, not direct fulfillment",
                )
            parent_order = self.get_sales_order(db, order_id, workspace_id)
            if not parent_order.invoice_confirmed:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Finalize the invoice before fulfilling this line",
                )

            sales_order = self.sales_manager.fulfill_service_item(
                session=db,
                order_item_id=order_item_id,
                workspace_id=workspace_id,
                user_id=current_user.id,
            )

            messages.append(success_message("Line item marked as fulfilled"))
            if sales_order.is_fully_delivered:
                messages.append(success_message(
                    f"Sales order {sales_order.sales_order_number} is now fully delivered"
                ))

            self._commit_transaction(db)
            db.refresh(sales_order)
            return sales_order, messages

        except Exception:
            self._rollback_transaction(db)
            raise

    def get_deliveries_for_order(
        self,
        db: Session,
        sales_order_id: int,
        workspace_id: int
    ) -> List[SalesDelivery]:
        """
        Get all deliveries for a sales order.

        Args:
            db: Database session
            sales_order_id: Sales order ID
            workspace_id: Workspace ID

        Returns:
            List of deliveries
        """
        return self.sales_manager.sales_delivery_dao.get_by_sales_order(
            db, sales_order_id=sales_order_id, workspace_id=workspace_id
        )

    def get_sales_order_items(
        self,
        db: Session,
        sales_order_id: int,
        workspace_id: int
    ):
        """
        Get all items for a sales order.

        Args:
            db: Database session
            sales_order_id: Sales order ID
            workspace_id: Workspace ID

        Returns:
            List of sales order items
        """
        from app.dao.sales_order_item import sales_order_item_dao
        return sales_order_item_dao.get_by_sales_order(
            db, sales_order_id=sales_order_id, workspace_id=workspace_id
        )

    def get_delivery(
        self,
        db: Session,
        delivery_id: int,
        workspace_id: int
    ) -> SalesDelivery:
        """
        Get delivery by ID.

        Args:
            db: Database session
            delivery_id: Delivery ID
            workspace_id: Workspace ID

        Returns:
            Sales delivery

        Raises:
            ValueError: If delivery not found
        """
        delivery = self.sales_manager.sales_delivery_dao.get_by_id_and_workspace(
            db, id=delivery_id, workspace_id=workspace_id
        )
        if not delivery:
            raise ValueError(f"Delivery {delivery_id} not found")
        return delivery

    def get_deliveries(
        self,
        db: Session,
        workspace_id: int,
        delivery_status: str = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[SalesDelivery]:
        """
        Get list of deliveries for workspace with optional status filter.

        Args:
            db: Database session
            workspace_id: Workspace ID
            delivery_status: Optional status filter
            skip: Number of records to skip
            limit: Maximum records to return

        Returns:
            List of sales deliveries
        """
        if delivery_status:
            return self.sales_manager.sales_delivery_dao.get_by_status(
                db, delivery_status=delivery_status, workspace_id=workspace_id, skip=skip, limit=limit
            )
        else:
            return self.sales_manager.sales_delivery_dao.get_by_workspace(
                db, workspace_id=workspace_id, skip=skip, limit=limit
            )

    def get_delivery_items(
        self,
        db: Session,
        delivery_id: int,
        workspace_id: int
    ):
        """
        Get all items for a delivery.

        Args:
            db: Database session
            delivery_id: Delivery ID
            workspace_id: Workspace ID

        Returns:
            List of sales delivery items
        """
        from app.dao.sales_delivery_item import sales_delivery_item_dao
        return sales_delivery_item_dao.get_by_delivery(
            db, delivery_id=delivery_id, workspace_id=workspace_id
        )

    # ─── Completion ────────────────────────────────────────────

    def mark_order_complete(
        self, db: Session, order_id: int, workspace_id: int, user_id: int
    ) -> SalesOrder:
        """Mark a sales order complete once the invoice is finalized and every
        line has been delivered/fulfilled."""
        try:
            order = self.sales_manager.mark_order_complete(db, order_id, workspace_id, user_id)
            self._commit_transaction(db)
            db.refresh(order)
            self._attach_invoice_payment_status(db, [order])
            return order
        except Exception:
            self._rollback_transaction(db)
            raise

    # ─── Section confirm ───────────────────────────────────────

    def set_section_confirm(
        self, db: Session, order_id: int, workspace_id: int, user_id: int,
        section: str, confirmed: bool,
    ) -> SalesOrder:
        try:
            order = self.sales_manager.set_section_confirm(
                db, order_id, workspace_id, user_id, section, confirmed,
            )
            self._commit_transaction(db)
            db.refresh(order)
            return order
        except Exception:
            self._rollback_transaction(db)
            raise

    # ─── Approvers ─────────────────────────────────────────────

    def list_approvers(
        self, db: Session, order_id: int, workspace_id: int
    ) -> List[Tuple[SalesOrderApprover, Optional[Profile], Optional[str]]]:
        return self.sales_manager.list_approvers(db, order_id, workspace_id)

    def approval_summary(self, db: Session, order: SalesOrder) -> Tuple[int, int, bool]:
        return self.sales_manager.approval_summary(db, order)

    def add_approver(
        self, db: Session, order_id: int, user_id: int, workspace_id: int, assigned_by: int
    ) -> SalesOrderApprover:
        try:
            approver = self.sales_manager.add_approver(db, order_id, user_id, workspace_id, assigned_by)
            self._commit_transaction(db)
            db.refresh(approver)
            return approver
        except Exception:
            self._rollback_transaction(db)
            raise

    def remove_approver(
        self, db: Session, order_id: int, user_id: int, workspace_id: int, performed_by: int,
    ) -> None:
        try:
            self.sales_manager.remove_approver(db, order_id, user_id, workspace_id, performed_by)
            self._commit_transaction(db)
        except Exception:
            self._rollback_transaction(db)
            raise

    def set_approval(
        self, db: Session, order_id: int, user_id: int, workspace_id: int, approved: bool,
    ) -> SalesOrderApprover:
        try:
            approver = self.sales_manager.set_approval(db, order_id, user_id, workspace_id, approved)
            self._commit_transaction(db)
            db.refresh(approver)
            return approver
        except Exception:
            self._rollback_transaction(db)
            raise

    # ─── Events ────────────────────────────────────────────────

    def list_events(
        self, db: Session, order_id: int, workspace_id: int
    ) -> List[Tuple[SalesOrderEvent, Optional[Profile]]]:
        return self.sales_manager.list_events(db, order_id, workspace_id)


sales_service = SalesService()
