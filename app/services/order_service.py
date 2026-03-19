"""Order Service for orchestrating order workflows"""
from typing import List
from sqlalchemy.orm import Session
from app.services.base_service import BaseService
from app.managers.order_manager import order_manager
from app.managers.inventory_manager import inventory_manager
from app.models.order import Order
from app.models.profile import Profile
from app.schemas.order import OrderCreate, OrderUpdate
from app.dao.order import order_dao
from app.dao.order_item import order_item_dao

class OrderService(BaseService):
    """
    Service for Order workflows.

    Handles:
    - Transaction boundaries (commit/rollback)
    - Orchestrating multiple managers
    - Error handling and exception translation
    """

    def __init__(self):
        super().__init__()
        self.order_manager = order_manager
        self.inventory_manager = inventory_manager

    def create_order(
        self,
        db: Session,
        order_in: OrderCreate,
        current_user: Profile
    ) -> Order:
        """
        Create a new order with items.

        Args:
            db: Database session
            order_in: Order creation data
            current_user: Current authenticated user

        Returns:
            Created order

        Raises:
            Exception: If creation fails
        """
        try:
            # Extract parts from order_in if present
            items_data = []
            order_data = order_in.model_dump(exclude={'items'})
            if hasattr(order_in, 'items') and order_in.items:
                items_data = [p.model_dump() for p in order_in.items]

            # Create order with items using manager
            order = self.order_manager.create_order_with_items(
                session=db,
                order_data=order_data,
                items_data=items_data,
                user_id=current_user.id
            )

            # Commit transaction
            self._commit_transaction(db)
            db.refresh(order)

            return order

        except Exception as e:
            self._rollback_transaction(db)
            raise

    def get_order(
        self,
        db: Session,
        order_id: int
    ) -> Order:
        """
        Get order by ID.

        Args:
            db: Database session
            order_id: Order ID

        Returns:
            Order

        Raises:
            ValueError: If order not found
        """
        order = self.order_manager.get_order_with_items(db, order_id)
        if not order:
            raise ValueError(f"Order {order_id} not found")
        return order

    def get_orders(
        self,
        db: Session,
        skip: int = 0,
        limit: int = 100
    ) -> List[Order]:
        """
        Get all orders with pagination.

        Args:
            db: Database session
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of orders
        """
        return order_dao.get_multi(db, skip=skip, limit=limit)

    def update_order(
        self,
        db: Session,
        order_id: int,
        order_in: OrderUpdate,
        current_user: Profile
    ) -> Order:
        """
        Update an existing order.

        Args:
            db: Database session
            order_id: Order ID
            order_in: Order update data
            current_user: Current authenticated user

        Returns:
            Updated order

        Raises:
            ValueError: If order not found
        """
        try:
            # Get order
            order = order_dao.get(db, id=order_id)
            if not order:
                raise ValueError(f"Order {order_id} not found")

            # Update order
            order = order_dao.update(db, db_obj=order, obj_in=order_in)

            # Commit transaction
            self._commit_transaction(db)
            db.refresh(order)

            return order

        except Exception as e:
            self._rollback_transaction(db)
            raise

    def delete_order(
        self,
        db: Session,
        order_id: int,
        current_user: Profile
    ) -> None:
        """
        Delete an order.

        Args:
            db: Database session
            order_id: Order ID
            current_user: Current authenticated user

        Raises:
            ValueError: If order not found
        """
        try:
            # Get order
            order = order_dao.get(db, id=order_id)
            if not order:
                raise ValueError(f"Order {order_id} not found")

            # Delete order
            order_dao.remove(db, id=order_id)

            # Commit transaction
            self._commit_transaction(db)

        except Exception as e:
            self._rollback_transaction(db)
            raise

    def approve_storage_withdrawal(
        self,
        db: Session,
        order_id: int,
        current_user: Profile
    ) -> Order:
        """
        Approve storage withdrawal for an order.
        Deducts items from storage and advances order status.

        Args:
            db: Database session
            order_id: Order ID
            current_user: Current authenticated user

        Returns:
            Updated order

        Raises:
            ValueError: If order not found or insufficient stock
        """
        try:


            # Get order
            order = order_dao.get(db, id=order_id)
            if not order:
                raise ValueError(f"Order {order_id} not found")

            # Get order items
            order_items = order_item_dao.get_by_order(db, order_id=order_id)

            # Prepare items data for deduction
            items_to_deduct = [
                {'item_id': op.item_id, 'qty': op.qty}
                for op in order_items
            ]

            # Deduct from storage using inventory manager
            self.inventory_manager.deduct_from_storage(
                session=db,
                factory_id=order.factory_id,
                items=items_to_deduct
            )

            # Advance order status using order manager
            order = self.order_manager.advance_order_status(
                session=db,
                order_id=order_id,
                new_status_id=3,  # Approved/Withdrawn status
                user_id=current_user.id
            )

            # Commit transaction
            self._commit_transaction(db)
            db.refresh(order)

            return order

        except Exception as e:
            self._rollback_transaction(db)
            raise

    def process_stm_order(
        self,
        db: Session,
        order_id: int,
        current_user: Profile
    ) -> Order:
        """
        Process STM (Storage To Machine) order.
        Transfers items from storage to machine.

        Args:
            db: Database session
            order_id: Order ID
            current_user: Current authenticated user

        Returns:
            Updated order

        Raises:
            ValueError: If order not found or insufficient stock
        """
        try:
            # Get order
            order = order_dao.get(db, id=order_id)
            if not order:
                raise ValueError(f"Order {order_id} not found")

            if not order.machine_id:
                raise ValueError(f"Order {order_id} does not have a machine assigned")

            # Get order items
            order_items = order_item_dao.get_by_order(db, order_id=order_id)

            # Prepare items data for transfer to machine    
            items_data = [
                {'item_id': op.item_id, 'qty': op.qty}
                for op in order_items
            ]

            # Transfer from storage to machine
            self.inventory_manager.transfer_storage_to_machine(
                session=db,
                factory_id=order.factory_id,
                machine_id=order.machine_id,
                items=items_data
            )

            # Advance order status
            order = self.order_manager.advance_order_status(
                session=db,
                order_id=order_id,
                new_status_id=5,  # Completed status
                user_id=current_user.id
            )

            # Commit transaction
            self._commit_transaction(db)
            db.refresh(order)

            return order

        except Exception as e:
            self._rollback_transaction(db)
            raise


# Singleton instance
order_service = OrderService()
