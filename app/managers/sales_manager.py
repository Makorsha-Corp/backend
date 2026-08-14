"""Sales Manager for sales order business logic"""
from typing import List, Optional, Tuple
from datetime import datetime
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.managers.base_manager import BaseManager
from app.models.sales_order import SalesOrder
from app.models.sales_order_item import SalesOrderItem
from app.models.sales_order_approver import SalesOrderApprover
from app.models.sales_order_event import SalesOrderEvent
from app.models.sales_delivery import SalesDelivery
from app.models.profile import Profile
from app.dao.sales_order import sales_order_dao
from app.dao.sales_order_item import sales_order_item_dao
from app.dao.sales_order_approver import sales_order_approver_dao
from app.dao.sales_order_event import sales_order_event_dao
from app.dao.sales_delivery import sales_delivery_dao
from app.dao.sales_delivery_item import sales_delivery_item_dao
from app.dao.workspace_member import workspace_member_dao
from app.dao.profile import profile_dao
from app.dao.account_invoice import account_invoice_dao

SECTION_CONFIRM_FIELDS = {
    'order_info_confirmed': ('order_info', 'Order info'),
    'items_confirmed': ('items', 'Order items'),
    'invoice_confirmed': ('invoice', 'Draft invoice'),
}


def all_deliverable_items_delivered(items: List[SalesOrderItem]) -> bool:
    """True if every requires_delivery=True line has been fully delivered. Vacuously true if none."""
    deliverable = [i for i in items if i.requires_delivery]
    return all(i.quantity_delivered >= i.quantity_ordered for i in deliverable)


def all_fulfilment_items_fulfilled(items: List[SalesOrderItem]) -> bool:
    """True if every requires_delivery=False line has been fulfilled. Vacuously true if none."""
    fulfilment = [i for i in items if not i.requires_delivery]
    return all(i.quantity_delivered >= i.quantity_ordered for i in fulfilment)


