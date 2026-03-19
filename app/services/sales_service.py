"""Sales Service for orchestrating sales workflows"""
from typing import List, Tuple
from sqlalchemy.orm import Session
from app.services.base_service import BaseService
from app.managers.sales_manager import sales_manager
from app.models.sales_order import SalesOrder
from app.models.sales_delivery import SalesDelivery
from app.models.profile import Profile
from app.schemas.sales_order import SalesOrderCreate, SalesOrderUpdate
from app.schemas.sales_delivery import SalesDeliveryCreate, SalesDeliveryUpdate
from app.schemas.response import ActionMessage, success_message, info_message, warning_message
from app.core.exceptions import NotFoundError, BusinessRuleError


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
        return self.sales_manager.sales_order_dao.get_by_workspace(
            db, workspace_id=workspace_id, skip=skip, limit=limit
        )

    def update_sales_order(
        self,
        db: Session,
        order_id: int,
        workspace_id: int,
        order_update: SalesOrderUpdate
    ) -> SalesOrder:
        """
        Update sales order.

        Args:
            db: Database session
            order_id: Sales order ID
            workspace_id: Workspace ID
            order_update: Update data

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

        except Exception as e:
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

        except Exception as e:
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
        6. Auto-generate invoice if configured

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


sales_service = SalesService()
