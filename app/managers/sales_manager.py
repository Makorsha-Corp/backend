"""Sales Manager for sales order business logic"""
from typing import List
from sqlalchemy.orm import Session
from app.managers.base_manager import BaseManager
from app.models.sales_order import SalesOrder
from app.models.sales_delivery import SalesDelivery
from app.dao.sales_order import sales_order_dao
from app.dao.sales_order_item import sales_order_item_dao
from app.dao.sales_delivery import sales_delivery_dao
from app.dao.sales_delivery_item import sales_delivery_item_dao


class SalesManager(BaseManager[SalesOrder]):
    """
    AGGREGATE MANAGER: Manages SalesOrder aggregate root.

    Aggregate: SalesOrder + SalesOrderItems + SalesDeliveries + SalesDeliveryItems

    Business rules:
    - Sales order MUST have at least one item
    - Deliveries update order item quantities
    - Physical deliveries deduct from sellable Product stock (product_ledger)
    - Service/free-text lines are fulfilled directly, no delivery, no stock movement

    Does NOT commit transactions - that's the service layer's responsibility.
    """

    def __init__(self):
        super().__init__(SalesOrder)
        self.sales_order_dao = sales_order_dao
        self.sales_order_item_dao = sales_order_item_dao
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

        if order_item.quantity_delivered < order_item.quantity_ordered:
            order_item.quantity_delivered = order_item.quantity_ordered
            session.flush()

        sales_order = self.sales_order_dao.get_by_id_and_workspace(
            session, id=order_item.sales_order_id, workspace_id=workspace_id
        )
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


sales_manager = SalesManager()
