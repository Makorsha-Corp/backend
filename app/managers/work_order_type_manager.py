"""
Work Order Type Manager

Business logic for work order type operations.
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.managers.base_manager import BaseManager
from app.models.work_order_type import WorkOrderType
from app.schemas.work_order_type import WorkOrderTypeCreate, WorkOrderTypeUpdate
from app.dao.work_order_type import work_order_type_dao


class WorkOrderTypeManager(BaseManager[WorkOrderType]):
    """
    Manager for work order type business logic.

    Handles CRUD operations for work order types with workspace isolation.
    """

    def __init__(self):
        super().__init__(WorkOrderType)
        self.work_order_type_dao = work_order_type_dao

    def create_work_order_type(
        self,
        session: Session,
        type_data: WorkOrderTypeCreate,
        workspace_id: int,
        user_id: int
    ) -> WorkOrderType:
        """Create new work order type. Raises 409 if name already exists in workspace."""
        existing_name = self._check_name_exists(
            session, workspace_id=workspace_id, name=type_data.name
        )
        if existing_name:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Work order type '{type_data.name}' already exists"
            )

        type_dict = type_data.model_dump()
        type_dict['workspace_id'] = workspace_id
        type_dict['created_by'] = user_id

        return self.work_order_type_dao.create(session, obj_in=type_dict)

    def update_work_order_type(
        self,
        session: Session,
        type_id: int,
        type_data: WorkOrderTypeUpdate,
        workspace_id: int,
        user_id: int
    ) -> WorkOrderType:
        """Update work order type."""
        wo_type = self.work_order_type_dao.get_by_id_and_workspace(
            session, id=type_id, workspace_id=workspace_id
        )
        if not wo_type:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Work order type with ID {type_id} not found"
            )
        if wo_type.is_deleted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot update a deleted work order type"
            )

        if type_data.name and type_data.name != wo_type.name:
            existing_name = self._check_name_exists(
                session, workspace_id=workspace_id, name=type_data.name, exclude_id=type_id
            )
            if existing_name:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Work order type '{type_data.name}' already exists"
                )

        update_dict = type_data.model_dump(exclude_unset=True, exclude_none=True)
        update_dict['updated_by'] = user_id
        return self.work_order_type_dao.update(session, db_obj=wo_type, obj_in=update_dict)

    def get_work_order_type(
        self, session: Session, type_id: int, workspace_id: int
    ) -> WorkOrderType:
        """Get work order type by ID."""
        wo_type = self.work_order_type_dao.get_by_id_and_workspace(
            session, id=type_id, workspace_id=workspace_id
        )
        if not wo_type:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Work order type with ID {type_id} not found"
            )
        return wo_type

    def search_work_order_types(
        self,
        session: Session,
        workspace_id: int,
        search: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
        include_deleted: bool = False
    ) -> List[WorkOrderType]:
        """Search work order types in workspace."""
        types = self.work_order_type_dao.get_by_workspace(
            session, workspace_id=workspace_id, skip=skip, limit=limit
        )
        if not include_deleted:
            types = [t for t in types if not t.is_deleted]
        if search:
            search_lower = search.lower()
            types = [t for t in types if search_lower in t.name.lower()]
        return types

    def delete_work_order_type(
        self, session: Session, type_id: int, workspace_id: int, user_id: int
    ) -> WorkOrderType:
        """Soft delete work order type."""
        wo_type = self.work_order_type_dao.get_by_id_and_workspace(
            session, id=type_id, workspace_id=workspace_id
        )
        if not wo_type:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Work order type with ID {type_id} not found"
            )
        if wo_type.is_deleted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Work order type is already deleted"
            )
        return self.work_order_type_dao.soft_delete(session, db_obj=wo_type, deleted_by=user_id)

    # ==================== HELPER METHODS ====================

    def _check_name_exists(
        self,
        session: Session,
        workspace_id: int,
        name: str,
        exclude_id: Optional[int] = None
    ) -> bool:
        """Check if work order type with given name exists in workspace (excluding deleted)."""
        types = self.work_order_type_dao.get_by_workspace(session, workspace_id=workspace_id)
        for t in types:
            if t.is_deleted:
                continue
            if t.name == name and (exclude_id is None or t.id != exclude_id):
                return True
        return False


# Singleton instance
work_order_type_manager = WorkOrderTypeManager()
