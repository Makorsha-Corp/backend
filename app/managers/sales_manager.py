"""Sales Manager for sales order business logic"""
from typing import List
from sqlalchemy.orm import Session
from app.managers.base_manager import BaseManager
from app.models.sales_order import SalesOrder
from app.dao.sales_order import sales_order_dao
from app.dao.sales_order_item import sales_order_item_dao
from app.dao.sales_delivery import sales_delivery_dao
from app.dao.sales_delivery_item import sales_delivery_item_dao
from app.dao.inventory_ledger import inventory_ledger_dao
from app.dao.inventory import inventory_dao


class SalesManager(BaseManager[SalesOrder]):
    """
    AGGREGATE MANAGER: Manages SalesOrder aggregate root.

    Aggregate: SalesOrder + SalesOrderItems + SalesDeliveries + SalesDeliveryItems

    Business rules:
    - Sales order MUST have at least one item
    - Deliveries update order item quantities
    - Completed deliveries update inventory ledger

    Does NOT commit transactions - that's the service layer's responsibility.
    """

    def __init__(self):
        super().__init__(SalesOrder)
        self.sales_order_dao = sales_order_dao
        self.sales_order_item_dao = sales_order_item_dao
        self.sales_delivery_dao = sales_delivery_dao
        self.sales_delivery_item_dao = sales_delivery_item_dao
        self.inventory_ledger_dao = inventory_ledger_dao
        self.inventory_dao = inventory_dao

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
        Mark delivery as completed and update inventory.

        Business logic:
        - Update delivery status to 'delivered'
        - Update sales order item quantities delivered
        - Create inventory ledger entries (transfer_out)
        - Update inventory snapshot
        - Check if sales order is fully delivered

        Args:
            session: Database session
            delivery_id: Delivery ID
            workspace_id: Workspace ID
            user_id: User completing delivery

        Returns:
            Updated sales order
        """
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

            # Create inventory ledger entry (transfer_out)
            from app.schemas.inventory_ledger import InventoryLedgerCreate
            ledger_entry = InventoryLedgerCreate(
                workspace_id=workspace_id,
                factory_id=sales_order.factory_id,
                item_id=delivery_item.item_id,
                transaction_type='transfer_out',
                quantity=delivery_item.quantity_delivered,
                unit_cost=0,  # TODO: Get actual cost from inventory
                total_cost=0,
                qty_before=0,  # TODO: Get from inventory snapshot
                qty_after=0,
                source_type='sales_delivery',
                source_id=delivery_id,
                transfer_destination_type='customer',
                transfer_destination_id=sales_order.account_id,
                notes=f"Delivery {delivery.delivery_number} for SO-{sales_order.sales_order_number}",
                performed_by=user_id
            )
            self.inventory_ledger_dao.create(session, obj_in=ledger_entry)

            # Update inventory snapshot (deduct quantity)
            inventory = self.inventory_dao.get_by_factory_and_item(
                session,
                factory_id=sales_order.factory_id,
                item_id=delivery_item.item_id,
                workspace_id=workspace_id
            )
            if inventory:
                inventory.qty -= delivery_item.quantity_delivered
                session.flush()

        # Check if sales order is fully delivered
        all_items = self.sales_order_item_dao.get_by_sales_order(
            session, sales_order_id=sales_order.id, workspace_id=workspace_id
        )
        is_fully_delivered = all(
            item.quantity_delivered >= item.quantity_ordered for item in all_items
        )

        if is_fully_delivered:
            sales_order.is_fully_delivered = True
            session.flush()

        return sales_order


sales_manager = SalesManager()