class SalesManager(BaseManager[SalesOrder]):
    """
    AGGREGATE MANAGER: Manages SalesOrder aggregate root.

    Aggregate: SalesOrder + SalesOrderItems + SalesDeliveries + SalesDeliveryItems
             + SalesOrderApprovers + SalesOrderEvents

    Business rules:
    - Sales order MUST have at least one item
    - Deliveries update order item quantities
    - Physical deliveries deduct from sellable Product stock (product_ledger)
    - Service/free-text lines are fulfilled directly, no delivery, no stock movement
    - Delivery/fulfilment actions require the invoice to be finalized first
    - Order completion requires the invoice finalized and all lines delivered/fulfilled

    Does NOT commit transactions - that's the service layer's responsibility.
    """

    def __init__(self):
        super().__init__(SalesOrder)
        self.sales_order_dao = sales_order_dao
        self.sales_order_item_dao = sales_order_item_dao
        self.approver_dao = sales_order_approver_dao
        self.event_dao = sales_order_event_dao
        self.sales_delivery_dao = sales_delivery_dao
        self.sales_delivery_item_dao = sales_delivery_item_dao

    def create_sales_order_with_items(
        self,
        session: Session,
        order_data: dict,
        items_data: List[dict],
        workspace_id: int,
        user_id: int
    ) -> SalesOrder:
        """
        Create sales order with items.

        Args:
            session: Database session
            order_data: Sales order creation data
            items_data: List of items to sell
            workspace_id: Workspace ID
            user_id: ID of user creating the order

        Returns:
            Created sales order (not yet committed)

        Raises:
            ValueError: If no items provided (business rule violation)
        """
        # Business rule: Sales order MUST have at least one item
        if not items_data:
            raise ValueError("Sales order must have at least one item")

        from app.utils.order_catalog_items import (
            assert_unique_catalog_item_ids,
            assert_meets_minimum_order_quantities,
        )

        assert_unique_catalog_item_ids(
            session,
            workspace_id,
            items_data,
            get_item_id=lambda row: row['item_id'] if isinstance(row, dict) else row.item_id,
        )
        assert_meets_minimum_order_quantities(
            session,
            workspace_id,
            order_data['factory_id'],
            items_data,
            get_item_id=lambda row: row['item_id'] if isinstance(row, dict) else row.item_id,
            get_quantity=lambda row: row['quantity_ordered'] if isinstance(row, dict) else row.quantity_ordered,
        )

        # Create the sales order
        from app.schemas.sales_order import SalesOrderCreate
        order_in = SalesOrderCreate(**order_data)
        sales_order = self.sales_order_dao.create_with_user(
            session,
            obj_in=order_in,
            workspace_id=workspace_id,
            user_id=user_id
        )

        # Auto-add the creator as an approver (unapproved).
        session.add(SalesOrderApprover(
            workspace_id=workspace_id,
            sales_order_id=sales_order.id,
            user_id=user_id,
            assigned_by=user_id,
            approved=False,
        ))
        session.flush()
        self.log_event(session, sales_order.id, workspace_id, 'created', 'Order created', user_id)

        # Create order items
        for item_data in items_data:
            from app.schemas.sales_order_item import SalesOrderItemCreate
            item_data['sales_order_id'] = sales_order.id
            item_data['workspace_id'] = workspace_id
            item_in = SalesOrderItemCreate(**item_data)
            self.sales_order_item_dao.create(session, obj_in=item_in)

        return sales_order

    def create_delivery_with_items(
        self,
        session: Session,
        delivery_data: dict,
        delivery_items_data: List[dict],
        workspace_id: int,
        user_id: int
    ) -> tuple:
        """
        Create delivery with items.

        Args:
            session: Database session
            delivery_data: Delivery creation data
            delivery_items_data: Items in this delivery
            workspace_id: Workspace ID
            user_id: User creating delivery

        Returns:
            Tuple of (delivery, sales_order)

        Raises:
            ValueError: If no items provided or quantities invalid
        """
        if not delivery_items_data:
            raise ValueError("Delivery must have at least one item")

        parent_order = self.sales_order_dao.get_by_id_and_workspace(
            session, id=delivery_data['sales_order_id'], workspace_id=workspace_id
        )
        if not parent_order:
            raise ValueError(f"Sales order {delivery_data['sales_order_id']} not found")
        if not parent_order.invoice_confirmed:
            raise ValueError(
                "Finalize the invoice before planning a delivery"
            )

        # Create delivery
        from app.schemas.sales_delivery import SalesDeliveryCreate
        delivery_in = SalesDeliveryCreate(**delivery_data)
        delivery = self.sales_delivery_dao.create_with_user(
            session,
            obj_in=delivery_in,
            workspace_id=workspace_id,
            user_id=user_id
        )

        # Create delivery items
        for item_data in delivery_items_data:
            from app.schemas.sales_delivery_item import SalesDeliveryItemCreate

            # Get sales order item to derive item_id
            sales_order_item = self.sales_order_item_dao.get_by_id_and_workspace(
                session,
                id=item_data['sales_order_item_id'],
                workspace_id=workspace_id
            )
            if not sales_order_item:
                raise ValueError(f"Sales order item {item_data['sales_order_item_id']} not found")
            if not sales_order_item.requires_delivery:
                raise ValueError(
                    f"Sales order item {sales_order_item.id} does not require delivery — "
                    "it should be fulfilled directly, not delivered"
                )

            requested_qty = item_data['quantity_delivered']
            available_qty = sales_order_item.quantity_available_to_plan
            if requested_qty > available_qty:
                raise ValueError(
                    f"Cannot plan {requested_qty} unit(s) for sales order item {sales_order_item.id} — "
                    f"only {available_qty} unit(s) are available to plan "
                    f"({sales_order_item.quantity_planned} already committed to other planned deliveries). "
                    "Edit or delete an existing planned delivery to free up capacity."
                )

            # Add required fields
            item_data['delivery_id'] = delivery.id
            item_data['workspace_id'] = workspace_id
            item_data['item_id'] = sales_order_item.item_id  # Derive from sales order item

            delivery_item_in = SalesDeliveryItemCreate(**item_data)
            self.sales_delivery_item_dao.create(session, obj_in=delivery_item_in)

        # Get sales order to return
        sales_order = self.sales_order_dao.get_by_id_and_workspace(
            session,
            id=delivery.sales_order_id,
            workspace_id=workspace_id
        )

        return delivery, sales_order

    def complete_delivery(
        self,
        session: Session,
        delivery_id: int,
        workspace_id: int,
        user_id: int
    ) -> SalesOrder:
        """
        Mark delivery as completed and deduct sellable product stock.

        Business logic:
        - Update delivery status to 'delivered'
        - Update sales order item quantities delivered
        - Deduct from Product (is_available_for_sale=True) + write product_ledger entries
        - Check if sales order is fully delivered

        Args:
            session: Database session
            delivery_id: Delivery ID
            workspace_id: Workspace ID
            user_id: User completing delivery

        Returns:
            Updated sales order
        """
        from app.managers.product_manager import product_manager

        # Get delivery
        delivery = self.sales_delivery_dao.get_by_id_and_workspace(
            session, id=delivery_id, workspace_id=workspace_id
        )
        if not delivery:
            raise ValueError("Delivery not found")

        # Get delivery items
        delivery_items = self.sales_delivery_item_dao.get_by_delivery(
            session, delivery_id=delivery_id, workspace_id=workspace_id
        )

        # Get sales order
        sales_order = self.sales_order_dao.get_by_id_and_workspace(
            session, id=delivery.sales_order_id, workspace_id=workspace_id
        )

        # Update delivery status
        from app.schemas.sales_delivery import SalesDeliveryUpdate
        from datetime import datetime
        delivery_update = SalesDeliveryUpdate(
            delivery_status='delivered',
            actual_delivery_date=datetime.now().date()
        )
        self.sales_delivery_dao.update(session, db_obj=delivery, obj_in=delivery_update)

        # Process each delivery item
        for delivery_item in delivery_items:
            # Update sales order item quantity delivered
            order_item = self.sales_order_item_dao.get(session, id=delivery_item.sales_order_item_id)
            order_item.quantity_delivered += delivery_item.quantity_delivered
            session.flush()

            # Free-text lines have no catalog item, so there's no Product stock to
            # deduct against — they're delivered (shipped) but don't move inventory.
            if delivery_item.item_id is not None:
                product_manager.apply_sale_deduction(
                    session,
                    workspace_id=workspace_id,
                    user_id=user_id,
                    factory_id=sales_order.factory_id,
                    item_id=delivery_item.item_id,
                    quantity=delivery_item.quantity_delivered,
                    delivery_id=delivery_id,
                    account_id=sales_order.account_id,
                    notes=f"Delivery {delivery.delivery_number} for SO-{sales_order.sales_order_number}",
                )

        self._recompute_is_fully_delivered(session, sales_order, workspace_id)

        return sales_order

    def cancel_delivery(
        self,
        session: Session,
        delivery_id: int,
        workspace_id: int,
    ) -> SalesDelivery:
        """
        Cancel a planned delivery, freeing up the quantity it had committed
        so it can be planned into a different delivery. No inventory/product
        impact since planned deliveries never touch stock (only completing
        one does) — this just flips the status.

        Raises:
            ValueError: If the delivery doesn't exist or isn't in 'planned' status.
        """
        delivery = self.sales_delivery_dao.get_by_id_and_workspace(
            session, id=delivery_id, workspace_id=workspace_id
        )
        if not delivery:
            raise ValueError(f"Delivery {delivery_id} not found")
        if delivery.delivery_status != "planned":
            raise ValueError(
                f"Only planned deliveries can be cancelled (this delivery is '{delivery.delivery_status}')"
            )

        from app.schemas.sales_delivery import SalesDeliveryUpdate
        delivery_update = SalesDeliveryUpdate(delivery_status="cancelled")
        return self.sales_delivery_dao.update(session, db_obj=delivery, obj_in=delivery_update)

    def fulfill_service_item(
        self,
        session: Session,
        order_item_id: int,
        workspace_id: int,
        user_id: int,
    ) -> SalesOrder:
        """
        Mark a sales order line that doesn't require delivery as fulfilled directly:
        sets quantity_delivered = quantity_ordered. No SalesDelivery row,
        no product/inventory movement. All-or-nothing; idempotent no-op if
        already fulfilled.

        Raises:
            ValueError: If the line item doesn't exist, or requires delivery
                (must use the delivery workflow instead).
        """
        order_item = self.sales_order_item_dao.get_by_id_and_workspace(
            session, id=order_item_id, workspace_id=workspace_id
        )
        if not order_item:
            raise ValueError(f"Sales order item {order_item_id} not found")

        if order_item.requires_delivery:
            raise ValueError(
                "This line requires delivery — use the delivery workflow, not direct fulfillment"
            )

        sales_order = self.sales_order_dao.get_by_id_and_workspace(
            session, id=order_item.sales_order_id, workspace_id=workspace_id
        )
        if not sales_order.invoice_confirmed:
            raise ValueError("Finalize the invoice before fulfilling this line")

        if order_item.quantity_delivered < order_item.quantity_ordered:
            order_item.quantity_delivered = order_item.quantity_ordered
            session.flush()

        self._recompute_is_fully_delivered(session, sales_order, workspace_id)
        return sales_order

    def _recompute_is_fully_delivered(
        self, session: Session, sales_order: SalesOrder, workspace_id: int
    ) -> bool:
        """Recompute and persist SalesOrder.is_fully_delivered from current item state."""
        all_items = self.sales_order_item_dao.get_by_sales_order(
            session, sales_order_id=sales_order.id, workspace_id=workspace_id
        )
        is_fully_delivered = all(
            item.quantity_delivered >= item.quantity_ordered for item in all_items
        )
        if sales_order.is_fully_delivered != is_fully_delivered:
            sales_order.is_fully_delivered = is_fully_delivered
            session.flush()
        return is_fully_delivered

    # ─── Section confirm ───────────────────────────────────────

    def _base_sections_confirmed(self, order: SalesOrder) -> bool:
        return bool(order.order_info_confirmed and order.items_confirmed)

    def is_so_financially_locked(self, session: Session, order: SalesOrder) -> bool:
        """True when a linked invoice is confirmed or locked (order fields locked)."""
        if order.invoice_id is None:
            return False
        invoice = account_invoice_dao.get_by_id_and_workspace(
            session, id=order.invoice_id, workspace_id=order.workspace_id
        )
        if not invoice:
            return False
        return invoice.invoice_status in ('confirmed', 'locked')

    def set_section_confirm(
        self,
        session: Session,
        order_id: int,
        workspace_id: int,
        user_id: int,
        section: str,
        confirmed: bool,
    ) -> SalesOrder:
        """Confirm or unconfirm an order_info/items section on a sales order."""
        field_by_section = {'order_info': 'order_info_confirmed', 'items': 'items_confirmed'}
        confirm_field = field_by_section.get(section)
        if not confirm_field:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown section '{section}'")

        order = self.sales_order_dao.get_by_id_and_workspace(session, id=order_id, workspace_id=workspace_id)
        if not order:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Sales order with ID {order_id} not found")

        old_confirmed = bool(getattr(order, confirm_field))
        if confirmed == old_confirmed:
            return order

        if confirmed:
            if section == 'order_info':
                if order.account_id is None:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Select a customer before confirming')
                if order.order_date is None:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Set the order date before confirming')
                if not order.contact_name or not order.contact_name.strip():
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Set the customer name before confirming')
            if section == 'items':
                items = self.sales_order_item_dao.get_by_sales_order(session, sales_order_id=order.id, workspace_id=workspace_id)
                if not items:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Add at least one line item before confirming')
        else:
            if self.is_so_financially_locked(session, order):
                _, label = SECTION_CONFIRM_FIELDS[confirm_field]
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f'Cannot unconfirm {label.lower()} after invoice is confirmed')
            if order.order_completed:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Cannot unconfirm — order is complete')

        setattr(order, confirm_field, confirmed)
        session.flush()

        section_key, label = SECTION_CONFIRM_FIELDS[confirm_field]
        event_suffix = 'confirmed' if confirmed else 'unconfirmed'
        self.log_event(session, order_id, workspace_id, f'{section_key}_{event_suffix}', f'{label} {event_suffix}', user_id)

        if not confirmed:
            self.reset_approvals(session, order_id, workspace_id, user_id, reason='Section unconfirmed')

        return order

    def reset_approvals(
        self, session: Session, order_id: int, workspace_id: int, user_id: Optional[int],
        reason: str = 'Cleared approvals',
    ) -> None:
        approvers = self.approver_dao.get_by_order(session, sales_order_id=order_id, workspace_id=workspace_id)
        reset_count = 0
        for approver in approvers:
            if approver.approved:
                approver.approved = False
                approver.approved_at = None
                reset_count += 1
        if reset_count:
            session.flush()
            self.log_event(
                session, order_id, workspace_id, 'approvals_reset',
                f'{reason} ({reset_count} approval(s) cleared)', user_id,
            )

    def apply_post_invoice_confirms(
        self, session: Session, order: SalesOrder, workspace_id: int, user_id: int
    ) -> None:
        """Set section confirms and log events after an invoice is finalized."""
        if not order.order_info_confirmed:
            order.order_info_confirmed = True
            self.log_event(session, order.id, workspace_id, 'order_info_confirmed', 'Order info confirmed after invoice finalized', user_id)
        if not order.items_confirmed:
            order.items_confirmed = True
            self.log_event(session, order.id, workspace_id, 'items_confirmed', 'Order items confirmed after invoice finalized', user_id)
        if not order.invoice_confirmed:
            order.invoice_confirmed = True
            self.log_event(session, order.id, workspace_id, 'invoice_confirmed', 'Draft invoice confirmed', user_id)
        session.flush()

    # ─── Completion ────────────────────────────────────────────

    def mark_order_complete(
        self, session: Session, order_id: int, workspace_id: int, user_id: int
    ) -> SalesOrder:
        """Manually close a sales order once delivery and fulfilment are both done."""
        order = self.sales_order_dao.get_by_id_and_workspace(session, id=order_id, workspace_id=workspace_id)
        if not order:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Sales order with ID {order_id} not found")
        if order.order_completed:
            return order

        if not order.invoice_confirmed:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Finalize the invoice before marking the order complete')

        items = self.sales_order_item_dao.get_by_sales_order(session, sales_order_id=order.id, workspace_id=workspace_id)
        if not (all_deliverable_items_delivered(items) and all_fulfilment_items_fulfilled(items)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Finish delivering and fulfilling all items before completing the order',
            )

        order.order_completed = True
        order.completed_at = datetime.utcnow()
        order.completed_by = user_id
        session.flush()

        self.sync_so_paid(session, order, workspace_id, user_id)
        self.log_event(session, order.id, workspace_id, 'order_completed', 'Order marked complete', user_id)
        return order

    # ─── Payment sync ──────────────────────────────────────────

    def _invoice_payment_status(self, session: Session, order: SalesOrder) -> Optional[str]:
        if order.invoice_id is None:
            return None
        invoice = account_invoice_dao.get_by_id_and_workspace(session, id=order.invoice_id, workspace_id=order.workspace_id)
        return invoice.payment_status if invoice else None

    def sync_so_for_linked_invoice(
        self, session: Session, invoice_id: int, workspace_id: int, user_id: Optional[int],
    ) -> None:
        order = self.sales_order_dao.get_by_invoice_id(session, invoice_id=invoice_id, workspace_id=workspace_id)
        if order:
            self.sync_so_paid(session, order, workspace_id, user_id)

    def sync_so_paid(
        self, session: Session, order: SalesOrder, workspace_id: int, user_id: Optional[int],
    ) -> bool:
        """Sync denormalized paid flag from linked invoice payment status."""
        new_paid = False
        if order.invoice_id is not None:
            new_paid = self._invoice_payment_status(session, order) == 'paid'
        if order.paid == new_paid:
            return False
        order.paid = new_paid
        session.flush()
        label = 'Paid' if new_paid else 'Unpaid'
        self.log_event(
            session, order.id, workspace_id, 'payment_status_synced',
            f'Order marked {label.lower()} from linked invoice', user_id,
            metadata={'paid': new_paid},
        )
        return True

    # ─── Approvers ─────────────────────────────────────────────

    def list_approvers(
        self, session: Session, order_id: int, workspace_id: int
    ) -> List[Tuple[SalesOrderApprover, Optional[Profile], Optional[str]]]:
        """Approvers for an order, enriched with profile + workspace position."""
        order = self.sales_order_dao.get_by_id_and_workspace(session, id=order_id, workspace_id=workspace_id)
        if not order:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Sales order with ID {order_id} not found")
        approvers = self.approver_dao.get_by_order(session, sales_order_id=order_id, workspace_id=workspace_id)
        result: List[Tuple[SalesOrderApprover, Optional[Profile], Optional[str]]] = []
        for a in approvers:
            profile = profile_dao.get(session, id=a.user_id)
            member = workspace_member_dao.get_by_workspace_and_user(session, workspace_id=workspace_id, user_id=a.user_id)
            result.append((a, profile, member.position if member else None))
        return result

    def approval_summary(self, session: Session, order: SalesOrder) -> Tuple[int, int, bool]:
        """(approved_count, required, met). required null -> all assigned must approve."""
        approvers = self.approver_dao.get_by_order(session, sales_order_id=order.id, workspace_id=order.workspace_id)
        approved_count = sum(1 for a in approvers if a.approved)
        if order.required_approvals is not None:
            required = order.required_approvals
        elif len(approvers) > 0:
            required = len(approvers)
        else:
            required = 0
        return approved_count, required, approved_count >= required

    def approvals_met(self, session: Session, order: SalesOrder) -> bool:
        return self.approval_summary(session, order)[2]

    def add_approver(
        self, session: Session, order_id: int, user_id: int, workspace_id: int, assigned_by: int
    ) -> SalesOrderApprover:
        order = self.sales_order_dao.get_by_id_and_workspace(session, id=order_id, workspace_id=workspace_id)
        if not order:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Sales order with ID {order_id} not found")
        member = workspace_member_dao.get_by_workspace_and_user(session, workspace_id=workspace_id, user_id=user_id)
        if not member or member.status != 'active':
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User is not an active member of this workspace")
        existing = self.approver_dao.get_by_order_and_user(session, sales_order_id=order_id, user_id=user_id, workspace_id=workspace_id)
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User is already an approver for this order")
        obj = SalesOrderApprover(
            workspace_id=workspace_id, sales_order_id=order_id, user_id=user_id,
            assigned_by=assigned_by, approved=False,
        )
        session.add(obj)
        session.flush()
        profile = profile_dao.get(session, id=user_id)
        user_name = profile.name if profile else f'User #{user_id}'
        self.log_event(
            session, order_id, workspace_id, 'approver_added', f'Added {user_name} as approver', assigned_by,
            metadata={'user_id': user_id, 'user_name': user_name},
        )
        return obj

    def remove_approver(
        self, session: Session, order_id: int, user_id: int, workspace_id: int,
        performed_by: Optional[int] = None,
    ) -> None:
        rec = self.approver_dao.get_by_order_and_user(session, sales_order_id=order_id, user_id=user_id, workspace_id=workspace_id)
        if not rec:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approver not found")
        profile = profile_dao.get(session, id=user_id)
        user_name = profile.name if profile else f'User #{user_id}'
        session.delete(rec)
        session.flush()
        self.log_event(
            session, order_id, workspace_id, 'approver_removed', f'Removed {user_name} as approver', performed_by,
            metadata={'user_id': user_id, 'user_name': user_name},
        )

    def set_approval(
        self, session: Session, order_id: int, user_id: int, workspace_id: int, approved: bool
    ) -> SalesOrderApprover:
        rec = self.approver_dao.get_by_order_and_user(session, sales_order_id=order_id, user_id=user_id, workspace_id=workspace_id)
        if not rec:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not an assigned approver for this order")

        order = self.sales_order_dao.get_by_id_and_workspace(session, id=order_id, workspace_id=workspace_id)
        if approved:
            if not self._base_sections_confirmed(order):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Confirm customer, order details, and items before approving')
        else:
            if order.order_completed:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Cannot withdraw approval — order is complete')
            if self.is_so_financially_locked(session, order):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Cannot withdraw approval — invoice is locked')

        rec.approved = approved
        rec.approved_at = datetime.utcnow() if approved else None
        session.flush()

        self.log_event(
            session, order_id, workspace_id,
            'approved' if approved else 'approval_withdrawn',
            'Approved order' if approved else 'Withdrew approval',
            user_id,
        )
        return rec

    # ─── Events ────────────────────────────────────────────────

    def log_event(
        self, session: Session, order_id: int, workspace_id: int,
        event_type: str, description: str, performed_by: Optional[int] = None,
        metadata: Optional[dict] = None,
    ) -> SalesOrderEvent:
        ev = SalesOrderEvent(
            workspace_id=workspace_id,
            sales_order_id=order_id,
            event_type=event_type,
            description=description,
            metadata_json=metadata,
            performed_by=performed_by,
        )
        session.add(ev)
        session.flush()
        return ev

    def list_events(
        self, session: Session, order_id: int, workspace_id: int
    ) -> List[Tuple[SalesOrderEvent, Optional[Profile]]]:
        order = self.sales_order_dao.get_by_id_and_workspace(session, id=order_id, workspace_id=workspace_id)
        if not order:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Sales order with ID {order_id} not found")
        events = self.event_dao.get_by_order(session, sales_order_id=order_id, workspace_id=workspace_id)
        return [(e, profile_dao.get(session, id=e.performed_by) if e.performed_by else None) for e in events]


sales_manager = SalesManager()
