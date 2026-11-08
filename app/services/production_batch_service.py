"""Production Batch Service for orchestrating production batch workflows"""
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from sqlalchemy.orm import Session
from app.services.base_service import BaseService
from app.managers.production_batch_manager import production_batch_manager
from app.models.production_batch import ProductionBatch
from app.models.production_batch_program import ProductionBatchProgram
from app.models.production_batch_item import ProductionBatchItem
from app.models.production_batch_stage_item import ProductionBatchStageItem
from app.models.production_batch_stage_parameter import ProductionBatchStageParameter
from app.schemas.production_batch_stage_parameter import ProductionBatchStageParameterUpdate
from app.schemas.production_batch_event import ProductionBatchEventResponse
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
            return self.batch_manager.annotate_batch_totals(db, [batch])[0]
        except ValueError as e:
            self._rollback_transaction(db)
            raise BusinessRuleError(str(e))
        except Exception:
            self._rollback_transaction(db)
            raise

    def create_program(
        self,
        db: Session,
        *,
        factory_id: int,
        formula_id: int,
        first_start_at: datetime,
        cadence: str,
        end_date: date,
        workspace_id: int,
        user_id: int,
        interval_days: int | None = None,
    ) -> ProductionBatchProgram:
        """Create a program and its draft batches in one transaction."""
        try:
            program = self.batch_manager.create_program(
                db,
                factory_id=factory_id,
                formula_id=formula_id,
                first_start_at=first_start_at,
                cadence=cadence,
                end_date=end_date,
                workspace_id=workspace_id,
                user_id=user_id,
                interval_days=interval_days,
            )
            self._commit_transaction(db)
            db.refresh(program)
            return program
        except ValueError as e:
            self._rollback_transaction(db)
            raise BusinessRuleError(str(e))
        except Exception:
            self._rollback_transaction(db)
            raise

    def stop_program(
        self,
        db: Session,
        program_id: int,
        workspace_id: int,
        user_id: int,
    ) -> ProductionBatchProgram:
        """Stop a program and cancel its draft batches in one transaction."""
        try:
            program = self.batch_manager.stop_program(
                db, program_id, workspace_id, user_id
            )
            self._commit_transaction(db)
            db.refresh(program)
            return program
        except ValueError as e:
            self._rollback_transaction(db)
            raise BusinessRuleError(str(e))
        except Exception:
            self._rollback_transaction(db)
            raise

    def get_programs(
        self,
        db: Session,
        *,
        workspace_id: int,
        factory_id: int | None = None,
    ) -> List[ProductionBatchProgram]:
        """List programs in this workspace, optionally scoped to one factory."""
        return self.batch_manager.get_programs(
            db, workspace_id=workspace_id, factory_id=factory_id
        )

    def program_batch_counts(
        self,
        db: Session,
        *,
        program_ids: List[int],
        workspace_id: int,
    ) -> dict[int, int]:
        """Batch counts for the given programs, scoped to the workspace."""
        return self.batch_manager.count_batches_for_programs(
            db, program_ids=program_ids, workspace_id=workspace_id
        )

    def program_batches(
        self,
        db: Session,
        *,
        program_ids: List[int],
        workspace_id: int,
    ) -> List[ProductionBatch]:
        """Batches for the given programs, scoped to the workspace."""
        return self.batch_manager.batches_for_programs(
            db, program_ids=program_ids, workspace_id=workspace_id
        )

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
        return self.batch_manager.attach_batch_read_model(db, batch)

    def get_batches(
        self,
        db: Session,
        workspace_id: int,
        production_line_id: Optional[int] = None,
        formula_id: Optional[int] = None,
        status: Optional[str] = None,
        sales_order_item_id: Optional[int] = None,
        factory_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[ProductionBatch]:
        """Get batches with optional filtering."""
        rows = self.batch_manager.get_batches(
            session=db,
            workspace_id=workspace_id,
            production_line_id=production_line_id,
            formula_id=formula_id,
            status=status,
            sales_order_item_id=sales_order_item_id,
            factory_id=factory_id,
            skip=skip,
            limit=limit,
        )
        return self.batch_manager.annotate_batch_totals(db, rows)

    def get_batch_stats(
        self,
        db: Session,
        workspace_id: int,
        factory_id: Optional[int] = None,
    ):
        return self.batch_manager.get_batch_stats(
            session=db, workspace_id=workspace_id, factory_id=factory_id
        )

    def get_overview_stats(
        self,
        db: Session,
        workspace_id: int,
        factory_id: int | None,
        date_from: date,
        date_to: date,
        production_line_id: Optional[int] = None,
        statuses: Optional[List[str]] = None,
    ):
        return self.batch_manager.get_overview_stats(
            session=db,
            workspace_id=workspace_id,
            factory_id=factory_id,
            date_from=date_from,
            date_to=date_to,
            production_line_id=production_line_id,
            statuses=statuses,
        )

    def get_batch_activity_counts(
        self,
        db: Session,
        workspace_id: int,
        factory_id: int | None,
        date_from: date,
        date_to: date,
        production_line_ids: Optional[List[int]] = None,
        formula_ids: Optional[List[int]] = None,
        statuses: Optional[List[str]] = None,
    ):
        days = self.batch_manager.get_batch_activity_counts(
            session=db,
            workspace_id=workspace_id,
            factory_id=factory_id,
            date_from=date_from,
            date_to=date_to,
            production_line_ids=production_line_ids,
            formula_ids=formula_ids,
            statuses=statuses,
        )
        return {"date_from": date_from, "date_to": date_to, "days": days}

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
            return self.batch_manager.annotate_batch_totals(db, [batch])[0]
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
        workspace_id: int,
        user_id: int,
    ) -> None:
        """Delete (cancel) a draft batch."""
        try:
            self.batch_manager.delete_batch(
                session=db,
                batch_id=batch_id,
                workspace_id=workspace_id,
                user_id=user_id,
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

    def revert_batch_to_draft(
        self,
        db: Session,
        batch_id: int,
        workspace_id: int,
        user_id: int,
    ) -> ProductionBatch:
        """Planned → draft for editing before start."""
        try:
            batch = self.batch_manager.revert_batch_to_draft(
                session=db,
                batch_id=batch_id,
                workspace_id=workspace_id,
                user_id=user_id,
            )
            self._commit_transaction(db)
            db.refresh(batch)
            return self.batch_manager.annotate_batch_totals(db, [batch])[0]
        except ValueError as e:
            self._rollback_transaction(db)
            error_msg = str(e)
            if "not found" in error_msg:
                raise NotFoundError(error_msg)
            raise BusinessRuleError(error_msg)
        except Exception:
            self._rollback_transaction(db)
            raise

    def start_batch(
        self,
        db: Session,
        batch_id: int,
        workspace_id: int,
        user_id: int,
        target_output_quantity: Optional[int] = None,
        started_at: Optional[datetime] = None,
    ) -> ProductionBatch:
        """
        Start a production batch (draft or recurring → in_progress).

        If formula is attached, calculates expected values and creates batch items.
        """
        try:
            batch = self.batch_manager.start_batch(
                session=db,
                batch_id=batch_id,
                workspace_id=workspace_id,
                user_id=user_id,
                target_output_quantity=target_output_quantity,
                started_at=started_at,
            )
            self._commit_transaction(db)
            db.refresh(batch)
            return self.batch_manager.annotate_batch_totals(db, [batch])[0]
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
        notes: Optional[str] = None,
        completed_at: Optional[datetime] = None,
    ) -> ProductionBatch:
        """
        Complete a production batch (in_progress → completed).

        Auto-posts outputs/byproducts to finished goods and waste to damaged ledger.
        """
        try:
            batch = self.batch_manager.complete_batch(
                session=db,
                batch_id=batch_id,
                workspace_id=workspace_id,
                user_id=user_id,
                actual_output_quantity=actual_output_quantity,
                actual_duration_minutes=actual_duration_minutes,
                notes=notes,
                completed_at=completed_at,
            )
            self._commit_transaction(db)
            db.refresh(batch)
            return self.batch_manager.annotate_batch_totals(db, [batch])[0]
        except ValueError as e:
            self._rollback_transaction(db)
            error_msg = str(e)
            if "not found" in error_msg.lower():
                if "production batch" in error_msg.lower():
                    raise NotFoundError(error_msg)
                raise BusinessRuleError(error_msg)
            raise BusinessRuleError(error_msg)
        except Exception:
            self._rollback_transaction(db)
            raise

    def post_outputs_to_finished_goods(
        self,
        db: Session,
        batch_id: int,
        workspace_id: int,
        user_id: int,
        include_byproducts: bool = True,
    ) -> ProductionBatch:
        """Post a completed batch's outputs to factory finished goods (products)."""
        try:
            self.batch_manager.post_outputs_to_finished_goods(
                session=db,
                batch_id=batch_id,
                workspace_id=workspace_id,
                user_id=user_id,
                include_byproducts=include_byproducts,
            )
            self._commit_transaction(db)
            batch = self.batch_manager.get_batch(db, batch_id, workspace_id)
            if not batch:
                raise NotFoundError(f"Production batch with ID {batch_id} not found")
            db.refresh(batch)
            return self.batch_manager.annotate_batch_totals(db, [batch])[0]
        except ValueError as e:
            self._rollback_transaction(db)
            error_msg = str(e)
            if "not found" in error_msg.lower():
                if "production batch" in error_msg.lower():
                    raise NotFoundError(error_msg)
                raise BusinessRuleError(error_msg)
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
            return self.batch_manager.annotate_batch_totals(db, [batch])[0]
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
        workspace_id: int,
        user_id: int | None = None,
    ) -> ProductionBatchItem:
        """Add an item to a batch."""
        try:
            batch_item = self.batch_manager.add_batch_item(
                session=db,
                item_data=item_in,
                workspace_id=workspace_id,
                user_id=user_id,
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
        workspace_id: int,
        user_id: int,
    ) -> ProductionBatchItem:
        """Update a batch item."""
        try:
            batch_item = self.batch_manager.update_batch_item(
                session=db,
                batch_item_id=batch_item_id,
                item_data=item_in,
                workspace_id=workspace_id,
                user_id=user_id,
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

    def get_batch_stage_parameters(
        self, db: Session, batch_id: int, workspace_id: int
    ) -> List[ProductionBatchStageParameter]:
        try:
            return self.batch_manager.get_batch_stage_parameters(db, batch_id, workspace_id)
        except ValueError as e:
            error_msg = str(e)
            if "not found" in error_msg:
                raise NotFoundError(error_msg)
            raise BusinessRuleError(error_msg)

    def get_batch_stage_log_parameters(
        self, db: Session, batch_id: int, log_id: int, workspace_id: int
    ) -> List[ProductionBatchStageParameter]:
        try:
            return self.batch_manager.get_batch_stage_log_parameters(
                db, batch_id, log_id, workspace_id
            )
        except ValueError as e:
            error_msg = str(e)
            if "not found" in error_msg:
                raise NotFoundError(error_msg)
            raise BusinessRuleError(error_msg)

    def get_batch_stage_items(
        self, db: Session, batch_id: int, workspace_id: int
    ) -> List[ProductionBatchStageItem]:
        try:
            return self.batch_manager.get_batch_stage_items(db, batch_id, workspace_id)
        except ValueError as e:
            error_msg = str(e)
            if "not found" in error_msg:
                raise NotFoundError(error_msg)
            raise BusinessRuleError(error_msg)

    def update_batch_stage_item_actual(
        self,
        db: Session,
        item_row_id: int,
        actual_quantity: Optional[Decimal],
        workspace_id: int,
        user_id: Optional[int] = None,
    ) -> ProductionBatchStageItem:
        try:
            row = self.batch_manager.update_batch_stage_item_actual(
                db, item_row_id, actual_quantity, workspace_id, user_id=user_id
            )
            self._commit_transaction(db)
            db.refresh(row)
            return row
        except ValueError as e:
            self._rollback_transaction(db)
            error_msg = str(e)
            if "not found" in error_msg:
                raise NotFoundError(error_msg)
            raise BusinessRuleError(error_msg)
        except Exception:
            self._rollback_transaction(db)
            raise

    def update_batch_stage_parameter(
        self,
        db: Session,
        parameter_id: int,
        param_in: ProductionBatchStageParameterUpdate,
        workspace_id: int,
        user_id: int,
    ) -> ProductionBatchStageParameter:
        try:
            param = self.batch_manager.update_batch_stage_parameter(
                db, parameter_id, param_in, workspace_id, user_id=user_id
            )
            self._commit_transaction(db)
            db.refresh(param)
            return param
        except ValueError as e:
            self._rollback_transaction(db)
            error_msg = str(e)
            if "not found" in error_msg:
                raise NotFoundError(error_msg)
            raise BusinessRuleError(error_msg)
        except Exception:
            self._rollback_transaction(db)
            raise

    def set_batch_stage_parameter_by_source(
        self,
        db: Session,
        batch_id: int,
        log_id: int,
        source_parameter_id: int,
        param_in: ProductionBatchStageParameterUpdate,
        workspace_id: int,
        user_id: int,
    ) -> ProductionBatchStageParameter:
        try:
            param = self.batch_manager.set_batch_stage_parameter_by_source(
                session=db,
                batch_id=batch_id,
                log_id=log_id,
                source_parameter_id=source_parameter_id,
                param_data=param_in,
                workspace_id=workspace_id,
                user_id=user_id,
            )
            self._commit_transaction(db)
            db.refresh(param)
            return param
        except ValueError as e:
            self._rollback_transaction(db)
            error_msg = str(e)
            if "not found" in error_msg:
                raise NotFoundError(error_msg)
            raise BusinessRuleError(error_msg)
        except Exception:
            self._rollback_transaction(db)
            raise

    # ─── Batch Stage Log Operations ─────────────────────────────────

    def get_batch_stage_logs(
        self, db: Session, batch_id: int, workspace_id: int
    ) -> List["ProductionBatchStageLog"]:
        try:
            return self.batch_manager.get_batch_stage_logs(db, batch_id, workspace_id)
        except ValueError as e:
            raise NotFoundError(str(e))

    def add_batch_stage_log(
        self,
        db: Session,
        log_in: "ProductionBatchStageLogCreate",
        workspace_id: int,
        user_id: int,
    ) -> "ProductionBatchStageLog":
        try:
            log = self.batch_manager.add_batch_stage_log(db, log_in, workspace_id, user_id)
            self._commit_transaction(db)
            db.refresh(log)
            return log
        except ValueError as e:
            self._rollback_transaction(db)
            error_msg = str(e)
            if "not found" in error_msg:
                raise NotFoundError(error_msg)
            raise BusinessRuleError(error_msg)
        except Exception:
            self._rollback_transaction(db)
            raise

    def update_batch_stage_log(
        self,
        db: Session,
        log_id: int,
        log_in: "ProductionBatchStageLogUpdate",
        workspace_id: int,
        user_id: int,
    ) -> "ProductionBatchStageLog":
        try:
            log = self.batch_manager.update_batch_stage_log(db, log_id, log_in, workspace_id, user_id)
            self._commit_transaction(db)
            db.refresh(log)
            from app.utils.production_stage_metrics import attach_stage_metrics
            return attach_stage_metrics(log)
        except ValueError as e:
            self._rollback_transaction(db)
            error_msg = str(e)
            if "not found" in error_msg:
                raise NotFoundError(error_msg)
            raise BusinessRuleError(error_msg)
        except Exception:
            self._rollback_transaction(db)
            raise


    def start_stage_log(self, db, log_id, workspace_id, user_id, started_at=None, machine_id=None):
        return self._stage_action(
            db, lambda: self.batch_manager.start_stage_log(
                db, log_id, workspace_id, user_id, started_at=started_at, machine_id=machine_id
            )
        )

    def finish_stage_log(self, db, log_id, workspace_id, user_id, **kwargs):
        return self._stage_action(
            db, lambda: self.batch_manager.finish_stage_log(db, log_id, workspace_id, user_id, **kwargs)
        )

    def log_stage_as_planned(self, db, log_id, workspace_id, user_id, **kwargs):
        return self._stage_action(
            db, lambda: self.batch_manager.log_stage_as_planned(db, log_id, workspace_id, user_id, **kwargs)
        )

    def get_schedule(self, db, workspace_id, factory_id: int | None, start, end):
        return self.batch_manager.get_schedule(db, workspace_id, factory_id, start, end)

    def move_stage_log_on_schedule(
        self,
        db,
        log_id: int,
        workspace_id: int,
        user_id: int,
        *,
        production_line_id: int,
        planned_start_at,
        machine_id=None,
    ):
        return self._stage_action(
            db,
            lambda: self.batch_manager.move_stage_log_on_schedule(
                db,
                log_id,
                workspace_id,
                user_id,
                production_line_id=production_line_id,
                planned_start_at=planned_start_at,
                machine_id=machine_id,
            ),
        )

    def linked_orders(self, db, batch_id, workspace_id):
        try:
            return self.batch_manager.linked_orders(db, batch_id, workspace_id)
        except ValueError as exc:
            raise NotFoundError(str(exc)) from exc

    def list_batch_events(
        self,
        db: Session,
        batch_id: int,
        workspace_id: int,
        skip: int = 0,
        limit: int = 100,
    ) -> List[ProductionBatchEventResponse]:
        try:
            rows = self.batch_manager.list_batch_events(
                db, batch_id, workspace_id, skip=skip, limit=limit
            )
            return [
                ProductionBatchEventResponse(
                    id=event.id,
                    workspace_id=event.workspace_id,
                    batch_id=event.batch_id,
                    batch_stage_log_id=event.batch_stage_log_id,
                    event_type=event.event_type,
                    description=event.description,
                    metadata=event.metadata_json,
                    performed_by=event.performed_by,
                    user_name=performer.name if performer else None,
                    created_at=event.created_at,
                )
                for event, performer in rows
            ]
        except ValueError as exc:
            raise NotFoundError(str(exc)) from exc

    def _stage_action(self, db, action):
        from app.utils.production_stage_metrics import attach_stage_metrics
        try:
            log = action()
            self._commit_transaction(db)
            db.refresh(log)
            return attach_stage_metrics(log)
        except ValueError as exc:
            self._rollback_transaction(db)
            message = str(exc)
            if "not found" in message:
                raise NotFoundError(message) from exc
            raise BusinessRuleError(message) from exc
        except Exception:
            self._rollback_transaction(db)
            raise


# Singleton instance
production_batch_service = ProductionBatchService()
