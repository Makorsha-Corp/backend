"""DAO operations for DeliveryMethod model

SECURITY NOTICE:
This DAO handles workspace-scoped data. All inherited BaseDAO methods automatically
filter by workspace_id via get_by_workspace() and get_by_id_and_workspace().
"""
from typing import List
from datetime import datetime
from sqlalchemy.orm import Session
from app.dao.base import BaseDAO
from app.models.delivery_method import DeliveryMethod
from app.schemas.delivery_method import DeliveryMethodCreate, DeliveryMethodUpdate
from app.utils.time import utcnow


class DAODeliveryMethod(BaseDAO[DeliveryMethod, DeliveryMethodCreate, DeliveryMethodUpdate]):
    """
    DAO operations for DeliveryMethod model (workspace-scoped)

    Uses inherited BaseDAO methods which are workspace-safe:
    - get_by_workspace() - Get all delivery methods in workspace
    - get_by_id_and_workspace() - Get specific delivery method in workspace
    """

    def soft_delete(
        self, db: Session, *, db_obj: DeliveryMethod, deleted_by: int
    ) -> DeliveryMethod:
        """Soft delete a delivery method (does NOT commit)"""
        db_obj.is_deleted = True
        db_obj.deleted_at = utcnow()
        db_obj.deleted_by = deleted_by
        db.add(db_obj)
        db.flush()
        return db_obj

    def restore(
        self, db: Session, *, db_obj: DeliveryMethod
    ) -> DeliveryMethod:
        """Restore a soft-deleted delivery method (does NOT commit)"""
        db_obj.is_deleted = False
        db_obj.deleted_at = None
        db_obj.deleted_by = None
        db.add(db_obj)
        db.flush()
        return db_obj


delivery_method_dao = DAODeliveryMethod(DeliveryMethod)
