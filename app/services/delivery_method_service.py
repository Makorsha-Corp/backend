"""Delivery Method Service for orchestrating delivery method workflows"""
from typing import List, Optional
from sqlalchemy.orm import Session

from app.services.base_service import BaseService
from app.managers.delivery_method_manager import delivery_method_manager
from app.models.delivery_method import DeliveryMethod
from app.schemas.delivery_method import DeliveryMethodCreate, DeliveryMethodUpdate


class DeliveryMethodService(BaseService):
    """
    Service for Delivery Method workflows.

    Handles:
    - Transaction boundaries (commit/rollback)
    - Delivery method CRUD operations
    - Error handling and exception translation
    """

    def __init__(self):
        super().__init__()
        self.delivery_method_manager = delivery_method_manager

    def create_delivery_method(
        self,
        db: Session,
        delivery_method_in: DeliveryMethodCreate,
        workspace_id: int,
        user_id: int
    ) -> DeliveryMethod:
        """Create a new delivery method.

        Raises:
            HTTPException: If delivery method with same name exists
        """
        try:
            delivery_method = self.delivery_method_manager.create_delivery_method(
                session=db,
                delivery_method_data=delivery_method_in,
                workspace_id=workspace_id,
                user_id=user_id
            )

            self._commit_transaction(db)
            db.refresh(delivery_method)

            return delivery_method

        except Exception as e:
            self._rollback_transaction(db)
            raise

    def get_delivery_method(
        self,
        db: Session,
        delivery_method_id: int,
        workspace_id: int
    ) -> DeliveryMethod:
        """Get delivery method by ID.

        Raises:
            HTTPException: If delivery method not found
        """
        return self.delivery_method_manager.get_delivery_method(db, delivery_method_id, workspace_id)

    def get_delivery_methods(
        self,
        db: Session,
        workspace_id: int,
        search: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[DeliveryMethod]:
        """Get delivery methods in workspace."""
        return self.delivery_method_manager.search_delivery_methods(
            session=db,
            workspace_id=workspace_id,
            search=search,
            skip=skip,
            limit=limit
        )

    def update_delivery_method(
        self,
        db: Session,
        delivery_method_id: int,
        delivery_method_in: DeliveryMethodUpdate,
        workspace_id: int,
        user_id: int
    ) -> DeliveryMethod:
        """Update delivery method.

        Raises:
            HTTPException: If delivery method not found or validation fails
        """
        try:
            delivery_method = self.delivery_method_manager.update_delivery_method(
                session=db,
                delivery_method_id=delivery_method_id,
                delivery_method_data=delivery_method_in,
                workspace_id=workspace_id,
                user_id=user_id
            )

            self._commit_transaction(db)
            db.refresh(delivery_method)

            return delivery_method

        except Exception as e:
            self._rollback_transaction(db)
            raise

    def delete_delivery_method(
        self,
        db: Session,
        delivery_method_id: int,
        workspace_id: int,
        user_id: int
    ) -> DeliveryMethod:
        """Soft delete delivery method.

        Raises:
            HTTPException: If delivery method not found or already deleted
        """
        try:
            delivery_method = self.delivery_method_manager.delete_delivery_method(
                session=db,
                delivery_method_id=delivery_method_id,
                workspace_id=workspace_id,
                user_id=user_id
            )

            self._commit_transaction(db)
            db.refresh(delivery_method)

            return delivery_method

        except Exception as e:
            self._rollback_transaction(db)
            raise


# Singleton instance
delivery_method_service = DeliveryMethodService()
