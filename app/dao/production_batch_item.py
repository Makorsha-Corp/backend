"""Production Batch Item DAO operations"""
from typing import List, Optional
from sqlalchemy.orm import Session
from app.dao.base import BaseDAO
from app.models.production_batch_item import ProductionBatchItem
from app.schemas.production_batch_item import ProductionBatchItemCreate, ProductionBatchItemUpdate


class ProductionBatchItemDAO(BaseDAO[ProductionBatchItem, ProductionBatchItemCreate, ProductionBatchItemUpdate]):
    """
    DAO operations for ProductionBatchItem model.
    All methods enforce workspace isolation for security.
    """

    def get_by_batch(
        self, db: Session, *, batch_id: int, workspace_id: int
    ) -> List[ProductionBatchItem]:
        """
        Get all items for a batch (SECURITY-CRITICAL)

        Args:
            db: Database session
            batch_id: Batch ID
            workspace_id: Workspace ID to filter by

        Returns:
            List of batch items
        """
        return (
            db.query(ProductionBatchItem)
            .filter(
                ProductionBatchItem.workspace_id == workspace_id,
                ProductionBatchItem.batch_id == batch_id
            )
            .all()
        )

    def get_by_batch_and_role(
        self, db: Session, *, batch_id: int, item_role: str, workspace_id: int
    ) -> List[ProductionBatchItem]:
        """
        Get items by batch and role (SECURITY-CRITICAL)

        Args:
            db: Database session
            batch_id: Batch ID
            item_role: Item role ('input', 'output', 'waste', 'byproduct')
            workspace_id: Workspace ID to filter by

        Returns:
            List of batch items
        """
        return (
            db.query(ProductionBatchItem)
            .filter(
                ProductionBatchItem.workspace_id == workspace_id,
                ProductionBatchItem.batch_id == batch_id,
                ProductionBatchItem.item_role == item_role
            )
            .all()
        )

    def get_inputs_for_batch(
        self, db: Session, *, batch_id: int, workspace_id: int
    ) -> List[ProductionBatchItem]:
        """
        Get all input items for a batch (SECURITY-CRITICAL)

        Args:
            db: Database session
            batch_id: Batch ID
            workspace_id: Workspace ID to filter by

        Returns:
            List of input items
        """
        return self.get_by_batch_and_role(
            db, batch_id=batch_id, item_role='input', workspace_id=workspace_id
        )

    def get_outputs_for_batch(
        self, db: Session, *, batch_id: int, workspace_id: int
    ) -> List[ProductionBatchItem]:
        """
        Get all output items for a batch (SECURITY-CRITICAL)

        Args:
            db: Database session
            batch_id: Batch ID
            workspace_id: Workspace ID to filter by

        Returns:
            List of output items
        """
        return self.get_by_batch_and_role(
            db, batch_id=batch_id, item_role='output', workspace_id=workspace_id
        )

    def get_waste_for_batch(
        self, db: Session, *, batch_id: int, workspace_id: int
    ) -> List[ProductionBatchItem]:
        """
        Get all waste items for a batch (SECURITY-CRITICAL)

        Args:
            db: Database session
            batch_id: Batch ID
            workspace_id: Workspace ID to filter by

        Returns:
            List of waste items
        """
        return self.get_by_batch_and_role(
            db, batch_id=batch_id, item_role='waste', workspace_id=workspace_id
        )

    def get_byproducts_for_batch(
        self, db: Session, *, batch_id: int, workspace_id: int
    ) -> List[ProductionBatchItem]:
        """
        Get all byproduct items for a batch (SECURITY-CRITICAL)

        Args:
            db: Database session
            batch_id: Batch ID
            workspace_id: Workspace ID to filter by

        Returns:
            List of byproduct items
        """
        return self.get_by_batch_and_role(
            db, batch_id=batch_id, item_role='byproduct', workspace_id=workspace_id
        )

    def get_by_item(
        self, db: Session, *, item_id: int, workspace_id: int,
        skip: int = 0, limit: int = 100
    ) -> List[ProductionBatchItem]:
        """
        Get all batch items for a specific item (SECURITY-CRITICAL)

        Args:
            db: Database session
            item_id: Item ID
            workspace_id: Workspace ID to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of batch items
        """
        return (
            db.query(ProductionBatchItem)
            .filter(
                ProductionBatchItem.workspace_id == workspace_id,
                ProductionBatchItem.item_id == item_id
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_id_and_workspace(
        self, db: Session, *, id: int, workspace_id: int
    ) -> Optional[ProductionBatchItem]:
        """
        Get batch item by ID with workspace validation (SECURITY-CRITICAL)

        Args:
            db: Database session
            id: Batch item ID
            workspace_id: Workspace ID to filter by

        Returns:
            Batch item or None
        """
        return (
            db.query(ProductionBatchItem)
            .filter(
                ProductionBatchItem.id == id,
                ProductionBatchItem.workspace_id == workspace_id
            )
            .first()
        )


production_batch_item_dao = ProductionBatchItemDAO(ProductionBatchItem)
