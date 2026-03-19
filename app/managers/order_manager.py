"""Order Manager for order business logic"""
from typing import List, Optional
from sqlalchemy.orm import Session
from app.managers.base_manager import BaseManager
from app.models.order import Order
from app.dao.order import order_dao
from app.dao.order_item import order_item_dao
from app.schemas.order import OrderCreate, OrderUpdate
from app.schemas.order_item import OrderItemCreate

class OrderManager(BaseManager[Order]):
    """
    AGGREGATE MANAGER: Manages Order aggregate root.

    Aggregate: Order + OrderItem

    Business rules:
    - Order MUST have at least one item

    Does NOT commit transactions - that's the service layer's responsibility.
    """

    def __init__(self):
        super().__init__(Order)
        self.order_dao = order_dao
        self.order_item_dao = order_item_dao

    def create_order_with_items(
        self,
        session: Session,
        order_data: dict,
        items_data: List[dict],
        user_id: int
    ) -> Order:
        """
        Create order with items.

        Args:
            session: Database session
            order_data: Order creation data
            items_data: List of items to include in order
            user_id: ID of user creating the order

        Returns:
            Created order (not yet committed)

        Raises:
            ValueError: If no items provided (business rule violation)

        Note:
            This method does NOT commit. The service layer must commit.
        """
        # Business rule: Order MUST have at least one item
        if not items_data:
            raise ValueError("Order must have at least one item")

        # Create the order with user ID
        from app.schemas.order import OrderCreate
        order_in = OrderCreate(**order_data)
        order = self.order_dao.create_with_user(
            session,
            obj_in=order_in,
            user_id=user_id
        )

        # Create order items
        for item_data in items_data:

            item_data['order_id'] = order.id
            item_in = OrderItemCreate(**item_data)
            self.order_item_dao.create(session, obj_in=item_in)

        return order

    def advance_order_status(
        self,
        session: Session,
        order_id: int,
        new_status_id: int,
        user_id: int
    ) -> Order:
        """
        Advance order to a new status.

        Args:
            session: Database session
            order_id: Order ID
            new_status_id: New status ID
            user_id: ID of user making the change

        Returns:
            Updated order (not yet committed)

        Raises:
            ValueError: If order not found

        Note:
            This method does NOT commit. The service layer must commit.
        """
        order = self.order_dao.get(session, id=order_id)
        if not order:
            raise ValueError(f"Order {order_id} not found")

        # Update order status
        order = self.order_dao.update(
            session,
            db_obj=order,
            obj_in={'current_status_id': new_status_id}
        )

        return order

    def get_order_with_items(
        self,
        session: Session,
        order_id: int
    ) -> Optional[Order]:
        """
        Get order by ID.

        Args:
            session: Database session
            order_id: Order ID

        Returns:
            Order or None if not found
        """
        return self.order_dao.get(session, id=order_id)

    def get_orders_by_factory(
        self,
        session: Session,
        factory_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[Order]:
        """
        Get orders by factory with pagination.

        Args:
            session: Database session
            factory_id: Factory ID
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of orders
        """
        return self.order_dao.get_by_factory(
            session,
            factory_id=factory_id,
            skip=skip,
            limit=limit
        )


# Singleton instance
order_manager = OrderManager()
