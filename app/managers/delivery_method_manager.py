"""
Delivery Method Manager

Business logic for delivery method operations.
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.managers.base_manager import BaseManager
from app.models.delivery_method import DeliveryMethod
from app.schemas.delivery_method import DeliveryMethodCreate, DeliveryMethodUpdate
from app.dao.delivery_method import delivery_method_dao


class DeliveryMethodManager(BaseManager[DeliveryMethod]):
    """
    Manager for delivery method business logic.

    Handles CRUD operations for delivery methods with workspace isolation.
    """

    def __init__(self):
        super().__init__(DeliveryMethod)
        self.delivery_method_dao = delivery_method_dao

    def create_delivery_method(
        self,
        session: Session,
        delivery_method_data: DeliveryMethodCreate,
        workspace_id: int,
        user_id: int
    ) -> DeliveryMethod:
        """Create new delivery method.

        Raises:
            HTTPException: If delivery method with same name already exists
        """
        existing_name = self._check_name_exists(
            session, workspace_id=workspace_id, name=delivery_method_data.name
        )
        if existing_name:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Delivery method with name '{delivery_method_data.name}' already exists"
            )

        delivery_method_dict = delivery_method_data.model_dump()
        delivery_method_dict['workspace_id'] = workspace_id
        delivery_method_dict['created_by'] = user_id

        delivery_method = self.delivery_method_dao.create(session, obj_in=delivery_method_dict)
        return delivery_method

    def update_delivery_method(
        self,
        session: Session,
        delivery_method_id: int,
        delivery_method_data: DeliveryMethodUpdate,
        workspace_id: int,
        user_id: int
    ) -> DeliveryMethod:
        """Update delivery method.

        Raises:
            HTTPException: If delivery method not found or validation fails
        """
        delivery_method = self.delivery_method_dao.get_by_id_and_workspace(
            session, id=delivery_method_id, workspace_id=workspace_id
        )
        if not delivery_method:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Delivery method with ID {delivery_method_id} not found"
            )

        if delivery_method.is_deleted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot update deleted delivery method"
            )

        if delivery_method_data.name and delivery_method_data.name != delivery_method.name:
            existing_name = self._check_name_exists(
                session, workspace_id=workspace_id, name=delivery_method_data.name, exclude_id=delivery_method_id
            )
            if existing_name:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Delivery method with name '{delivery_method_data.name}' already exists"
                )

        update_dict = delivery_method_data.model_dump(exclude_unset=True, exclude_none=True)
        update_dict['updated_by'] = user_id

        updated_delivery_method = self.delivery_method_dao.update(session, db_obj=delivery_method, obj_in=update_dict)
        return updated_delivery_method

    def get_delivery_method(
        self,
        session: Session,
        delivery_method_id: int,
        workspace_id: int
    ) -> DeliveryMethod:
        """Get delivery method by ID.

        Raises:
            HTTPException: If delivery method not found
        """
        delivery_method = self.delivery_method_dao.get_by_id_and_workspace(
            session, id=delivery_method_id, workspace_id=workspace_id
        )

        if not delivery_method:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Delivery method with ID {delivery_method_id} not found"
            )

        return delivery_method

    def search_delivery_methods(
        self,
        session: Session,
        workspace_id: int,
        search: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
        include_deleted: bool = False
    ) -> List[DeliveryMethod]:
        """Search delivery methods in workspace."""
        delivery_methods = self.delivery_method_dao.get_by_workspace(
            session, workspace_id=workspace_id, skip=skip, limit=limit
        )

        if not include_deleted:
            delivery_methods = [d for d in delivery_methods if not d.is_deleted]

        if search:
            search_lower = search.lower()
            delivery_methods = [
                d for d in delivery_methods
                if search_lower in d.name.lower()
            ]

        return delivery_methods

    def delete_delivery_method(
        self,
        session: Session,
        delivery_method_id: int,
        workspace_id: int,
        user_id: int
    ) -> DeliveryMethod:
        """Soft delete delivery method.

        Raises:
            HTTPException: If delivery method not found or already deleted
        """
        delivery_method = self.delivery_method_dao.get_by_id_and_workspace(
            session, id=delivery_method_id, workspace_id=workspace_id
        )

        if not delivery_method:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Delivery method with ID {delivery_method_id} not found"
            )

        if delivery_method.is_deleted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Delivery method is already deleted"
            )

        deleted_delivery_method = self.delivery_method_dao.soft_delete(session, db_obj=delivery_method, deleted_by=user_id)
        return deleted_delivery_method

    # ==================== HELPER METHODS ====================

    def _check_name_exists(
        self,
        session: Session,
        workspace_id: int,
        name: str,
        exclude_id: Optional[int] = None
    ) -> bool:
        """Check if delivery method with given name exists in workspace (excluding deleted)."""
        delivery_methods = self.delivery_method_dao.get_by_workspace(session, workspace_id=workspace_id)
        for delivery_method in delivery_methods:
            if delivery_method.is_deleted:
                continue
            if delivery_method.name == name and (exclude_id is None or delivery_method.id != exclude_id):
                return True
        return False


# Singleton instance
delivery_method_manager = DeliveryMethodManager()
