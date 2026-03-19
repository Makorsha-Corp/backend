"""Production Batch Service for orchestrating production batch workflows"""
from typing import List, Optional
from sqlalchemy.orm import Session
from app.services.base_service import BaseService
from app.managers.production_batch_manager import production_batch_manager
from app.models.production_batch import ProductionBatch
from app.models.production_batch_item import ProductionBatchItem
from app.core.exceptions import NotFoundError, BusinessRuleError


class ProductionBatchService(BaseService):
    """
    Service for Production Batch workflows.

    Handles:
    - Transaction boundaries (commit/rollback)
    - Batch CRUD and workflow operations (start, complete, cancel)
    - Batch item CRUD
    - Error handling and exception translation
    """

    def __init__(self):
        super().__init__()
        self.batch_manager = production_batch_manager

    # ─── Batch Operations ───────────────────────────────────────────

    def create_batch(
        self,
        db: Session,
        batch_in: "ProductionBatchCreate",
        workspace_id: int,
        user_id: int
    ) -> ProductionBatch:
        """Create a new production batch."""
        try:
            batch = self.batch_manager.create_batch(
                session=db,
                batch_data=batch_in,
                workspace_id=workspace_id,
                user_id=user_id
            )
            self._commit_transaction(db)
            db.refresh(batch)
            return batch
        except ValueError as e:
            self._rollback_transaction(db)
            raise BusinessRuleError(str(e))
        except Exception:
            self._rollback_transaction(db)
            raise

    def get_batch(
        self,
        db: Session,
        batch_id: int,
        workspace_id: int
    ) -> ProductionBatch:
        """Get batch by ID. Raises NotFoundError if not found."""
        batch = self.batch_manager.get_batch(db, batch_id, workspace_id)
        if not batch:
            raise NotFoundError(f"Production batch with ID {batch_id} not found")
        return batch

    def get_batches(
        self,
        db: Session,
        workspace_id: int,
        production_line_id: Optional[int] = None,
        formula_id: Optional[int] = None,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[ProductionBatch]:
        """Get batches with optional filtering."""
        return self.batch_manager.get_batches(
            session=db,
            workspace_id=workspace_id,
            production_line_id=production_line_id,
            formula_id=formula_id,
            status=status,
            skip=skip,
            limit=limit
        )

    def update_batch(
        self,
        db: Session,
        batch_id: int,
        batch_in: "ProductionBatchUpdate",
        workspace_id: int,
        user_id: int
    ) -> ProductionBatch:
        """Update an existing production batch."""
        try:
            batch = self.batch_manager.update_batch(
                session=db,
                batch_id=batch_id,
                batch_data=batch_in,
                workspace_id=workspace_id,
                user_id=user_id
            )
            self._commit_transaction(db)
            db.refresh(batch)
            return batch
        except ValueError as e:
            self._rollback_transaction(db)
            error_msg = str(e)
            if "not found" in error_msg:
                raise NotFoundError(error_msg)
            raise BusinessRuleError(error_msg)
        except Exception:
            self._rollback_transaction(db)
            raise

    def delete_batch(
        self,
        db: Session,
        batch_id: int,
        workspace_id: int
    ) -> None:
        """Delete (cancel) a draft batch."""
        try:
            self.batch_manager.delete_batch(
                session=db,
                batch_id=batch_id,
                workspace_id=workspace_id
            )
            self._commit_transaction(db)
        except ValueError as e:
            self._rollback_transaction(db)
            error_msg = str(e)
            if "not found" in error_msg:
                raise NotFoundError(error_msg)
            raise BusinessRuleError(error_msg)
        except Exception:
            self._rollback_transaction(db)
            raise

    # ─── Batch Workflow Operations ──────────────────────────────────

    def start_batch(
        self,
        db: Session,
        batch_id: int,
        workspace_id: int,
        user_id: int,
        target_output_quantity: Optional[int] = None
    ) -> ProductionBatch:
        """
        Start a production batch (draft → in_progress).

        If formula is attached, calculates expected values and creates batch items.
        """
        try:
            batch = self.batch_manager.start_batch(
                session=db,
                batch_id=batch_id,
                workspace_id=workspace_id,
                user_id=user_id,
                target_output_quantity=target_output_quantity
            )
            self._commit_transaction(db)
            db.refresh(batch)
            return batch
        except ValueError as e:
            self._rollback_transaction(db)
            error_msg = str(e)
            if "not found" in error_msg:
                raise NotFoundError(error_msg)
            raise BusinessRuleError(error_msg)
        except Exception:
            self._rollback_transaction(db)
            raise

    def complete_batch(
        self,
        db: Session,
        batch_id: int,
        workspace_id: int,
        user_id: int,
        actual_output_quantity: Optional[int] = None,
        actual_duration_minutes: Optional[int] = None,
        notes: Optional[str] = None
    ) -> ProductionBatch:
        """
        Complete a production batch (in_progress → completed).

        Calculates variance between expected and actual values.
        """
        try:
            batch = self.batch_manager.complete_batch(
                session=db,
                batch_id=batch_id,
                workspace_id=workspace_id,
                user_id=user_id,
                actual_output_quantity=actual_output_quantity,
                actual_duration_minutes=actual_duration_minutes,
                notes=notes
            )
            self._commit_transaction(db)
            db.refresh(batch)
            return batch
        except ValueError as e:
            self._rollback_transaction(db)
            error_msg = str(e)
            if "not found" in error_msg:
                raise NotFoundError(error_msg)
            raise BusinessRuleError(error_msg)
        except Exception:
            self._rollback_transaction(db)
            raise

    def cancel_batch(
        self,
        db: Session,
        batch_id: int,
        workspace_id: int,
        user_id: int,
        notes: Optional[str] = None
    ) -> ProductionBatch:
        """Cancel a production batch."""
        try:
            batch = self.batch_manager.cancel_batch(
                session=db,
                batch_id=batch_id,
                workspace_id=workspace_id,
                user_id=user_id,
                notes=notes
            )
            self._commit_transaction(db)
            db.refresh(batch)
            return batch
        except ValueError as e:
            self._rollback_transaction(db)
            error_msg = str(e)
            if "not found" in error_msg:
                raise NotFoundError(error_msg)
            raise BusinessRuleError(error_msg)
        except Exception:
            self._rollback_transaction(db)
            raise

    # ─── Batch Item Operations ──────────────────────────────────────

    def add_batch_item(
        self,
        db: Session,
        item_in: "ProductionBatchItemCreate",
        workspace_id: int
    ) -> ProductionBatchItem:
        """Add an item to a batch."""
        try:
            batch_item = self.batch_manager.add_batch_item(
                session=db,
                item_data=item_in,
                workspace_id=workspace_id
            )
            self._commit_transaction(db)
            db.refresh(batch_item)
            return batch_item
        except ValueError as e:
            self._rollback_transaction(db)
            error_msg = str(e)
            if "not found" in error_msg:
                raise NotFoundError(error_msg)
            raise BusinessRuleError(error_msg)
        except Exception:
            self._rollback_transaction(db)
            raise

    def update_batch_item(
        self,
        db: Session,
        batch_item_id: int,
        item_in: "ProductionBatchItemUpdate",
        workspace_id: int
    ) -> ProductionBatchItem:
        """Update a batch item."""
        try:
            batch_item = self.batch_manager.update_batch_item(
                session=db,
                batch_item_id=batch_item_id,
                item_data=item_in,
                workspace_id=workspace_id
            )
            self._commit_transaction(db)
            db.refresh(batch_item)
            return batch_item
        except ValueError as e:
            self._rollback_transaction(db)
            error_msg = str(e)
            if "not found" in error_msg:
                raise NotFoundError(error_msg)
            raise BusinessRuleError(error_msg)
        except Exception:
            self._rollback_transaction(db)
            raise

    def remove_batch_item(
        self,
        db: Session,
        batch_item_id: int,
        workspace_id: int
    ) -> None:
        """Remove an item from a batch."""
        try:
            self.batch_manager.remove_batch_item(
                session=db,
                batch_item_id=batch_item_id,
                workspace_id=workspace_id
            )
            self._commit_transaction(db)
        except ValueError as e:
            self._rollback_transaction(db)
            error_msg = str(e)
            if "not found" in error_msg:
                raise NotFoundError(error_msg)
            raise BusinessRuleError(error_msg)
        except Exception:
            self._rollback_transaction(db)
            raise

    def get_batch_items(
        self,
        db: Session,
        batch_id: int,
        workspace_id: int,
        item_role: Optional[str] = None
    ) -> List[ProductionBatchItem]:
        """Get items for a batch with optional role filter."""
        try:
            return self.batch_manager.get_batch_items(
                session=db,
                batch_id=batch_id,
                workspace_id=workspace_id,
                item_role=item_role
            )
        except ValueError as e:
            error_msg = str(e)
            if "not found" in error_msg:
                raise NotFoundError(error_msg)
            raise BusinessRuleError(error_msg)


# Singleton instance
production_batch_service = ProductionBatchService()
