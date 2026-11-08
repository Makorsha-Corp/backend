"""Production Batch Manager for business logic"""
from collections import defaultdict
from typing import List, Optional
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session
from app.managers.base_manager import BaseManager
from app.models.production_batch import ProductionBatch
from app.models.production_batch_item import ProductionBatchItem
from app.models.production_batch_stage_log import ProductionBatchStageLog
from app.models.production_batch_stage_parameter import ProductionBatchStageParameter
from app.dao.production_batch import production_batch_dao
from app.dao.production_batch_program import ProductionBatchProgramDAO
from app.models.production_batch_program import ProductionBatchProgram
from app.utils.production_program_occurrences import occurrence_starts
from app.dao.production_batch_item import production_batch_item_dao
from app.dao.production_line import production_line_dao
from app.dao.factory import factory_dao
from app.dao.production_line_machine import production_line_machine_dao
from app.dao.production_formula import production_formula_dao
from app.utils.recipe_derived_metrics import finished_good_output_quantity, last_formula_stage
from app.dao.production_formula_stage import production_formula_stage_dao
from app.dao.production_formula_stage_item import production_formula_stage_item_dao
from app.dao.production_formula_stage_parameter import production_formula_stage_parameter_dao
from app.dao.production_batch_stage_log import production_batch_stage_log_dao
from app.dao.production_batch_stage_parameter import production_batch_stage_parameter_dao
from app.dao.production_batch_event import production_batch_event_dao
from app.dao.profile import profile_dao
from app.models.production_batch_event import ProductionBatchEvent
from app.utils.production_line_machines import assert_production_line_assignable
from app.utils.production_machine_pick_policy import (
    assert_machine_pick_allowed_for_batch_step,
    machine_has_other_in_progress_step,
    parse_production_machine_pick_policy,
)
from app.dao.workspace import workspace_dao
from app.models.machine import Machine
from app.utils.production_batch_event_logging import (
    build_step_event_snapshot,
    log_batch_event,
    log_batch_item_quantity_events,
    log_batch_update_events,
    log_condition_actual_event,
    log_stage_log_update_events,
    _serialize_value,
)
from app.dao.production_route import production_route_step_dao
from app.models.production_route import ProductionRoute
from app.dao.item import item_dao
from app.dao.inventory import inventory_dao
from app.dao.inventory_ledger import inventory_ledger_dao
from app.dao.product_ledger import product_ledger_dao
from app.managers.product_manager import product_manager
from app.models.enums import InventoryTypeEnum
from app.schemas.production_batch import ProductionBatchCreate, ProductionBatchUpdate
from app.schemas.production_batch_item import ProductionBatchItemCreate, ProductionBatchItemUpdate
from app.schemas.production_batch_stage_log import (
    ProductionBatchStageLogCreate,
    ProductionBatchStageLogUpdate,
)
from app.schemas.production_batch_stage_parameter import ProductionBatchStageParameterUpdate
from app.utils.production_parameter_numeric import optional_numeric_from_text
from app.utils.production_stage_metrics import (
    assign_sequential_planned_starts,
    attach_stage_metrics,
    duration_minutes,
    planned_end_at,
    step_planned_windows,
)
from app.utils.step_schedule_move import compute_move_planned_start_updates
from app.utils.production_output_cost import unit_cost_from_raw
from app.dao.production_batch_stage_item import production_batch_stage_item_dao
from app.utils.batch_step_wip import (
    compute_remaining_wip,
    compute_wip_available_by_item,
    group_step_start_storage_inputs,
    leftover_handoff_lines,
    leftover_intermediate_wip,
    storage_needed_after_wip,
)
from app.utils.production_quantity import as_quantity, scale_quantity
from app.utils.time import as_utc, reject_future_started_at, utcnow
from app.dao.workspace_shift import workspace_shift_dao
from app.utils.workspace_shift_windows import find_shift_for_local_datetime, wall_clock_for_shift


def require_linkable_production_batch(session: Session, batch_id: int, workspace_id: int) -> ProductionBatch:
    batch = (
        session.query(ProductionBatch)
        .filter(ProductionBatch.id == batch_id, ProductionBatch.workspace_id == workspace_id)
        .first()
    )
    if not batch:
        raise ValueError(f"Production batch {batch_id} not found")
    if batch.status == "cancelled":
        raise ValueError(f"Production batch {batch.batch_number} is cancelled")
    return batch


class ProductionBatchManager(BaseManager[ProductionBatch]):
    """
    STANDALONE MANAGER: Production batch business logic.

    Manages: ProductionBatch and ProductionBatchItem entities
    Operations: CRUD, batch workflow (start, complete, cancel), variance calculation

    Does NOT commit transactions - that's the service layer's responsibility.
    """

    VALID_STATUSES = {'draft', 'recurring', 'in_progress', 'completed', 'cancelled'}
    PRE_START_STATUSES = frozenset({'draft', 'recurring'})
    VALID_ITEM_ROLES = {'input', 'output', 'waste', 'byproduct'}
    VALID_STAGE_LOG_STATUSES = {'pending', 'in_progress', 'completed', 'skipped'}

    def __init__(self):
        super().__init__(ProductionBatch)
        self.batch_dao = production_batch_dao
        self.program_dao = ProductionBatchProgramDAO(ProductionBatchProgram)
        self.workspace_shift_dao = workspace_shift_dao
        self.batch_item_dao = production_batch_item_dao
        self.formula_dao = production_formula_dao
        self.formula_stage_dao = production_formula_stage_dao
        self.stage_log_dao = production_batch_stage_log_dao
        self.batch_event_dao = production_batch_event_dao

    # ─── Batch CRUD ─────────────────────────────────────────────────

    def _shift_fields_from_planned(
        self,
        session: Session,
        *,
        workspace_id: int,
        planned_start_at: Optional[datetime],
    ) -> dict:
        if planned_start_at is None:
            return {"shift_id": None, "shift": None}
        shifts = self.workspace_shift_dao.get_active_by_workspace(session, workspace_id=workspace_id)
        matched = find_shift_for_local_datetime(
            wall_clock_for_shift(
                planned_start_at,
                self._workspace_timezone_name(session, workspace_id),
            ),
            shifts,
        )
        if not matched:
            return {"shift_id": None, "shift": None}
        return {"shift_id": matched.id, "shift": matched.name}

    def _shift_fields_from_instant(
        self,
        session: Session,
        *,
        workspace_id: int,
        when: datetime,
    ) -> dict:
        return self._shift_fields_from_planned(session, workspace_id=workspace_id, planned_start_at=when)

    def _workspace_timezone_name(self, session: Session, workspace_id: int) -> str | None:
        """IANA timezone from workspace settings, same source as shift assignment."""
        workspace = workspace_dao.get(session, id=workspace_id)
        settings = workspace.settings if workspace is not None else None
        tz_name = settings.get("timezone") if isinstance(settings, dict) else None
        return str(tz_name) if tz_name else None

    def create_batch(
        self,
        session: Session,
        batch_data: ProductionBatchCreate,
        workspace_id: int,
        user_id: int
    ) -> ProductionBatch:
        """
        Create a new production batch.

        Validates:
        - Production line exists and belongs to workspace
        - Formula exists and belongs to workspace (if provided)
        - Auto-generates batch_number

        If formula_id is provided and status is 'draft', expected values
        can be populated later via start_batch.
        """
        # Validate production line
        line = production_line_dao.get_by_id_and_workspace(
            session, id=batch_data.production_line_id, workspace_id=workspace_id
        )
        if not line:
            raise ValueError(f"Production line {batch_data.production_line_id} not found")
        if not line.is_active:
            raise ValueError(f"Production line {batch_data.production_line_id} is not active")

        if batch_data.machine_id is not None:
            self._validate_machine_on_line(
                session,
                machine_id=batch_data.machine_id,
                production_line_id=batch_data.production_line_id,
                workspace_id=workspace_id,
            )

        # Validate formula if provided
        if batch_data.formula_id is not None:
            formula = self.formula_dao.get_by_id_and_workspace(
                session, id=batch_data.formula_id, workspace_id=workspace_id
            )
            if not formula:
                raise ValueError(f"Production formula {batch_data.formula_id} not found")
            if not formula.is_active:
                raise ValueError(f"Production formula {batch_data.formula_id} is not active")

        # Generate batch number
        batch_number = self.batch_dao.generate_batch_number(session, workspace_id=workspace_id)

        # Build creation dict
        batch_dict = batch_data.model_dump(
            exclude={
                "stage_seeds",
                "item_seeds",
                "parameter_seeds",
                "expected_output_quantity",
                "expected_duration_minutes",
                "actual_output_quantity",
                "actual_duration_minutes",
            }
        )
        planned = batch_dict.get("planned_start_at")
        if planned is not None:
            batch_dict.update(
                self._shift_fields_from_planned(
                    session, workspace_id=workspace_id, planned_start_at=planned
                )
            )
        elif batch_dict.get("shift_id"):
            row = self.workspace_shift_dao.get_by_id_and_workspace(
                session, shift_id=batch_dict["shift_id"], workspace_id=workspace_id
            )
            if row:
                batch_dict["shift"] = row.name
        batch_dict['workspace_id'] = workspace_id
        batch_dict['batch_number'] = batch_number
        batch_dict['created_by'] = user_id
        stage_seeds = batch_data.stage_seeds
        item_seeds = batch_data.item_seeds
        parameter_seeds = batch_data.parameter_seeds

        if batch_data.sales_order_item_id is not None:
            self._validate_sales_order_item(session, batch_data.sales_order_item_id, workspace_id)

        batch = self.batch_dao.create(session, obj_in=batch_dict)

        if batch_data.machine_id is not None:
            self._enforce_machine_pick_policy(
                session,
                workspace_id=workspace_id,
                machine_id=batch_data.machine_id,
                batch=batch,
                stage_log=None,
            )

        if batch_data.formula_id is not None:
            formula = self.formula_dao.get_by_id_and_workspace(
                session, id=batch_data.formula_id, workspace_id=workspace_id
            )
            if formula and formula.route_id:
                if line.factory_id != self._route_factory_id(session, formula.route_id, workspace_id):
                    raise ValueError("Formula route belongs to a different factory")
                batch = self.batch_dao.update(session, db_obj=batch, obj_in={"route_id": formula.route_id})
            self._seed_stage_logs_from_formula(
                session,
                batch=batch,
                formula_id=batch_data.formula_id,
                workspace_id=workspace_id,
                stage_seeds=stage_seeds,
                parameter_seeds=parameter_seeds,
                target_output=batch_data.expected_output_quantity,
            )
            self._seed_batch_items_from_formula(
                session,
                batch=batch,
                formula_id=batch_data.formula_id,
                workspace_id=workspace_id,
                item_seeds=item_seeds,
                target_output=batch_data.expected_output_quantity,
            )
            self._sync_sequential_planned_starts_for_batch(session, batch, workspace_id)

        log_batch_event(
            session,
            workspace_id=workspace_id,
            batch_id=batch.id,
            event_type="batch_created",
            description="Batch created",
            performed_by=user_id,
            metadata={
                "formula_id": batch.formula_id,
                "production_line_id": batch.production_line_id,
            },
        )
        return batch

    def _program_batch_line_id(
        self,
        session: Session,
        *,
        formula_id: int,
        workspace_id: int,
    ) -> int:
        """Line of the first included recipe step that has a line."""
        stages = self.formula_stage_dao.get_by_formula(
            session, formula_id=formula_id, workspace_id=workspace_id
        )
        included = [
            stage for stage in stages if getattr(stage, "is_used", True) is not False
        ]
        if not included:
            raise ValueError("Recipe has no steps")
        included.sort(key=lambda stage: stage.stage_order)
        for stage in included:
            line_id = None
            if stage.route_step_id is not None:
                route_step = production_route_step_dao.get_by_id_and_workspace(
                    session, id=stage.route_step_id, workspace_id=workspace_id
                )
                if route_step is not None:
                    line_id = route_step.production_line_id
            if line_id is None:
                line_id = stage.production_line_id
            if line_id is not None:
                return line_id
        raise ValueError("Recipe steps have no production line")

    def _require_program_factory_line(
        self,
        session: Session,
        *,
        factory_id: int,
        line_id: int,
        workspace_id: int,
    ) -> None:
        """Factory and batch line must both exist in this workspace and name the same factory."""
        factory = factory_dao.get_by_id_and_workspace(
            session, id=factory_id, workspace_id=workspace_id
        )
        if not factory:
            raise ValueError(f"Factory {factory_id} not found")
        line = production_line_dao.get_by_id_and_workspace(
            session, id=line_id, workspace_id=workspace_id
        )
        if not line:
            raise ValueError(f"Production line {line_id} not found")
        if line.factory_id != factory_id:
            raise ValueError(f"Production line {line.name} is not in this factory")

    def create_program(
        self,
        session: Session,
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
        """
        Create one program and a draft batch per occurrence.

        Does not commit. Resolves the batch line, then occurrence starts,
        then calls create_batch. program_id is set after each create.
        """
        line_id = self._program_batch_line_id(
            session, formula_id=formula_id, workspace_id=workspace_id
        )
        tz_name = self._workspace_timezone_name(session, workspace_id)
        starts = occurrence_starts(
            first_start_at,
            cadence,
            end_date,
            tz_name,
            interval_days=interval_days,
        )
        self._require_program_factory_line(
            session,
            factory_id=factory_id,
            line_id=line_id,
            workspace_id=workspace_id,
        )
        program = self.program_dao.create(
            session,
            obj_in={
                "workspace_id": workspace_id,
                "factory_id": factory_id,
                "formula_id": formula_id,
                "first_start_at": first_start_at,
                "cadence": cadence,
                "interval_days": interval_days,
                "end_date": end_date,
                "status": "active",
                "created_by": user_id,
            },
        )
        for start in starts:
            batch_in = ProductionBatchCreate(
                production_line_id=line_id,
                formula_id=formula_id,
                planned_start_at=start,
                batch_date=wall_clock_for_shift(start, tz_name).date(),
                status="recurring",
            )
            batch = self.create_batch(session, batch_in, workspace_id, user_id)
            batch.program_id = program.id
            session.flush()
        return program

    def stop_program(
        self,
        session: Session,
        program_id: int,
        workspace_id: int,
        user_id: int,
    ) -> ProductionBatchProgram:
        """Mark the program stopped and cancel its draft batches. Does not commit."""
        program = self.program_dao.get_by_id_and_workspace(
            session, id=program_id, workspace_id=workspace_id
        )
        if program is None:
            raise ValueError(f"Production batch program {program_id} not found")
        program.status = "stopped"
        batches = self.batch_dao.get_by_program(
            session, program_id=program_id, workspace_id=workspace_id
        )
        for batch in batches:
            if batch.status not in self.PRE_START_STATUSES:
                continue
            batch.status = "cancelled"
            log_batch_event(
                session,
                workspace_id=workspace_id,
                batch_id=batch.id,
                event_type="batch_cancelled",
                description="Batch cancelled",
                performed_by=user_id,
            )
        session.flush()
        return program

    def get_programs(
        self,
        session: Session,
        *,
        workspace_id: int,
        factory_id: int | None = None,
    ) -> List[ProductionBatchProgram]:
        """Programs in this workspace, optionally scoped to one factory. Does not commit."""
        return self.program_dao.list_by_workspace(
            session, workspace_id=workspace_id, factory_id=factory_id
        )

    def count_batches_for_programs(
        self,
        session: Session,
        *,
        program_ids: List[int],
        workspace_id: int,
    ) -> dict[int, int]:
        """Workspace-scoped batch counts keyed by program id."""
        return self.batch_dao.count_by_program_ids(
            session, program_ids=program_ids, workspace_id=workspace_id
        )

    def batches_for_programs(
        self,
        session: Session,
        *,
        program_ids: List[int],
        workspace_id: int,
    ) -> List[ProductionBatch]:
        """Workspace-scoped batches that belong to the given programs."""
        return self.batch_dao.get_by_program_ids(
            session, program_ids=program_ids, workspace_id=workspace_id
        )

    def update_batch(
        self,
        session: Session,
        batch_id: int,
        batch_data: ProductionBatchUpdate,
        workspace_id: int,
        user_id: int
    ) -> ProductionBatch:
        """
        Update a production batch (only draft or in_progress batches).

        Cannot update completed or cancelled batches.
        """
        batch = self.batch_dao.get_by_id_and_workspace(
            session, id=batch_id, workspace_id=workspace_id
        )
        if not batch:
            raise ValueError(f"Production batch {batch_id} not found")
        if batch.status in ('completed', 'cancelled'):
            raise ValueError(f"Cannot update a {batch.status} batch")

        update_dict = batch_data.model_dump(exclude_unset=True, exclude_none=True)

        # Don't allow direct status changes via update - use start/complete/cancel
        if 'status' in update_dict:
            raise ValueError("Use start_batch, complete_batch, or cancel_batch to change status")

        # Validate formula if being changed
        if 'formula_id' in update_dict and update_dict['formula_id'] is not None:
            formula = self.formula_dao.get_by_id_and_workspace(
                session, id=update_dict['formula_id'], workspace_id=workspace_id
            )
            if not formula:
                raise ValueError(f"Production formula {update_dict['formula_id']} not found")

        if batch.status in self.PRE_START_STATUSES and "planned_start_at" in update_dict:
            planned = update_dict.get("planned_start_at")
            update_dict.update(
                self._shift_fields_from_planned(
                    session, workspace_id=workspace_id, planned_start_at=planned
                )
            )

        if update_dict.get("sales_order_item_id") is not None:
            self._validate_sales_order_item(session, update_dict["sales_order_item_id"], workspace_id)

        update_dict['updated_by'] = user_id
        log_batch_update_events(
            session, batch=batch, update_dict=update_dict, user_id=user_id
        )
        updated = self.batch_dao.update(session, db_obj=batch, obj_in=update_dict)
        if batch.status in self.PRE_START_STATUSES and "planned_start_at" in update_dict:
            self._sync_sequential_planned_starts_for_batch(session, updated, workspace_id)
        return updated

    def get_batch(
        self,
        session: Session,
        batch_id: int,
        workspace_id: int
    ) -> Optional[ProductionBatch]:
        """Get batch by ID within workspace."""
        return self.batch_dao.get_by_id_and_workspace(
            session, id=batch_id, workspace_id=workspace_id
        )

    def get_batches(
        self,
        session: Session,
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
        if sales_order_item_id is not None:
            return (
                session.query(ProductionBatch)
                .filter(
                    ProductionBatch.workspace_id == workspace_id,
                    ProductionBatch.sales_order_item_id == sales_order_item_id,
                )
                .order_by(ProductionBatch.batch_date.desc())
                .offset(skip)
                .limit(limit)
                .all()
            )
        if production_line_id is not None:
            return self.batch_dao.get_by_production_line(
                session, production_line_id=production_line_id,
                workspace_id=workspace_id, skip=skip, limit=limit
            )
        elif formula_id is not None:
            return self.batch_dao.get_by_formula(
                session, formula_id=formula_id,
                workspace_id=workspace_id, skip=skip, limit=limit
            )
        elif status is not None:
            return self.batch_dao.get_by_status(
                session, status=status,
                workspace_id=workspace_id, skip=skip, limit=limit
            )
        elif factory_id is not None:
            return self.batch_dao.get_by_factory(
                session,
                workspace_id=workspace_id,
                factory_id=factory_id,
                skip=skip,
                limit=limit,
            )
        else:
            return self.batch_dao.get_by_workspace(
                session, workspace_id=workspace_id, skip=skip, limit=limit
            )

    def get_batch_stats(
        self,
        session: Session,
        workspace_id: int,
        factory_id: Optional[int] = None,
    ) -> dict:
        in_progress = self.batch_dao.count_by_status(
            session,
            workspace_id=workspace_id,
            status="in_progress",
            factory_id=factory_id,
        )
        return {"in_progress_count": in_progress, "total_count": in_progress}

    def get_overview_stats(
        self,
        session: Session,
        workspace_id: int,
        factory_id: int | None,
        date_from: date,
        date_to: date,
        production_line_id: Optional[int] = None,
        statuses: Optional[List[str]] = None,
    ) -> dict:
        from app.models.production_batch import ProductionBatch
        from app.models.production_batch_stage_log import ProductionBatchStageLog
        from app.models.production_line import ProductionLine
        from app.utils.production_batch_overview_stats import build_overview_stats

        q = (
            session.query(ProductionBatch)
            .join(ProductionLine, ProductionBatch.production_line_id == ProductionLine.id)
            .filter(
                ProductionBatch.workspace_id == workspace_id,
                ProductionBatch.batch_date >= date_from,
                ProductionBatch.batch_date <= date_to,
            )
        )
        if factory_id is not None:
            q = q.filter(ProductionLine.factory_id == factory_id)
        if production_line_id is not None:
            q = q.filter(ProductionBatch.production_line_id == production_line_id)
        if statuses:
            q = q.filter(ProductionBatch.status.in_(statuses))
        batches = q.all()
        batch_ids = [batch.id for batch in batches]

        logs_by_batch: dict[int, list] = defaultdict(list)
        if batch_ids:
            logs = (
                session.query(ProductionBatchStageLog)
                .filter(
                    ProductionBatchStageLog.workspace_id == workspace_id,
                    ProductionBatchStageLog.batch_id.in_(batch_ids),
                )
                .all()
            )
            for log in logs:
                logs_by_batch[log.batch_id].append(log)

        params_by_log: dict[int, list] = defaultdict(list)
        if batch_ids:
            params = production_batch_stage_parameter_dao.get_by_batch_ids(
                session, batch_ids=batch_ids, workspace_id=workspace_id
            )
            for param in params:
                if param.batch_stage_log_id is not None:
                    params_by_log[param.batch_stage_log_id].append(param)

        line_ids: set[int] = set()
        for batch in batches:
            line_ids.add(batch.production_line_id)
        for logs in logs_by_batch.values():
            for log in logs:
                if log.production_line_id is not None:
                    line_ids.add(log.production_line_id)

        line_names: dict[int, str] = {}
        if line_ids:
            for line in (
                session.query(ProductionLine)
                .filter(
                    ProductionLine.workspace_id == workspace_id,
                    ProductionLine.id.in_(line_ids),
                )
                .all()
            ):
                line_names[line.id] = line.name

        formula_names: dict[int, str] = {}
        for batch in batches:
            if batch.formula_id is None or batch.formula_id in formula_names:
                continue
            formula = self.formula_dao.get_by_id_and_workspace(
                session, id=batch.formula_id, workspace_id=workspace_id
            )
            if formula:
                formula_names[batch.formula_id] = formula.name

        items_by_batch: dict[int, list] = defaultdict(list)
        if batch_ids:
            for item in self.batch_item_dao.get_by_batch_ids(
                session, batch_ids=batch_ids, workspace_id=workspace_id
            ):
                items_by_batch[item.batch_id].append(item)

        self.annotate_batch_totals(session, batches)
        return build_overview_stats(
            batches=batches,
            logs_by_batch=logs_by_batch,
            params_by_log=params_by_log,
            items_by_batch=items_by_batch,
            line_names=line_names,
            formula_names=formula_names,
            date_from=date_from,
            date_to=date_to,
        )

    def get_batch_activity_counts(
        self,
        session: Session,
        workspace_id: int,
        factory_id: int | None,
        date_from: date,
        date_to: date,
        production_line_ids: Optional[List[int]] = None,
        formula_ids: Optional[List[int]] = None,
        statuses: Optional[List[str]] = None,
    ) -> List[dict]:
        from sqlalchemy import func

        from app.models.production_line import ProductionLine

        q = (
            session.query(ProductionBatch.batch_date, func.count(ProductionBatch.id))
            .join(ProductionLine, ProductionBatch.production_line_id == ProductionLine.id)
            .filter(
                ProductionBatch.workspace_id == workspace_id,
                ProductionBatch.batch_date >= date_from,
                ProductionBatch.batch_date <= date_to,
            )
        )
        if factory_id is not None:
            q = q.filter(ProductionLine.factory_id == factory_id)
        if production_line_ids:
            q = q.filter(ProductionBatch.production_line_id.in_(production_line_ids))
        if formula_ids:
            q = q.filter(ProductionBatch.formula_id.in_(formula_ids))
        if statuses:
            q = q.filter(ProductionBatch.status.in_(statuses))
        rows = q.group_by(ProductionBatch.batch_date).order_by(ProductionBatch.batch_date).all()
        return [{"date": row[0], "count": int(row[1])} for row in rows]

    def delete_batch(
        self,
        session: Session,
        batch_id: int,
        workspace_id: int,
        user_id: int,
    ) -> ProductionBatch:
        """
        Cancel a batch (soft delete via status change).

        Only draft batches can be deleted/cancelled this way.
        In-progress batches should use cancel_batch instead.
        """
        batch = self.batch_dao.get_by_id_and_workspace(
            session, id=batch_id, workspace_id=workspace_id
        )
        if not batch:
            raise ValueError(f"Production batch {batch_id} not found")
        if batch.status not in self.PRE_START_STATUSES:
            raise ValueError(
                f"Only draft or planned batches can be deleted. Current status: {batch.status}. "
                f"Use cancel_batch for in-progress batches."
            )

        log_batch_event(
            session,
            workspace_id=workspace_id,
            batch_id=batch.id,
            event_type="batch_deleted",
            description="Draft deleted",
            performed_by=user_id,
        )
        return self.batch_dao.update(
            session, db_obj=batch, obj_in={'status': 'cancelled'}
        )

    # ─── Batch Workflow ─────────────────────────────────────────────

    def revert_batch_to_draft(
        self,
        session: Session,
        batch_id: int,
        workspace_id: int,
        user_id: int,
    ) -> ProductionBatch:
        """Move a program occurrence from planned back to draft for editing."""
        batch = self.batch_dao.get_by_id_and_workspace(
            session, id=batch_id, workspace_id=workspace_id
        )
        if not batch:
            raise ValueError(f"Production batch {batch_id} not found")
        if batch.status != "recurring":
            raise ValueError(
                f"Only recurring batches can return to draft. Current status: {batch.status}"
            )
        log_batch_event(
            session,
            workspace_id=workspace_id,
            batch_id=batch.id,
            event_type="batch_returned_to_draft",
            description="Returned to draft for editing",
            performed_by=user_id,
        )
        return self.batch_dao.update(
            session,
            db_obj=batch,
            obj_in={"status": "draft", "updated_by": user_id},
        )

    def start_batch(
        self,
        session: Session,
        batch_id: int,
        workspace_id: int,
        user_id: int,
        target_output_quantity: Optional[int] = None,
        started_at: Optional[datetime] = None,
        *,
        via_first_step: bool = False,
    ) -> ProductionBatch:
        """
        Start a production batch (draft or planned → in_progress).

        Batches with route steps deduct storage when each step starts — not here.
        Legacy batches without steps validate and deduct all inputs on batch start.
        """
        batch = self.batch_dao.get_by_id_and_workspace(
            session, id=batch_id, workspace_id=workspace_id
        )
        if not batch:
            raise ValueError(f"Production batch {batch_id} not found")
        if batch.status not in self.PRE_START_STATUSES:
            raise ValueError(
                f"Can only start draft or planned batches. Current status: {batch.status}"
            )

        all_batch_items = self.batch_item_dao.get_by_batch(
            session, batch_id=batch_id, workspace_id=workspace_id
        )
        if not all_batch_items:
            raise ValueError("Cannot start a batch with no items. Add at least one item before starting.")

        stage_logs = self.stage_log_dao.get_by_batch(
            session, batch_id=batch_id, workspace_id=workspace_id
        )
        if not stage_logs:
            line = production_line_dao.get_by_id_and_workspace(
                session, id=batch.production_line_id, workspace_id=workspace_id
            )
            if not line:
                raise ValueError(f"Production line {batch.production_line_id} not found")
            self._validate_and_deduct_batch_inputs(
                session,
                batch=batch,
                workspace_id=workspace_id,
                user_id=user_id,
                default_factory_id=line.factory_id,
                note=f"SYSTEM - PRODUCTION BATCH START | {batch.batch_number}",
            )

        reject_future_started_at(started_at)
        now = started_at or utcnow()
        update_data = {
            'status': 'in_progress',
            'started_by': user_id,
            'started_at': now,
            'actual_start_time': now,
            'updated_by': user_id,
        }
        update_data.update(
            self._shift_fields_from_instant(session, workspace_id=workspace_id, when=now)
        )
        updated = self.batch_dao.update(session, db_obj=batch, obj_in=update_data)
        log_batch_event(
            session,
            workspace_id=workspace_id,
            batch_id=batch_id,
            event_type="batch_started",
            description="Batch started",
            performed_by=user_id,
            metadata={
                "started_at": _serialize_value(now),
                "via_first_step": via_first_step,
                "started_earlier": started_at is not None,
            },
        )
        return updated

    def complete_batch(
        self,
        session: Session,
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

        - Calculates variance between expected and actual values.
        - Auto-posts output/byproduct items to finished goods (products).
        - Auto-posts waste items to damaged ledger.
        - All ledger entries are tagged SYSTEM - PRODUCTION BATCH COMPLETE.
        """
        batch = self.batch_dao.get_by_id_and_workspace(
            session, id=batch_id, workspace_id=workspace_id
        )
        if not batch:
            raise ValueError(f"Production batch {batch_id} not found")
        if batch.status != 'in_progress':
            raise ValueError(f"Can only complete in-progress batches. Current status: {batch.status}")

        # Get factory from production line
        line = production_line_dao.get_by_id_and_workspace(
            session, id=batch.production_line_id, workspace_id=workspace_id
        )
        if not line:
            raise ValueError(f"Production line {batch.production_line_id} not found")
        factory_id = line.factory_id

        now = completed_at or utcnow()
        logs = self.stage_log_dao.get_by_batch(session, batch_id=batch_id, workspace_id=workspace_id)
        open_logs = [log for log in logs if log.status in ("pending", "in_progress")]
        if open_logs:
            names = ", ".join(log.stage_name for log in open_logs)
            raise ValueError(f"Cannot complete batch while steps are open: {names}")

        update_data = {
            'status': 'completed',
            'completed_by': user_id,
            'completed_at': now,
            'updated_by': user_id,
        }
        update_data['actual_end_time'] = now
        if notes is not None:
            update_data['notes'] = notes

        updated_batch = self.batch_dao.update(session, db_obj=batch, obj_in=update_data)
        derived = self._totals_for_batch(session, updated_batch)
        actual_out = derived["actual_output_quantity"]

        # Calculate per-item variances
        self._calculate_batch_item_variances(session, batch_id, workspace_id)

        # Post outputs and byproducts to finished goods
        system_note = f"SYSTEM - PRODUCTION BATCH COMPLETE | {batch.batch_number}"
        all_items = self.batch_item_dao.get_by_batch(session, batch_id=batch_id, workspace_id=workspace_id)
        output_qty_total = Decimal("0")
        posted_products: list[dict] = []
        posted_waste: list[dict] = []
        for bi in all_items:
            if bi.item_role != "output":
                continue
            line_qty = bi.actual_quantity or bi.expected_quantity
            if line_qty and line_qty > 0:
                output_qty_total += as_quantity(line_qty)
        output_unit_cost = self._raw_output_unit_cost(
            session, workspace_id=workspace_id, batch_id=batch_id, output_quantity=output_qty_total
        )

        for bi in all_items:
            qty = bi.actual_quantity or bi.expected_quantity
            if not qty or qty <= 0:
                continue
            posted_qty = as_quantity(qty)
            if bi.item_role in ("output", "byproduct"):
                posted_products.append(
                    {"item_id": bi.item_id, "qty": posted_qty, "role": bi.item_role}
                )
            elif bi.item_role == "waste":
                posted_waste.append({"item_id": bi.item_id, "qty": posted_qty})

            dest_factory_id = (
                bi.destination_location_id
                if bi.destination_location_type == 'inventory' and bi.destination_location_id
                else factory_id
            )

            if bi.item_role in ('output', 'byproduct'):
                product_manager.apply_production_output(
                    session,
                    workspace_id=workspace_id,
                    user_id=user_id,
                    factory_id=dest_factory_id,
                    item_id=bi.item_id,
                    quantity=as_quantity(qty),
                    batch_id=batch_id,
                    unit_cost=output_unit_cost if bi.item_role == "output" else None,
                    notes=system_note,
                )

            elif bi.item_role == 'waste':
                inv_type = InventoryTypeEnum.DAMAGED
                damaged = inventory_dao.ensure_for_factory_item_type(
                    session,
                    factory_id=dest_factory_id,
                    item_id=bi.item_id,
                    inventory_type=inv_type,
                    workspace_id=workspace_id,
                    created_by=user_id,
                )

                old_qty = damaged.qty
                new_qty = old_qty + qty
                avg_price = damaged.avg_price if damaged.avg_price is not None else None
                damaged.qty = new_qty
                session.flush()

                inventory_ledger_dao.create(session, obj_in={
                    'workspace_id': workspace_id,
                    'inventory_type': inv_type,
                    'factory_id': dest_factory_id,
                    'item_id': bi.item_id,
                    'transaction_type': 'damaged',
                    'quantity': qty,
                    'unit_cost': avg_price,
                    'total_cost': (avg_price * qty) if avg_price else None,
                    'qty_before': old_qty,
                    'qty_after': new_qty,
                    'avg_price_before': avg_price,
                    'avg_price_after': avg_price,
                    'source_type': 'production_batch',
                    'source_id': batch_id,
                    'notes': system_note,
                    'performed_by': user_id,
                })

        flushed = self._flush_leftover_wip_to_storage(
            session,
            batch=updated_batch,
            workspace_id=workspace_id,
            user_id=user_id,
            factory_id=factory_id,
        )
        posting_summary = self._posting_summary(
            session,
            batch=updated_batch,
            workspace_id=workspace_id,
            products=posted_products,
            waste=posted_waste,
            flushed=flushed,
        )
        log_batch_event(
            session,
            workspace_id=workspace_id,
            batch_id=batch_id,
            event_type="batch_completed",
            description="Batch completed",
            performed_by=user_id,
            metadata={
                "actual_output_quantity": actual_out,
                "completed_at": _serialize_value(now),
                "wip_flushed": flushed,
                "posting_summary": posting_summary,
            },
        )
        return updated_batch

    def _all_stage_logs_closed(
        self, session: Session, batch_id: int, workspace_id: int
    ) -> bool:
        logs = self.stage_log_dao.get_by_batch(
            session, batch_id=batch_id, workspace_id=workspace_id
        )
        if not logs:
            return False
        return all(log.status in ("completed", "skipped") for log in logs)

    def _maybe_auto_complete_batch(
        self,
        session: Session,
        *,
        batch_id: int,
        workspace_id: int,
        user_id: int,
        completed_at: Optional[datetime] = None,
    ) -> Optional[ProductionBatch]:
        """When every step is completed or skipped, close the batch run."""
        batch = self.batch_dao.get_by_id_and_workspace(
            session, id=batch_id, workspace_id=workspace_id
        )
        if not batch or batch.status != "in_progress":
            return None
        if not self._all_stage_logs_closed(session, batch_id, workspace_id):
            return None
        return self.complete_batch(
            session,
            batch_id,
            workspace_id,
            user_id,
            completed_at=completed_at,
        )

    def cancel_batch(
        self,
        session: Session,
        batch_id: int,
        workspace_id: int,
        user_id: int,
        notes: Optional[str] = None
    ) -> ProductionBatch:
        """
        Cancel a production batch (draft or in_progress → cancelled).
        """
        batch = self.batch_dao.get_by_id_and_workspace(
            session, id=batch_id, workspace_id=workspace_id
        )
        if not batch:
            raise ValueError(f"Production batch {batch_id} not found")
        if batch.status not in (*self.PRE_START_STATUSES, 'in_progress'):
            raise ValueError(
                f"Can only cancel draft, planned, or in-progress batches. Current status: {batch.status}"
            )

        wip_voided = self._wip_void_snapshot(session, batch=batch, workspace_id=workspace_id)
        storage_reversed = self._reverse_step_start_storage(
            session, batch=batch, workspace_id=workspace_id, user_id=user_id
        )
        update_data = {
            'status': 'cancelled',
            'updated_by': user_id,
        }
        if notes is not None:
            update_data['notes'] = notes

        logs = self.stage_log_dao.get_by_batch(session, batch_id=batch_id, workspace_id=workspace_id)
        for log in logs:
            if log.status != "in_progress":
                continue
            released = self.stage_log_dao.update(session, db_obj=log, obj_in={"status": "skipped"})
            self._flip_machine_for_live_step(
                session, released, workspace_id, user_id, running=False
            )

        updated = self.batch_dao.update(session, db_obj=batch, obj_in=update_data)
        log_batch_event(
            session,
            workspace_id=workspace_id,
            batch_id=batch_id,
            event_type="batch_cancelled",
            description="Batch cancelled",
            performed_by=user_id,
            metadata={
                "notes": notes,
                "storage_reversed": storage_reversed,
                "wip_voided": wip_voided,
            },
        )
        return updated

    # ─── Batch Item CRUD ────────────────────────────────────────────

    def add_batch_item(
        self,
        session: Session,
        item_data: ProductionBatchItemCreate,
        workspace_id: int,
        user_id: int | None = None,
    ) -> ProductionBatchItem:
        """
        Add an item to a batch.

        Validates batch exists, is not completed/cancelled, and item exists.
        """
        # Validate batch
        batch = self.batch_dao.get_by_id_and_workspace(
            session, id=item_data.batch_id, workspace_id=workspace_id
        )
        if not batch:
            raise ValueError(f"Production batch {item_data.batch_id} not found")
        if batch.status in ('completed', 'cancelled'):
            raise ValueError(f"Cannot add items to a {batch.status} batch")

        # Validate item
        item = item_dao.get(session, id=item_data.item_id)
        if not item:
            raise ValueError(f"Item {item_data.item_id} not found")
        if item.workspace_id != workspace_id:
            raise ValueError(
                f"Item {item_data.item_id} does not belong to workspace {workspace_id}"
            )

        if item_data.item_role not in self.VALID_ITEM_ROLES:
            raise ValueError(
                f"Invalid item_role '{item_data.item_role}'. Must be one of: {', '.join(self.VALID_ITEM_ROLES)}"
            )

        item_dict = item_data.model_dump()
        item_dict['workspace_id'] = workspace_id

        created = self.batch_item_dao.create(session, obj_in=item_dict)
        if user_id is not None:
            from app.managers.item_manager import item_manager

            item_manager.ensure_production_role_catalog_tag(
                session,
                item_id=item_data.item_id,
                item_role=item_data.item_role,
                workspace_id=workspace_id,
                user_id=user_id,
            )
        return created

    def update_batch_item(
        self,
        session: Session,
        batch_item_id: int,
        item_data: ProductionBatchItemUpdate,
        workspace_id: int,
        user_id: int | None = None,
    ) -> ProductionBatchItem:
        """Update a batch item (e.g., log actual quantities)."""
        batch_item = self.batch_item_dao.get_by_id_and_workspace(
            session, id=batch_item_id, workspace_id=workspace_id
        )
        if not batch_item:
            raise ValueError(f"Batch item {batch_item_id} not found")

        # Check parent batch is not completed/cancelled
        batch = self.batch_dao.get_by_id_and_workspace(
            session, id=batch_item.batch_id, workspace_id=workspace_id
        )
        if batch and batch.status in ('completed', 'cancelled'):
            raise ValueError(f"Cannot update items in a {batch.status} batch")

        update_dict = item_data.model_dump(exclude_unset=True, exclude_none=True)
        context_log_id = update_dict.pop("context_batch_stage_log_id", None)
        stage_name: str | None = None
        if context_log_id is not None:
            stage_log = self.stage_log_dao.get_by_id_and_workspace(
                session, id=context_log_id, workspace_id=workspace_id
            )
            if stage_log is None or stage_log.batch_id != batch_item.batch_id:
                raise ValueError(
                    f"Step log {context_log_id} not found on this batch"
                )
            stage_name = stage_log.stage_name

        if 'item_role' in update_dict and update_dict['item_role'] not in self.VALID_ITEM_ROLES:
            raise ValueError(
                f"Invalid item_role '{update_dict['item_role']}'. Must be one of: {', '.join(self.VALID_ITEM_ROLES)}"
            )

        log_batch_item_quantity_events(
            session,
            batch_item=batch_item,
            update_dict=update_dict,
            user_id=user_id,
            batch_stage_log_id=context_log_id,
            stage_name=stage_name,
        )
        return self.batch_item_dao.update(session, db_obj=batch_item, obj_in=update_dict)

    def remove_batch_item(
        self,
        session: Session,
        batch_item_id: int,
        workspace_id: int
    ) -> ProductionBatchItem:
        """Remove an item from a batch (hard delete). Only for draft/in_progress batches."""
        batch_item = self.batch_item_dao.get_by_id_and_workspace(
            session, id=batch_item_id, workspace_id=workspace_id
        )
        if not batch_item:
            raise ValueError(f"Batch item {batch_item_id} not found")

        batch = self.batch_dao.get_by_id_and_workspace(
            session, id=batch_item.batch_id, workspace_id=workspace_id
        )
        if batch and batch.status in ('completed', 'cancelled'):
            raise ValueError(f"Cannot remove items from a {batch.status} batch")

        return self.batch_item_dao.remove(session, id=batch_item_id)

    def get_batch_items(
        self,
        session: Session,
        batch_id: int,
        workspace_id: int,
        item_role: Optional[str] = None
    ) -> List[ProductionBatchItem]:
        """Get items for a batch with optional role filter."""
        batch = self.batch_dao.get_by_id_and_workspace(
            session, id=batch_id, workspace_id=workspace_id
        )
        if not batch:
            raise ValueError(f"Production batch {batch_id} not found")

        if item_role:
            if item_role not in self.VALID_ITEM_ROLES:
                raise ValueError(
                    f"Invalid item_role '{item_role}'. Must be one of: {', '.join(self.VALID_ITEM_ROLES)}"
                )
            return self.batch_item_dao.get_by_batch_and_role(
                session, batch_id=batch_id, item_role=item_role, workspace_id=workspace_id
            )

        return self.batch_item_dao.get_by_batch(
            session, batch_id=batch_id, workspace_id=workspace_id
        )

    def get_batch_stage_parameters(
        self, session: Session, batch_id: int, workspace_id: int
    ) -> List[ProductionBatchStageParameter]:
        batch = self.batch_dao.get_by_id_and_workspace(
            session, id=batch_id, workspace_id=workspace_id
        )
        if not batch:
            raise ValueError(f"Production batch {batch_id} not found")
        return production_batch_stage_parameter_dao.get_by_batch(
            session, batch_id=batch_id, workspace_id=workspace_id
        )

    def get_batch_stage_log_parameters(
        self, session: Session, batch_id: int, log_id: int, workspace_id: int
    ) -> List[ProductionBatchStageParameter]:
        batch = self.batch_dao.get_by_id_and_workspace(
            session, id=batch_id, workspace_id=workspace_id
        )
        if not batch:
            raise ValueError(f"Production batch {batch_id} not found")
        log = self.stage_log_dao.get_by_id_and_workspace(
            session, id=log_id, workspace_id=workspace_id
        )
        if not log or log.batch_id != batch_id:
            raise ValueError(f"Stage log {log_id} not found for batch {batch_id}")
        return production_batch_stage_parameter_dao.get_by_stage_log(
            session, batch_stage_log_id=log_id, workspace_id=workspace_id
        )

    def update_batch_stage_parameter(
        self,
        session: Session,
        parameter_id: int,
        param_data: ProductionBatchStageParameterUpdate,
        workspace_id: int,
        user_id: int | None = None,
    ) -> ProductionBatchStageParameter:
        param = production_batch_stage_parameter_dao.get_by_id_and_workspace(
            session, id=parameter_id, workspace_id=workspace_id
        )
        if not param:
            raise ValueError(f"Batch stage parameter {parameter_id} not found")

        batch = self.batch_dao.get_by_id_and_workspace(
            session, id=param.batch_id, workspace_id=workspace_id
        )
        if batch and batch.status not in (*self.PRE_START_STATUSES, "in_progress"):
            raise ValueError(
                f"Cannot update conditions on a {batch.status} batch"
            )

        update_dict: dict = {}
        log_actual = False
        before_actual = param.actual_value

        if "actual_value" in param_data.model_fields_set:
            actual = param_data.actual_value
            if actual is not None:
                actual = actual.strip()
                if actual == "":
                    actual = None
            update_dict["actual_value"] = actual
            update_dict["actual_value_numeric"] = optional_numeric_from_text(actual)
            log_actual = before_actual != actual

        if param_data.planned_value is not None:
            planned = param_data.planned_value.strip()
            if not planned:
                raise ValueError("Planned value cannot be empty")
            update_dict["planned_value"] = planned
            update_dict["planned_value_numeric"] = optional_numeric_from_text(planned)

        if not update_dict:
            return param

        stage_name: str | None = None
        if param.batch_stage_log_id is not None:
            stage_log = self.stage_log_dao.get_by_id_and_workspace(
                session, id=param.batch_stage_log_id, workspace_id=workspace_id
            )
            if stage_log:
                stage_name = stage_log.stage_name

        updated = production_batch_stage_parameter_dao.update(
            session, db_obj=param, obj_in=update_dict
        )
        if log_actual:
            log_condition_actual_event(
                session,
                param=updated,
                before=before_actual,
                after=updated.actual_value,
                user_id=user_id,
                stage_name=stage_name,
            )
        return updated

    def set_batch_stage_parameter_by_source(
        self,
        session: Session,
        *,
        batch_id: int,
        log_id: int,
        source_parameter_id: int,
        param_data: ProductionBatchStageParameterUpdate,
        workspace_id: int,
        user_id: int | None = None,
    ) -> ProductionBatchStageParameter:
        log = self.stage_log_dao.get_by_id_and_workspace(
            session, id=log_id, workspace_id=workspace_id
        )
        if not log or log.batch_id != batch_id:
            raise ValueError(f"Stage log {log_id} not found for batch {batch_id}")

        param = production_batch_stage_parameter_dao.get_by_stage_log_and_source(
            session,
            batch_stage_log_id=log_id,
            source_parameter_id=source_parameter_id,
            workspace_id=workspace_id,
        )
        if not param:
            if log.formula_stage_id is None:
                raise ValueError("Step has no formula stage; cannot create condition row")
            formula_param = production_formula_stage_parameter_dao.get_by_id_and_workspace(
                session, id=source_parameter_id, workspace_id=workspace_id
            )
            if not formula_param or formula_param.formula_stage_id != log.formula_stage_id:
                raise ValueError(f"Formula condition {source_parameter_id} not found for this step")
            batch = self.batch_dao.get_by_id_and_workspace(
                session, id=batch_id, workspace_id=workspace_id
            )
            if not batch:
                raise ValueError(f"Batch {batch_id} not found")
            production_batch_stage_parameter_dao.create(
                session,
                obj_in={
                    "workspace_id": workspace_id,
                    "batch_id": batch.id,
                    "batch_stage_log_id": log.id,
                    "label": formula_param.label,
                    "planned_value": formula_param.planned_value,
                    "planned_value_numeric": formula_param.planned_value_numeric,
                    "actual_value": None,
                    "actual_value_numeric": None,
                    "unit": formula_param.unit,
                    "source_parameter_id": formula_param.id,
                },
            )
            param = production_batch_stage_parameter_dao.get_by_stage_log_and_source(
                session,
                batch_stage_log_id=log_id,
                source_parameter_id=source_parameter_id,
                workspace_id=workspace_id,
            )
            if not param:
                raise ValueError("Failed to create batch condition row")

        return self.update_batch_stage_parameter(
            session, param.id, param_data, workspace_id, user_id=user_id
        )

    def list_batch_events(
        self,
        session: Session,
        batch_id: int,
        workspace_id: int,
        skip: int = 0,
        limit: int = 100,
    ) -> List[tuple[ProductionBatchEvent, object | None]]:
        batch = self.batch_dao.get_by_id_and_workspace(
            session, id=batch_id, workspace_id=workspace_id
        )
        if not batch:
            raise ValueError(f"Production batch {batch_id} not found")
        events = self.batch_event_dao.get_by_batch(
            session,
            batch_id=batch_id,
            workspace_id=workspace_id,
            skip=skip,
            limit=limit,
        )
        return [
            (
                event,
                profile_dao.get(session, id=event.performed_by)
                if event.performed_by
                else None,
            )
            for event in events
        ]

    # ─── Helpers ────────────────────────────────────────────────────

    def _calculate_batch_item_variances(
        self,
        session: Session,
        batch_id: int,
        workspace_id: int
    ) -> None:
        """Calculate variance for all batch items that have both expected and actual quantities."""
        batch_items = self.batch_item_dao.get_by_batch(
            session, batch_id=batch_id, workspace_id=workspace_id
        )
        for bi in batch_items:
            if bi.expected_quantity is not None and bi.actual_quantity is not None and bi.expected_quantity > 0:
                variance = bi.actual_quantity - bi.expected_quantity
                variance_pct = Decimal(str(round((variance / bi.expected_quantity) * 100, 2)))
                self.batch_item_dao.update(
                    session, db_obj=bi,
                    obj_in={'variance_quantity': variance, 'variance_percentage': variance_pct}
                )

    def _raw_output_unit_cost(
        self,
        session: Session,
        *,
        workspace_id: int,
        batch_id: int,
        output_quantity: Decimal,
    ) -> Optional[Decimal]:
        """Per-unit raw cost from storage consumption already posted for this batch."""
        raw = inventory_ledger_dao.sum_total_cost_for_source(
            session,
            workspace_id=workspace_id,
            source_type="production_batch",
            source_id=batch_id,
            transaction_type="consumption",
        )
        return unit_cost_from_raw(raw, output_quantity)

    def post_outputs_to_finished_goods(
        self,
        session: Session,
        batch_id: int,
        workspace_id: int,
        user_id: int,
        *,
        include_byproducts: bool = True,
    ) -> int:
        """
        Post output and optional byproduct quantities to finished goods (products) for the batch's factory.

        Idempotent: raises if any product ledger row already exists for this batch.

        Returns:
            Number of distinct items posted (ledger lines created).
        """
        if product_ledger_dao.exists_for_production_batch(
            session, workspace_id=workspace_id, batch_id=batch_id
        ):
            raise ValueError(
                "Finished goods for this batch have already been posted. "
                "Each batch can only be received into products once."
            )

        batch = self.batch_dao.get_by_id_and_workspace(
            session, id=batch_id, workspace_id=workspace_id
        )
        if not batch:
            raise ValueError(f"Production batch {batch_id} not found")
        if batch.status != "completed":
            raise ValueError("Only completed batches can post outputs to finished goods")

        line = production_line_dao.get_by_id_and_workspace(
            session, id=batch.production_line_id, workspace_id=workspace_id
        )
        if not line:
            raise ValueError("Production line not found for this batch")
        factory_id = line.factory_id

        roles = {"output"}
        if include_byproducts:
            roles.add("byproduct")

        merged_qty: defaultdict[int, Decimal] = defaultdict(lambda: Decimal("0"))
        output_item_ids: set[int] = set()
        output_qty_total = Decimal("0")
        batch_items = self.batch_item_dao.get_by_batch(
            session, batch_id=batch_id, workspace_id=workspace_id
        )
        for bi in batch_items:
            if bi.item_role not in roles:
                continue
            qty = bi.actual_quantity if bi.actual_quantity is not None else bi.expected_quantity
            if qty is None or qty <= 0:
                continue
            posted_qty = as_quantity(qty)
            merged_qty[bi.item_id] += posted_qty
            if bi.item_role == "output":
                output_item_ids.add(bi.item_id)
                output_qty_total += posted_qty

        if not merged_qty:
            raise ValueError(
                "No quantities to post. Enter actual amounts on output/byproduct lines, "
                "or set actual output quantity on the batch when the formula has a single output item."
            )

        output_unit_cost = self._raw_output_unit_cost(
            session, workspace_id=workspace_id, batch_id=batch_id, output_quantity=output_qty_total
        )

        for item_id, qty in merged_qty.items():
            product_manager.apply_production_output(
                session,
                workspace_id=workspace_id,
                user_id=user_id,
                factory_id=factory_id,
                item_id=item_id,
                quantity=qty,
                batch_id=batch_id,
                unit_cost=output_unit_cost if item_id in output_item_ids else None,
            )

        posted_count = len(merged_qty)
        log_batch_event(
            session,
            workspace_id=workspace_id,
            batch_id=batch_id,
            event_type="finished_goods_posted",
            description="Finished goods posted",
            performed_by=user_id,
            metadata={"item_count": posted_count, "include_byproducts": include_byproducts},
        )
        return posted_count

    # ─── Batch Stage Logs ───────────────────────────────────────────

    def _seed_stage_logs_from_formula(
        self,
        session: Session,
        *,
        batch: ProductionBatch,
        formula_id: int,
        workspace_id: int,
        stage_seeds=None,
        parameter_seeds=None,
        target_output: Optional[Decimal] = None,
    ) -> None:
        seed_by_stage = {row.formula_stage_id: row for row in (stage_seeds or [])}
        seed_by_parameter_id = {
            row.source_parameter_id: row for row in (parameter_seeds or [])
        }
        stages = self.formula_stage_dao.get_by_formula(
            session, formula_id=formula_id, workspace_id=workspace_id
        )
        formula_stage_items = production_formula_stage_item_dao.get_by_formula(
            session, formula_id=formula_id, workspace_id=workspace_id
        )
        output_total = finished_good_output_quantity(stages, formula_stage_items)
        item_multiplier = Decimal("1")
        if target_output is not None and output_total > 0:
            item_multiplier = Decimal(str(target_output)) / Decimal(str(output_total))
        items_by_stage: dict = defaultdict(list)
        for row in formula_stage_items:
            items_by_stage[row.formula_stage_id].append(row)
        for stage in stages:
            seed = seed_by_stage.get(stage.id)
            if seed is not None and not seed.include:
                continue
            if seed is None and getattr(stage, "is_used", True) is False:
                continue
            route_step = None
            if stage.route_step_id is not None:
                route_step = production_route_step_dao.get_by_id_and_workspace(
                    session, id=stage.route_step_id, workspace_id=workspace_id
                )
            line_id = None
            machine_id = None
            if seed is not None and seed.production_line_id is not None:
                line_id = seed.production_line_id
            elif route_step is not None:
                line_id = route_step.production_line_id
            if line_id is None:
                line_id = stage.production_line_id or batch.production_line_id
            if seed is not None and seed.machine_id is not None:
                machine_id = seed.machine_id
            elif stage.machine_id is not None:
                machine_id = stage.machine_id
            if machine_id is not None and line_id is not None:
                self._validate_machine_on_line(
                    session,
                    machine_id=machine_id,
                    production_line_id=line_id,
                    workspace_id=workspace_id,
                )
            if machine_id is None and line_id is not None:
                machine_ids = production_line_machine_dao.get_machine_ids_for_line(
                    session, production_line_id=line_id, workspace_id=workspace_id
                )
                if len(machine_ids) == 1:
                    machine_id = machine_ids[0]
                elif len(machine_ids) == 0:
                    line = production_line_dao.get_by_id_and_workspace(
                        session, id=line_id, workspace_id=workspace_id
                    )
                    if line:
                        machine_id = line.machine_id
            expected_minutes = stage.expected_duration_minutes
            expected_output = stage.expected_output_quantity
            if seed is not None:
                if seed.expected_duration_minutes is not None:
                    expected_minutes = seed.expected_duration_minutes
                if seed.expected_output_quantity is not None:
                    expected_output = seed.expected_output_quantity
            log_dict = {
                "workspace_id": workspace_id,
                "batch_id": batch.id,
                "formula_stage_id": stage.id,
                "route_step_id": route_step.id if route_step is not None else None,
                "stage_name": stage.name,
                "stage_order": stage.stage_order,
                "production_line_id": line_id,
                "machine_id": machine_id,
                "expected_duration_minutes": expected_minutes,
                "expected_output_quantity": expected_output,
                "status": "pending",
            }
            log = self.stage_log_dao.create(session, obj_in=log_dict)
            self._seed_stage_parameters_for_log(
                session,
                batch=batch,
                log=log,
                formula_stage_id=stage.id,
                workspace_id=workspace_id,
                parameter_seeds_by_id=seed_by_parameter_id,
            )
            for row in items_by_stage.get(stage.id, []):
                production_batch_stage_item_dao.create(
                    session,
                    obj_in={
                        "workspace_id": workspace_id,
                        "batch_id": batch.id,
                        "batch_stage_log_id": log.id,
                        "item_id": row.item_id,
                        "item_role": row.item_role,
                        "expected_quantity": scale_quantity(row.quantity, item_multiplier),
                        "actual_quantity": None,
                    },
                )

    def _sync_sequential_planned_starts_for_batch(
        self, session: Session, batch: ProductionBatch, workspace_id: int
    ) -> None:
        if batch.planned_start_at is None:
            return
        logs = self.stage_log_dao.get_by_batch(
            session, batch_id=batch.id, workspace_id=workspace_id
        )
        if not logs:
            return
        assign_sequential_planned_starts(batch.planned_start_at, logs)
        for log in logs:
            self.stage_log_dao.update(
                session, db_obj=log, obj_in={"planned_start_at": log.planned_start_at}
            )

    def _seed_stage_parameters_for_log(
        self,
        session: Session,
        *,
        batch: ProductionBatch,
        log: ProductionBatchStageLog,
        formula_stage_id: int,
        workspace_id: int,
        parameter_seeds_by_id=None,
    ) -> None:
        overrides = parameter_seeds_by_id or {}
        params = production_formula_stage_parameter_dao.get_by_stage(
            session, formula_stage_id=formula_stage_id, workspace_id=workspace_id
        )
        for param in params:
            override = overrides.get(param.id)
            planned_value = (
                override.planned_value.strip()
                if override is not None
                else param.planned_value
            )
            planned_numeric = optional_numeric_from_text(planned_value)
            if planned_numeric is None and override is None:
                planned_numeric = param.planned_value_numeric
            production_batch_stage_parameter_dao.create(
                session,
                obj_in={
                    "workspace_id": workspace_id,
                    "batch_id": batch.id,
                    "batch_stage_log_id": log.id,
                    "label": param.label,
                    "planned_value": planned_value,
                    "planned_value_numeric": planned_numeric,
                    "actual_value": None,
                    "actual_value_numeric": None,
                    "unit": param.unit,
                    "source_parameter_id": param.id,
                },
            )

    def _seed_batch_items_from_formula(
        self,
        session: Session,
        *,
        batch: ProductionBatch,
        formula_id: int,
        workspace_id: int,
        item_seeds=None,
        target_output: Optional[int] = None,
    ) -> None:
        if item_seeds is not None:
            for row in item_seeds:
                self.batch_item_dao.create(
                    session,
                    obj_in={
                        "workspace_id": workspace_id,
                        "batch_id": batch.id,
                        "item_id": row.item_id,
                        "item_role": row.item_role,
                        "expected_quantity": row.expected_quantity,
                    },
                )
            return

        stage_items = production_formula_stage_item_dao.get_by_formula(
            session, formula_id=formula_id, workspace_id=workspace_id
        )
        if not stage_items:
            return

        stages = self.formula_stage_dao.get_by_formula(
            session, formula_id=formula_id, workspace_id=workspace_id
        )
        output_total = finished_good_output_quantity(stages, stage_items)
        multiplier = Decimal("1")
        if target_output is not None and output_total > 0:
            multiplier = Decimal(str(target_output)) / Decimal(str(output_total))

        for row in stage_items:
            qty = scale_quantity(row.quantity, multiplier)
            self.batch_item_dao.create(
                session,
                obj_in={
                    "workspace_id": workspace_id,
                    "batch_id": batch.id,
                    "item_id": row.item_id,
                    "item_role": row.item_role,
                    "expected_quantity": qty,
                },
            )

    def get_batch_stage_logs(
        self, session: Session, batch_id: int, workspace_id: int
    ) -> List[ProductionBatchStageLog]:
        batch = self.batch_dao.get_by_id_and_workspace(
            session, id=batch_id, workspace_id=workspace_id
        )
        if not batch:
            raise ValueError(f"Production batch {batch_id} not found")
        logs = self.stage_log_dao.get_by_batch(
            session, batch_id=batch_id, workspace_id=workspace_id
        )
        return [attach_stage_metrics(log) for log in logs]

    def add_batch_stage_log(
        self,
        session: Session,
        log_data: ProductionBatchStageLogCreate,
        workspace_id: int,
        user_id: int,
    ) -> ProductionBatchStageLog:
        batch = self.batch_dao.get_by_id_and_workspace(
            session, id=log_data.batch_id, workspace_id=workspace_id
        )
        if not batch:
            raise ValueError(f"Production batch {log_data.batch_id} not found")

        if log_data.status not in self.VALID_STAGE_LOG_STATUSES:
            raise ValueError(f"Invalid stage log status '{log_data.status}'")

        if log_data.production_line_id is not None:
            line = production_line_dao.get_by_id_and_workspace(
                session, id=log_data.production_line_id, workspace_id=workspace_id
            )
            if not line:
                raise ValueError(f"Production line {log_data.production_line_id} not found")

        self._validate_stage_log_completion(log_data.status, log_data.output_quantity)

        log_dict = log_data.model_dump()
        log_dict["workspace_id"] = workspace_id
        log_dict["logged_by"] = user_id
        return self.stage_log_dao.create(session, obj_in=log_dict)

    def update_batch_stage_log(
        self,
        session: Session,
        log_id: int,
        log_data: ProductionBatchStageLogUpdate,
        workspace_id: int,
        user_id: int,
    ) -> ProductionBatchStageLog:
        log = self.stage_log_dao.get_by_id_and_workspace(
            session, id=log_id, workspace_id=workspace_id
        )
        if not log:
            raise ValueError(f"Batch stage log {log_id} not found")

        update_dict = log_data.model_dump(exclude_unset=True, exclude_none=True)
        if not update_dict:
            return log

        new_status = update_dict.get("status", log.status)
        if new_status not in self.VALID_STAGE_LOG_STATUSES:
            raise ValueError(f"Invalid stage log status '{new_status}'")

        if new_status == "completed" and log.status != "in_progress":
            raise ValueError("Start the step before finishing it")

        if "production_line_id" in update_dict and update_dict["production_line_id"] is not None:
            new_line_id = update_dict["production_line_id"]
            line = production_line_dao.get_by_id_and_workspace(
                session, id=new_line_id, workspace_id=workspace_id
            )
            if not line:
                raise ValueError(f"Production line {new_line_id} not found")
            assert_production_line_assignable(
                session,
                line_id=new_line_id,
                workspace_id=workspace_id,
                previous_line_id=log.production_line_id,
            )

        output_qty = update_dict.get("output_quantity", log.output_quantity)
        self._validate_stage_log_completion(new_status, output_qty)

        started = update_dict.get("started_at", log.started_at)
        completed = update_dict.get("completed_at", log.completed_at)
        if started and completed and completed < started:
            raise ValueError("completed_at cannot be before started_at")

        if "machine_id" in update_dict and update_dict["machine_id"] is not None:
            batch = self.batch_dao.get_by_id_and_workspace(
                session, id=log.batch_id, workspace_id=workspace_id
            )
            if not batch:
                raise ValueError(f"Production batch {log.batch_id} not found")
            self._enforce_machine_pick_policy(
                session,
                workspace_id=workspace_id,
                machine_id=int(update_dict["machine_id"]),
                batch=batch,
                stage_log=log,
            )

        update_dict["logged_by"] = user_id
        old_status = log.status
        log_stage_log_update_events(
            session,
            log=log,
            update_dict=update_dict,
            user_id=user_id,
            old_status=old_status,
        )
        updated = self.stage_log_dao.update(session, db_obj=log, obj_in=update_dict)
        if new_status in ("completed", "skipped"):
            step_completed_at = update_dict.get("completed_at", updated.completed_at)
            self._maybe_auto_complete_batch(
                session,
                batch_id=log.batch_id,
                workspace_id=workspace_id,
                user_id=user_id,
                completed_at=step_completed_at if isinstance(step_completed_at, datetime) else None,
            )
        return attach_stage_metrics(updated)

    def _validate_stage_log_completion(self, status: str, output_quantity: Optional[int]) -> None:
        if status == "completed" and output_quantity is None:
            raise ValueError("Completed stage logs require output_quantity")
        if status == "skipped":
            return

    def start_stage_log(
        self,
        session: Session,
        log_id: int,
        workspace_id: int,
        user_id: int,
        started_at: Optional[datetime] = None,
        machine_id: Optional[int] = None,
    ) -> ProductionBatchStageLog:
        log = self._require_stage_log(session, log_id, workspace_id)
        self._ensure_batch_running_for_step(
            session,
            log.batch_id,
            workspace_id,
            user_id,
            started_at=started_at,
        )
        if log.status != "pending":
            raise ValueError(f"Only pending steps can be started. Current status: {log.status}")
        self._require_earlier_steps_closed(session, log, workspace_id)
        line_id = log.production_line_id
        station_machine_ids: List[int] = []
        if line_id is not None:
            station_machine_ids = production_line_machine_dao.get_machine_ids_for_line(
                session, production_line_id=line_id, workspace_id=workspace_id
            )
            if not station_machine_ids:
                line = production_line_dao.get_by_id_and_workspace(
                    session, id=line_id, workspace_id=workspace_id
                )
                if line and line.machine_id:
                    station_machine_ids = [line.machine_id]

        if machine_id is not None:
            self._require_machine(session, machine_id, workspace_id)
            if line_id is not None and station_machine_ids and machine_id not in station_machine_ids:
                raise ValueError("Selected machine is not assigned to this station")
            log.machine_id = machine_id
        elif len(station_machine_ids) > 1 and log.machine_id is None:
            raise ValueError("Select a machine for this station before starting the step")
        elif len(station_machine_ids) == 1 and log.machine_id is None:
            log.machine_id = station_machine_ids[0]
        batch = self.batch_dao.get_by_id_and_workspace(
            session, id=log.batch_id, workspace_id=workspace_id
        )
        if not batch:
            raise ValueError(f"Production batch {log.batch_id} not found")
        if log.machine_id is not None:
            self._enforce_machine_pick_policy(
                session,
                workspace_id=workspace_id,
                machine_id=log.machine_id,
                batch=batch,
                stage_log=log,
            )
        self._validate_and_deduct_step_inputs(
            session,
            batch=batch,
            log=log,
            workspace_id=workspace_id,
            user_id=user_id,
        )
        reject_future_started_at(started_at)
        when = started_at or utcnow()
        start_update: dict = {"status": "in_progress", "started_at": when, "logged_by": user_id}
        if log.machine_id is not None:
            start_update["machine_id"] = log.machine_id
        updated = self.stage_log_dao.update(
            session,
            db_obj=log,
            obj_in=start_update,
        )
        # Floor event is button time, even when the batch logs an earlier started_at.
        self._flip_machine_for_live_step(session, updated, workspace_id, user_id, running=True)
        step_start_desc = f"{log.stage_name} started"
        if started_at is not None:
            step_start_desc = f"{log.stage_name} started (started earlier)"
        start_snapshot = build_step_event_snapshot(
            session, log=updated, workspace_id=workspace_id
        )
        log_batch_event(
            session,
            workspace_id=workspace_id,
            batch_id=log.batch_id,
            batch_stage_log_id=updated.id,
            event_type="step_started",
            description=step_start_desc,
            performed_by=user_id,
            metadata={
                "stage_name": log.stage_name,
                "machine_id": updated.machine_id,
                "started_at": _serialize_value(when),
                "started_earlier": started_at is not None,
                "step_snapshot": start_snapshot,
            },
        )
        return attach_stage_metrics(updated)

    def finish_stage_log(
        self,
        session: Session,
        log_id: int,
        workspace_id: int,
        user_id: int,
        *,
        output_quantity: int,
        completed_at: Optional[datetime] = None,
        input_quantity: Optional[int] = None,
        waste_quantity: Optional[int] = None,
        rework_quantity: Optional[int] = None,
        rework_to_log_id: Optional[int] = None,
        notes: Optional[str] = None,
    ) -> ProductionBatchStageLog:
        log = self._require_stage_log(session, log_id, workspace_id)
        self._require_batch_in_progress(session, log.batch_id, workspace_id)
        if log.status != "in_progress":
            raise ValueError("Start the step before finishing it")
        when = completed_at or utcnow()
        if log.started_at and when < log.started_at:
            raise ValueError("completed_at cannot be before started_at")
        update = {
            "status": "completed",
            "completed_at": when,
            "output_quantity": output_quantity,
            "logged_by": user_id,
        }
        if input_quantity is not None:
            update["input_quantity"] = input_quantity
        if waste_quantity is not None:
            update["waste_quantity"] = waste_quantity
        if notes is not None:
            update["notes"] = notes
        if rework_quantity:
            if not rework_to_log_id:
                raise ValueError("rework_to_log_id is required when rework_quantity is set")
            self._create_rework_log(session, log, workspace_id, rework_quantity, rework_to_log_id)
            update["rework_quantity"] = rework_quantity
        updated = self.stage_log_dao.update(session, db_obj=log, obj_in=update)
        # Idle at button time, even when the batch logs an earlier completed_at.
        self._flip_machine_for_live_step(session, updated, workspace_id, user_id, running=False)
        finish_snapshot = build_step_event_snapshot(
            session, log=updated, workspace_id=workspace_id
        )
        log_batch_event(
            session,
            workspace_id=workspace_id,
            batch_id=log.batch_id,
            batch_stage_log_id=updated.id,
            event_type="step_finished",
            description=f"{log.stage_name} finished",
            performed_by=user_id,
            metadata={
                "stage_name": log.stage_name,
                "output_quantity": output_quantity,
                "output_item_id": finish_snapshot.get("output_item_id"),
                "rework_quantity": rework_quantity or None,
                "rework_to_log_id": rework_to_log_id,
                "completed_at": _serialize_value(when),
                "step_snapshot": finish_snapshot,
            },
        )
        self._maybe_auto_complete_batch(
            session,
            batch_id=log.batch_id,
            workspace_id=workspace_id,
            user_id=user_id,
            completed_at=when,
        )
        return attach_stage_metrics(updated)

    def log_stage_as_planned(
        self,
        session: Session,
        log_id: int,
        workspace_id: int,
        user_id: int,
        *,
        output_quantity: int,
        input_quantity: Optional[int] = None,
        waste_quantity: Optional[int] = None,
        notes: Optional[str] = None,
    ) -> ProductionBatchStageLog:
        log = self._require_stage_log(session, log_id, workspace_id)
        self._require_batch_in_progress(session, log.batch_id, workspace_id)
        if log.status not in ("pending", "in_progress"):
            raise ValueError(f"Cannot log a {log.status} step as planned")
        if not log.expected_duration_minutes:
            raise ValueError("Set expected minutes on this step before logging as planned")
        batch = self.batch_dao.get_by_id_and_workspace(session, id=log.batch_id, workspace_id=workspace_id)
        started = self._planned_step_start(session, log, batch, workspace_id)
        if started is None:
            raise ValueError("Set a planned start on the batch, or finish the previous step, before logging as planned")
        from datetime import timedelta

        completed = started + timedelta(minutes=log.expected_duration_minutes)
        update = {
            "status": "completed",
            "started_at": started,
            "completed_at": completed,
            "output_quantity": output_quantity,
            "logged_by": user_id,
        }
        if input_quantity is not None:
            update["input_quantity"] = input_quantity
        if waste_quantity is not None:
            update["waste_quantity"] = waste_quantity
        if notes is not None:
            update["notes"] = notes
        updated = self.stage_log_dao.update(session, db_obj=log, obj_in=update)
        self._maybe_auto_complete_batch(
            session,
            batch_id=log.batch_id,
            workspace_id=workspace_id,
            user_id=user_id,
            completed_at=completed,
        )
        return attach_stage_metrics(updated)

    @staticmethod
    def _schedule_planned_anchor(batch, logs: list) -> datetime:
        """Anchor for step windows when batch has no planned_start_at (live floor runs)."""
        if batch.planned_start_at is not None:
            return batch.planned_start_at
        started = [
            log.started_at
            for log in logs
            if getattr(log, "status", None) == "in_progress" and getattr(log, "started_at", None)
        ]
        if started:
            return min(started)
        for attr in ("started_at", "actual_start_time"):
            val = getattr(batch, attr, None)
            if val is not None:
                return val
        when = utcnow()
        return when.replace(tzinfo=None) if when.tzinfo else when

    def move_stage_log_on_schedule(
        self,
        session: Session,
        log_id: int,
        workspace_id: int,
        user_id: int,
        *,
        production_line_id: int,
        planned_start_at: datetime,
        machine_id: int | None = None,
    ) -> dict:
        log = self._require_stage_log(session, log_id, workspace_id)
        if log.status != "pending":
            raise ValueError("Only pending steps can be moved on the schedule")
        batch = self.batch_dao.get_by_id_and_workspace(
            session, id=log.batch_id, workspace_id=workspace_id
        )
        if not batch:
            raise ValueError(f"Production batch {log.batch_id} not found")
        if batch.status not in (*self.PRE_START_STATUSES, "in_progress"):
            raise ValueError("Cannot reschedule steps on a completed or cancelled batch")

        line = production_line_dao.get_by_id_and_workspace(
            session, id=production_line_id, workspace_id=workspace_id
        )
        if not line:
            raise ValueError(f"Production line {production_line_id} not found")

        allowed_machines = self._machine_ids_for_line(
            session, production_line_id=production_line_id, workspace_id=workspace_id
        )
        resolved_machine = machine_id
        if resolved_machine is None:
            if len(allowed_machines) == 1:
                resolved_machine = allowed_machines[0]
            elif log.machine_id in allowed_machines:
                resolved_machine = log.machine_id
            else:
                raise ValueError("Pick a machine on the target line")
        elif resolved_machine not in allowed_machines:
            raise ValueError(f"Machine {resolved_machine} is not assigned to production line {production_line_id}")

        if resolved_machine is not None:
            self._validate_machine_on_line(
                session,
                machine_id=resolved_machine,
                production_line_id=production_line_id,
                workspace_id=workspace_id,
            )

        logs = self.stage_log_dao.get_by_batch(
            session, batch_id=log.batch_id, workspace_id=workspace_id
        )
        start_updates = compute_move_planned_start_updates(logs, log_id, planned_start_at)

        self.stage_log_dao.update(
            session,
            db_obj=log,
            obj_in={
                "production_line_id": production_line_id,
                "machine_id": resolved_machine,
                "planned_start_at": start_updates[log_id],
            },
        )

        for row in logs:
            if row.id == log_id:
                continue
            new_start = start_updates.get(row.id)
            if new_start is None:
                continue
            self.stage_log_dao.update(
                session, db_obj=row, obj_in={"planned_start_at": new_start}
            )

        logs = self.stage_log_dao.get_by_batch(
            session, batch_id=log.batch_id, workspace_id=workspace_id
        )
        ordered = sorted(logs, key=lambda row: (row.stage_order, row.id))
        first_start = ordered[0].planned_start_at if ordered else None
        if first_start is not None:
            self.batch_dao.update(
                session,
                db_obj=batch,
                obj_in={"planned_start_at": first_start, "updated_by": user_id},
            )

        anchor = first_start or batch.planned_start_at
        steps = step_planned_windows(anchor, logs)
        return {
            "batch_id": batch.id,
            "planned_start_at": first_start or anchor,
            "steps": steps,
        }

    def get_schedule(
        self,
        session: Session,
        workspace_id: int,
        factory_id: int | None,
        start: datetime,
        end: datetime,
    ) -> list:
        range_start = as_utc(start)
        range_end = as_utc(end)
        range_end_naive = range_end.replace(tzinfo=None)
        pre_start_in_range = and_(
            ProductionBatch.status.in_(("draft", "recurring")),
            ProductionBatch.planned_start_at.isnot(None),
            ProductionBatch.planned_start_at <= range_end_naive,
        )
        rows = (
            session.query(ProductionBatch)
            .join(production_line_dao.model, ProductionBatch.production_line_id == production_line_dao.model.id)
            .filter(
                ProductionBatch.workspace_id == workspace_id,
                or_(pre_start_in_range, ProductionBatch.status == "in_progress"),
            )
        )
        if factory_id is not None:
            rows = rows.filter(production_line_dao.model.factory_id == factory_id)
        rows = rows.all()
        result = []
        for batch in rows:
            logs = self.stage_log_dao.get_by_batch(session, batch_id=batch.id, workspace_id=workspace_id)
            anchor = self._schedule_planned_anchor(batch, logs)
            steps = step_planned_windows(anchor, logs)
            window_end = steps[-1]["planned_end_at"] if steps else planned_end_at(
                anchor, sum(log.expected_duration_minutes or 0 for log in logs)
            )
            batch_start = (
                steps[0]["planned_start_at"]
                if steps
                else (batch.planned_start_at if batch.planned_start_at is not None else anchor)
            )
            if batch.status != "in_progress" and window_end and as_utc(window_end) < range_start:
                continue
            result.append(
                {
                    "batch_id": batch.id,
                    "batch_number": batch.batch_number,
                    "status": batch.status,
                    "machine_id": batch.machine_id,
                    "planned_start_at": batch_start,
                    "planned_end_at": window_end,
                    "steps": steps,
                }
            )
        return result

    def linked_orders(self, session: Session, batch_id: int, workspace_id: int) -> dict:
        from app.models.expense_order import ExpenseOrder
        from app.models.purchase_order import PurchaseOrder

        batch = self.batch_dao.get_by_id_and_workspace(session, id=batch_id, workspace_id=workspace_id)
        if not batch:
            raise ValueError(f"Production batch {batch_id} not found")
        expenses = (
            session.query(ExpenseOrder)
            .filter(ExpenseOrder.workspace_id == workspace_id, ExpenseOrder.production_batch_id == batch_id)
            .all()
        )
        purchases = (
            session.query(PurchaseOrder)
            .filter(PurchaseOrder.workspace_id == workspace_id, PurchaseOrder.production_batch_id == batch_id)
            .all()
        )
        orders = []
        total = Decimal("0")
        for row in expenses:
            orders.append(self._linked_order_row("expense", row, row.expense_number, row.expense_date))
            if not row.voided:
                total += row.total_amount or 0
        for row in purchases:
            orders.append(self._linked_order_row("purchase", row, row.po_number, row.order_date))
            if not row.voided:
                total += row.total_amount or 0
        return {"orders": orders, "linked_spend_total": total}

    def _totals_for_batch(self, session: Session, batch: ProductionBatch) -> dict:
        from app.utils.batch_derived_totals import derive_batch_totals

        logs = self.stage_log_dao.get_by_batch(
            session, batch_id=batch.id, workspace_id=batch.workspace_id
        )
        items = self.batch_item_dao.get_by_batch(
            session, batch_id=batch.id, workspace_id=batch.workspace_id
        )
        formula_items = []
        if batch.formula_id is not None:
            formula_items = production_formula_stage_item_dao.get_by_formula(
                session, formula_id=batch.formula_id, workspace_id=batch.workspace_id
            )
        return derive_batch_totals(
            logs=logs, batch_items=items, formula_stage_items=formula_items
        )

    def annotate_batch_totals(self, session: Session, batches: list) -> list:
        from app.utils.batch_derived_totals import apply_batch_totals, derive_batch_totals

        if not batches:
            return batches
        workspace_id = batches[0].workspace_id
        batch_ids = [batch.id for batch in batches]
        logs_by_batch: dict[int, list] = defaultdict(list)
        for log in self.stage_log_dao.get_by_batch_ids(
            session, batch_ids=batch_ids, workspace_id=workspace_id
        ):
            logs_by_batch[log.batch_id].append(log)
        items_by_batch: dict[int, list] = defaultdict(list)
        for item in self.batch_item_dao.get_by_batch_ids(
            session, batch_ids=batch_ids, workspace_id=workspace_id
        ):
            items_by_batch[item.batch_id].append(item)

        formula_items_by_formula: dict[int, list] = {}
        for batch in batches:
            if batch.formula_id is None or batch.formula_id in formula_items_by_formula:
                continue
            formula_items_by_formula[batch.formula_id] = (
                production_formula_stage_item_dao.get_by_formula(
                    session, formula_id=batch.formula_id, workspace_id=workspace_id
                )
            )
        for batch in batches:
            apply_batch_totals(
                batch,
                derive_batch_totals(
                    logs=logs_by_batch.get(batch.id, []),
                    batch_items=items_by_batch.get(batch.id, []),
                    formula_stage_items=formula_items_by_formula.get(batch.formula_id, []),
                ),
            )
        return batches

    def attach_batch_read_model(self, session: Session, batch: ProductionBatch) -> ProductionBatch:
        self.annotate_batch_totals(session, [batch])
        logs = self.stage_log_dao.get_by_batch(session, batch_id=batch.id, workspace_id=batch.workspace_id)
        minutes = sum(log.expected_duration_minutes or 0 for log in logs)
        setattr(batch, "planned_end_at", planned_end_at(batch.planned_start_at, minutes))
        spend = self.linked_orders(session, batch.id, batch.workspace_id)["linked_spend_total"]
        setattr(batch, "linked_spend_total", spend)
        setattr(batch, "sales_order_number", None)
        setattr(batch, "sales_account_name", None)
        if batch.sales_order_item_id:
            from app.models.account import Account
            from app.models.sales_order import SalesOrder
            from app.models.sales_order_item import SalesOrderItem

            item = session.get(SalesOrderItem, batch.sales_order_item_id)
            if item and item.workspace_id == batch.workspace_id:
                order = session.get(SalesOrder, item.sales_order_id)
                if order and order.workspace_id == batch.workspace_id:
                    setattr(batch, "sales_order_number", order.sales_order_number)
                    account = session.get(Account, order.account_id) if order.account_id else None
                    if account:
                        setattr(batch, "sales_account_name", account.name)
        return batch

    def _linked_order_row(self, kind: str, row, number: str, order_date) -> dict:
        account = getattr(row, "account", None)
        return {
            "order_kind": kind,
            "id": row.id,
            "number": number,
            "account_id": row.account_id,
            "account_name": account.name if account else None,
            "order_date": order_date,
            "total_amount": row.total_amount or 0,
            "voided": bool(row.voided),
        }

    def _require_batch_in_progress(self, session: Session, batch_id: int, workspace_id: int) -> None:
        batch = self.batch_dao.get_by_id_and_workspace(session, id=batch_id, workspace_id=workspace_id)
        if not batch:
            raise ValueError(f"Production batch {batch_id} not found")
        if batch.status != "in_progress":
            if batch.status in self.PRE_START_STATUSES:
                raise ValueError("Start the batch first")
            raise ValueError(f"Batch is {batch.status}")

    def _formula_output_multiplier(
        self, session: Session, batch: ProductionBatch, workspace_id: int
    ) -> Decimal:
        if not batch.formula_id:
            return Decimal("1")
        stages = self.formula_stage_dao.get_by_formula(
            session, formula_id=batch.formula_id, workspace_id=workspace_id
        )
        stage_items = production_formula_stage_item_dao.get_by_formula(
            session, formula_id=batch.formula_id, workspace_id=workspace_id
        )
        if not stages:
            return Decimal("1")
        output_total = finished_good_output_quantity(stages, stage_items)
        derived = self._totals_for_batch(session, batch)
        expected = derived["expected_output_quantity"]
        if expected and output_total > 0:
            return Decimal(str(expected)) / Decimal(str(output_total))
        return Decimal("1")

    def _default_factory_for_step(
        self, session: Session, batch: ProductionBatch, log: ProductionBatchStageLog, workspace_id: int
    ) -> int:
        line_id = log.production_line_id or batch.production_line_id
        line = production_line_dao.get_by_id_and_workspace(
            session, id=line_id, workspace_id=workspace_id
        )
        if not line:
            raise ValueError(f"Production line {line_id} not found")
        return line.factory_id

    def _batch_input_for_item(
        self,
        batch_items: List[ProductionBatchItem],
        item_id: int,
        qty_hint: Optional[int] = None,
    ) -> Optional[ProductionBatchItem]:
        matches = [bi for bi in batch_items if bi.item_role == "input" and bi.item_id == item_id]
        if not matches:
            return None
        if qty_hint is not None:
            for bi in matches:
                line_qty = bi.actual_quantity or bi.expected_quantity
                if line_qty == qty_hint:
                    return bi
        return matches[0]

    def _source_factory_for_batch_item(
        self, bi: ProductionBatchItem, default_factory_id: int
    ) -> int:
        if bi.source_location_type == "storage" and bi.source_location_id:
            return bi.source_location_id
        return default_factory_id

    def _step_input_deductions(
        self,
        session: Session,
        batch: ProductionBatch,
        log: ProductionBatchStageLog,
        workspace_id: int,
    ) -> List[tuple[int, Decimal, int]]:
        """Returns (item_id, quantity, source_factory_id) for this step."""
        default_factory = self._default_factory_for_step(session, batch, log, workspace_id)
        batch_items = self.batch_item_dao.get_by_batch(
            session, batch_id=batch.id, workspace_id=workspace_id
        )
        deductions: List[tuple[int, Decimal, int]] = []
        step_rows = production_batch_stage_item_dao.get_by_stage_log(
            session, batch_stage_log_id=log.id, workspace_id=workspace_id
        )
        if step_rows:
            for row in step_rows:
                if row.item_role != "input":
                    continue
                raw = row.actual_quantity if row.actual_quantity is not None else row.expected_quantity
                if raw is None:
                    continue
                qty = as_quantity(raw)
                if qty <= 0:
                    continue
                bi = self._batch_input_for_item(batch_items, row.item_id, qty)
                factory_id = (
                    self._source_factory_for_batch_item(bi, default_factory)
                    if bi
                    else default_factory
                )
                deductions.append((row.item_id, qty, factory_id))
            return deductions

        if log.formula_stage_id is not None:
            multiplier = self._formula_output_multiplier(session, batch, workspace_id)
            stage_inputs = production_formula_stage_item_dao.get_by_stage(
                session,
                formula_stage_id=log.formula_stage_id,
                workspace_id=workspace_id,
                item_role="input",
            )
            for row in stage_inputs:
                qty = scale_quantity(row.quantity, multiplier)
                if qty <= 0:
                    continue
                bi = self._batch_input_for_item(batch_items, row.item_id, qty)
                factory_id = (
                    self._source_factory_for_batch_item(bi, default_factory)
                    if bi
                    else default_factory
                )
                deductions.append((row.item_id, qty, factory_id))
            return deductions

        for bi in batch_items:
            if bi.item_role != "input":
                continue
            qty = bi.actual_quantity or bi.expected_quantity
            if not qty:
                continue
            factory_id = self._source_factory_for_batch_item(bi, default_factory)
            deductions.append((bi.item_id, as_quantity(qty), factory_id))
        return deductions

    def _validate_and_deduct_batch_inputs(
        self,
        session: Session,
        *,
        batch: ProductionBatch,
        workspace_id: int,
        user_id: int,
        default_factory_id: int,
        note: str,
    ) -> None:
        batch_items = self.batch_item_dao.get_by_batch(
            session, batch_id=batch.id, workspace_id=workspace_id
        )
        input_items = [bi for bi in batch_items if bi.item_role == "input"]
        lines: List[tuple[int, Decimal, int]] = []
        for bi in input_items:
            qty = bi.actual_quantity or bi.expected_quantity
            if not qty:
                continue
            factory_id = self._source_factory_for_batch_item(bi, default_factory_id)
            lines.append((bi.item_id, as_quantity(qty), factory_id))
        self._validate_and_deduct_storage_lines(
            session,
            batch=batch,
            workspace_id=workspace_id,
            user_id=user_id,
            lines=lines,
            note=note,
        )

    def _validate_and_deduct_step_inputs(
        self,
        session: Session,
        *,
        batch: ProductionBatch,
        log: ProductionBatchStageLog,
        workspace_id: int,
        user_id: int,
    ) -> None:
        lines = self._step_input_deductions(session, batch, log, workspace_id)
        if not lines:
            return
        note = (
            f"SYSTEM - PRODUCTION STEP START | {batch.batch_number} | "
            f"{log.stage_name} | step_log={log.id}"
        )
        wip_available = self._wip_available_for_step(
            session, batch=batch, log=log, workspace_id=workspace_id
        )
        self._validate_and_deduct_storage_lines(
            session,
            batch=batch,
            workspace_id=workspace_id,
            user_id=user_id,
            lines=lines,
            note=note,
            wip_available=wip_available,
        )

    def _load_wip_inputs(self, session: Session, batch: ProductionBatch, workspace_id: int) -> dict:
        stage_logs = self.stage_log_dao.get_by_batch(
            session, batch_id=batch.id, workspace_id=workspace_id
        )
        batch_items = self.batch_item_dao.get_by_batch(
            session, batch_id=batch.id, workspace_id=workspace_id
        )
        stages_by_id: dict = {}
        stage_items_by_stage: dict = defaultdict(list)
        multiplier = self._formula_output_multiplier(session, batch, workspace_id)
        if batch.formula_id:
            stages = self.formula_stage_dao.get_by_formula(
                session, formula_id=batch.formula_id, workspace_id=workspace_id
            )
            stages_by_id = {s.id: s for s in stages}
            for row in production_formula_stage_item_dao.get_by_formula(
                session, formula_id=batch.formula_id, workspace_id=workspace_id
            ):
                stage_items_by_stage[row.formula_stage_id].append(row)
        step_items_by_log: dict = defaultdict(list)
        for row in production_batch_stage_item_dao.get_by_batch(
            session, batch_id=batch.id, workspace_id=workspace_id
        ):
            step_items_by_log[row.batch_stage_log_id].append(row)
        return {
            "stage_logs": stage_logs,
            "batch_items": batch_items,
            "stages_by_id": stages_by_id,
            "stage_items_by_stage": dict(stage_items_by_stage),
            "multiplier": multiplier,
            "step_items_by_log": dict(step_items_by_log),
        }

    def _wip_available_for_step(
        self,
        session: Session,
        *,
        batch: ProductionBatch,
        log: ProductionBatchStageLog,
        workspace_id: int,
    ) -> dict[int, Decimal]:
        ctx = self._load_wip_inputs(session, batch, workspace_id)
        return compute_wip_available_by_item(
            ctx["stage_logs"],
            log,
            multiplier=ctx["multiplier"],
            stages_by_id=ctx["stages_by_id"],
            stage_items_by_stage=ctx["stage_items_by_stage"],
            batch_items=ctx["batch_items"],
            step_items_by_log=ctx["step_items_by_log"],
        )

    def _remaining_intermediate_wip(
        self, session: Session, batch: ProductionBatch, workspace_id: int
    ) -> dict[int, Decimal]:
        ctx = self._load_wip_inputs(session, batch, workspace_id)
        pool = compute_remaining_wip(
            ctx["stage_logs"],
            multiplier=ctx["multiplier"],
            stages_by_id=ctx["stages_by_id"],
            stage_items_by_stage=ctx["stage_items_by_stage"],
            batch_items=ctx["batch_items"],
            step_items_by_log=ctx["step_items_by_log"],
        )
        posted: dict[int, Decimal] = defaultdict(lambda: Decimal("0"))
        for bi in ctx["batch_items"]:
            if bi.item_role != "output":
                continue
            raw = bi.actual_quantity or bi.expected_quantity
            if raw:
                posted[bi.item_id] += as_quantity(raw)
        return leftover_intermediate_wip(pool, dict(posted))

    def _wip_void_snapshot(
        self, session: Session, batch: ProductionBatch, workspace_id: int
    ) -> list[dict]:
        remaining = self._remaining_intermediate_wip(session, batch, workspace_id)
        return [
            {"item_id": item_id, "qty": _serialize_value(qty)}
            for item_id, qty in sorted(remaining.items())
        ]

    def _apply_storage_delta(
        self,
        session: Session,
        *,
        workspace_id: int,
        user_id: int,
        factory_id: int,
        item_id: int,
        delta: Decimal,
        batch_id: int,
        note: str,
        transaction_type: str,
        unit_cost: Optional[Decimal] = None,
    ) -> None:
        if delta == 0:
            return
        inv = inventory_dao.ensure_for_factory_item_type(
            session,
            factory_id=factory_id,
            item_id=item_id,
            inventory_type=InventoryTypeEnum.STORAGE,
            workspace_id=workspace_id,
            created_by=user_id,
        )
        old_qty = inv.qty or Decimal("0")
        new_qty = old_qty + delta
        if new_qty < 0:
            raise ValueError(
                f"Storage for item_id={item_id} would go negative ({old_qty} + {delta})"
            )
        inv.qty = new_qty
        session.flush()
        cost = unit_cost if unit_cost else None
        inventory_ledger_dao.create(
            session,
            obj_in={
                "workspace_id": workspace_id,
                "inventory_type": InventoryTypeEnum.STORAGE,
                "factory_id": factory_id,
                "item_id": item_id,
                "transaction_type": transaction_type,
                "quantity": abs(delta),
                "unit_cost": cost,
                "total_cost": (cost * abs(delta)) if cost else None,
                "qty_before": old_qty,
                "qty_after": new_qty,
                "avg_price_before": cost,
                "avg_price_after": cost,
                "source_type": "production_batch",
                "source_id": batch_id,
                "notes": note,
                "performed_by": user_id,
            },
        )

    def _posting_summary(
        self,
        session: Session,
        *,
        batch: ProductionBatch,
        workspace_id: int,
        products: list[dict],
        waste: list[dict],
        flushed: list[dict],
    ) -> dict:
        ctx = self._load_wip_inputs(session, batch, workspace_id)
        leftover_qty = {
            int(row["item_id"]): as_quantity(row["qty"])
            for row in flushed
            if row.get("qty")
        }
        leftovers = leftover_handoff_lines(
            ctx["stage_logs"],
            leftover_qty,
            multiplier=ctx["multiplier"],
            stages_by_id=ctx["stages_by_id"],
            stage_items_by_stage=ctx["stage_items_by_stage"],
            batch_items=ctx["batch_items"],
            step_items_by_log=ctx["step_items_by_log"],
        )
        logs = ctx["stage_logs"]
        ledger_rows = inventory_ledger_dao.list_for_source(
            session,
            workspace_id=workspace_id,
            source_type="production_batch",
            source_id=batch.id,
        )
        storage_rows: list[tuple[str, int, Decimal]] = []
        for row in ledger_rows:
            if row.transaction_type != "consumption":
                continue
            if "PRODUCTION STEP START" not in (row.notes or ""):
                continue
            if row.inventory_type != InventoryTypeEnum.STORAGE:
                continue
            storage_rows.append((row.notes or "", row.item_id, as_quantity(row.quantity)))
        storage_inputs = group_step_start_storage_inputs(
            storage_rows,
            stage_name_by_log_id={log.id: log.stage_name for log in logs},
            stage_order_by_log_id={log.id: (log.stage_order, log.id) for log in logs},
        )
        summary: dict = {}
        if products:
            summary["products"] = products
        if leftovers:
            summary["leftovers"] = leftovers
        if storage_inputs:
            summary["storage_inputs"] = storage_inputs
        if waste:
            summary["waste"] = waste
        return _serialize_value(summary)

    def _flush_leftover_wip_to_storage(
        self,
        session: Session,
        *,
        batch: ProductionBatch,
        workspace_id: int,
        user_id: int,
        factory_id: int,
    ) -> list[dict]:
        remaining = self._remaining_intermediate_wip(session, batch, workspace_id)
        flushed: list[dict] = []
        note = f"SYSTEM - BATCH WIP FLUSH | {batch.batch_number}"
        for item_id, qty in sorted(remaining.items()):
            if qty <= 0:
                continue
            self._apply_storage_delta(
                session,
                workspace_id=workspace_id,
                user_id=user_id,
                factory_id=factory_id,
                item_id=item_id,
                delta=qty,
                batch_id=batch.id,
                note=note,
                transaction_type="transfer_in",
                unit_cost=None,
            )
            flushed.append({"item_id": item_id, "qty": _serialize_value(qty)})
        return flushed

    def _reverse_step_start_storage(
        self,
        session: Session,
        *,
        batch: ProductionBatch,
        workspace_id: int,
        user_id: int,
    ) -> list[dict]:
        rows = inventory_ledger_dao.list_for_source(
            session,
            workspace_id=workspace_id,
            source_type="production_batch",
            source_id=batch.id,
        )
        reversed_lines: list[dict] = []
        note = f"SYSTEM - BATCH CANCEL REVERSAL | {batch.batch_number}"
        for row in rows:
            if row.transaction_type != "consumption":
                continue
            if "PRODUCTION STEP START" not in (row.notes or ""):
                continue
            if row.inventory_type != InventoryTypeEnum.STORAGE:
                continue
            qty = as_quantity(row.quantity)
            unit_cost = as_quantity(row.unit_cost) if row.unit_cost is not None else None
            self._apply_storage_delta(
                session,
                workspace_id=workspace_id,
                user_id=user_id,
                factory_id=row.factory_id,
                item_id=row.item_id,
                delta=qty,
                batch_id=batch.id,
                note=note,
                transaction_type="transfer_in",
                unit_cost=unit_cost,
            )
            reversed_lines.append(
                {
                    "item_id": row.item_id,
                    "qty": _serialize_value(qty),
                    "factory_id": row.factory_id,
                    "ledger_id": row.id,
                }
            )
        return reversed_lines

    def get_batch_stage_items(
        self, session: Session, batch_id: int, workspace_id: int
    ):
        batch = self.batch_dao.get_by_id_and_workspace(
            session, id=batch_id, workspace_id=workspace_id
        )
        if not batch:
            raise ValueError(f"Production batch {batch_id} not found")
        return production_batch_stage_item_dao.get_by_batch(
            session, batch_id=batch_id, workspace_id=workspace_id
        )

    def update_batch_stage_item_actual(
        self,
        session: Session,
        item_row_id: int,
        actual_quantity: Optional[Decimal],
        workspace_id: int,
        user_id: Optional[int] = None,
    ):
        row = production_batch_stage_item_dao.get_by_id_and_workspace(
            session, id=item_row_id, workspace_id=workspace_id
        )
        if not row:
            raise ValueError(f"Batch stage item {item_row_id} not found")
        if row.item_role not in ("input", "output", "waste", "byproduct"):
            raise ValueError("Quantity can only be set on step material rows")
        log = self._require_stage_log(session, row.batch_stage_log_id, workspace_id)
        if log.status not in ("pending", "in_progress"):
            raise ValueError("Quantity is locked after the step finishes")
        if actual_quantity is not None and actual_quantity < 0:
            raise ValueError("Quantity cannot be negative")
        before = row.actual_quantity
        updated = production_batch_stage_item_dao.update(
            session,
            db_obj=row,
            obj_in={"actual_quantity": actual_quantity},
        )
        if before != actual_quantity:
            log_batch_event(
                session,
                workspace_id=workspace_id,
                batch_id=row.batch_id,
                batch_stage_log_id=log.id,
                event_type="item_actual_changed",
                description=f"{log.stage_name} updated" if log.stage_name else "Updated",
                performed_by=user_id,
                metadata={
                    "stage_name": log.stage_name,
                    "item_id": row.item_id,
                    "item_role": row.item_role,
                    "before": _serialize_value(before),
                    "after": _serialize_value(actual_quantity),
                },
            )
        return updated

    def _validate_and_deduct_storage_lines(
        self,
        session: Session,
        *,
        batch: ProductionBatch,
        workspace_id: int,
        user_id: int,
        lines: List[tuple[int, Decimal, int]],
        note: str,
        wip_available: Optional[dict[int, Decimal]] = None,
    ) -> None:
        wip_pool = dict(wip_available) if wip_available else None
        shortfalls = []
        storage_lines: List[tuple[int, Decimal, int]] = []
        for item_id, qty_needed, source_factory_id in lines:
            storage_needed = qty_needed
            wip_used = Decimal("0")
            if wip_pool is not None:
                wip_used, storage_needed = storage_needed_after_wip(
                    item_id, qty_needed, wip_pool
                )
            if storage_needed <= 0:
                storage_lines.append((item_id, Decimal("0"), source_factory_id))
                continue
            inv = inventory_dao.get_by_factory_item_type(
                session,
                factory_id=source_factory_id,
                item_id=item_id,
                inventory_type=InventoryTypeEnum.STORAGE,
                workspace_id=workspace_id,
            )
            available = inv.qty if inv else Decimal("0")
            if available < storage_needed:
                shortfalls.append(
                    {
                        "item_id": item_id,
                        "required_qty": qty_needed,
                        "storage_needed": storage_needed,
                        "available_qty": available,
                        "from_prior_steps": wip_used,
                    }
                )
            storage_lines.append((item_id, storage_needed, source_factory_id))
        if shortfalls:
            detail = "; ".join(
                f"item_id={s['item_id']} (required {s['required_qty']}, "
                f"storage {s['available_qty']}, from prior steps {s['from_prior_steps']})"
                for s in shortfalls
            )
            raise ValueError(
                f"Insufficient inventory for {len(shortfalls)} input item(s): {detail}. "
                f"Replenish storage or complete earlier steps before starting."
            )

        for item_id, qty_to_deduct, source_factory_id in storage_lines:
            if qty_to_deduct <= 0:
                continue
            inv = inventory_dao.get_by_factory_item_type(
                session,
                factory_id=source_factory_id,
                item_id=item_id,
                inventory_type=InventoryTypeEnum.STORAGE,
                workspace_id=workspace_id,
            )
            if not inv:
                continue
            old_qty = inv.qty
            new_qty = old_qty - qty_to_deduct
            avg_price = inv.avg_price if inv.avg_price is not None else Decimal("0")
            inv.qty = new_qty
            session.flush()
            inventory_ledger_dao.create(
                session,
                obj_in={
                    "workspace_id": workspace_id,
                    "inventory_type": InventoryTypeEnum.STORAGE,
                    "factory_id": source_factory_id,
                    "item_id": item_id,
                    "transaction_type": "consumption",
                    "quantity": qty_to_deduct,
                    "unit_cost": avg_price if avg_price else None,
                    "total_cost": (avg_price * qty_to_deduct) if avg_price else None,
                    "qty_before": old_qty,
                    "qty_after": new_qty,
                    "avg_price_before": avg_price if avg_price else None,
                    "avg_price_after": avg_price if avg_price else None,
                    "source_type": "production_batch",
                    "source_id": batch.id,
                    "notes": note,
                    "performed_by": user_id,
                },
            )

    def _ensure_batch_running_for_step(
        self,
        session: Session,
        batch_id: int,
        workspace_id: int,
        user_id: int,
        started_at: Optional[datetime] = None,
    ) -> None:
        """Draft batches move to in_progress when the first step starts; storage deducts per step."""
        batch = self.batch_dao.get_by_id_and_workspace(session, id=batch_id, workspace_id=workspace_id)
        if not batch:
            raise ValueError(f"Production batch {batch_id} not found")
        if batch.status in self.PRE_START_STATUSES:
            self.start_batch(
                session,
                batch_id,
                workspace_id,
                user_id,
                started_at=started_at,
                via_first_step=True,
            )
            return
        if batch.status != "in_progress":
            raise ValueError(f"Batch is {batch.status}")

    def _require_stage_log(self, session: Session, log_id: int, workspace_id: int) -> ProductionBatchStageLog:
        log = self.stage_log_dao.get_by_id_and_workspace(session, id=log_id, workspace_id=workspace_id)
        if not log:
            raise ValueError(f"Batch stage log {log_id} not found")
        return log

    def _require_earlier_steps_closed(
        self, session: Session, log: ProductionBatchStageLog, workspace_id: int
    ) -> None:
        logs = self.stage_log_dao.get_by_batch(
            session, batch_id=log.batch_id, workspace_id=workspace_id
        )
        for other in logs:
            if other.id == log.id:
                continue
            if other.stage_order >= log.stage_order:
                continue
            if other.status in ("pending", "in_progress"):
                raise ValueError(
                    f'Complete or skip "{other.stage_name}" before starting this step'
                )

    def _planned_step_start(self, session: Session, log, batch, workspace_id: int):
        logs = self.stage_log_dao.get_by_batch(session, batch_id=log.batch_id, workspace_id=workspace_id)
        earlier = [
            row for row in logs
            if row.id != log.id and (row.stage_order < log.stage_order or (row.stage_order == log.stage_order and row.id < log.id))
        ]
        completed = [row.completed_at for row in earlier if row.completed_at]
        if completed:
            return max(completed)
        if log.stage_order == min((row.stage_order for row in logs), default=log.stage_order):
            return batch.planned_start_at if batch else None
        return batch.planned_start_at if batch and not earlier else None

    def _create_rework_log(self, session, log, workspace_id: int, rework_quantity: int, rework_to_log_id: int) -> None:
        target = self._require_stage_log(session, rework_to_log_id, workspace_id)
        if target.batch_id != log.batch_id:
            raise ValueError("Rework target must be a step on the same batch")
        if target.stage_order >= log.stage_order:
            raise ValueError("Rework can only be sent to an earlier step")
        children = self.stage_log_dao.get_by_batch(session, batch_id=log.batch_id, workspace_id=workspace_id)
        if any(row.rework_of_log_id == log.id and row.status in ("pending", "in_progress") for row in children):
            raise ValueError("This step already has an open rework")
        self.stage_log_dao.create(
            session,
            obj_in={
                "workspace_id": workspace_id,
                "batch_id": log.batch_id,
                "formula_stage_id": target.formula_stage_id,
                "route_step_id": target.route_step_id,
                "stage_name": target.stage_name,
                "stage_order": target.stage_order,
                "production_line_id": target.production_line_id,
                "machine_id": target.machine_id,
                "expected_duration_minutes": target.expected_duration_minutes,
                "expected_output_quantity": target.expected_output_quantity,
                "status": "pending",
                "rework_of_log_id": log.id,
                "input_quantity": rework_quantity,
            },
        )

    def _flip_machine_for_live_step(self, session, log, workspace_id: int, user_id: int, *, running: bool) -> None:
        if not log.machine_id:
            return
        from app.managers.machine_manager import machine_manager
        from app.managers.machine_activity_manager import machine_activity_manager
        from app.models.enums import MachineEventTypeEnum
        from app.schemas.machine_event import MachineEventCreate
        from fastapi import HTTPException

        latest = machine_activity_manager.get_latest_status(session, log.machine_id, workspace_id)
        prev = machine_activity_manager.status_from_activity(latest)
        if prev in (MachineEventTypeEnum.MAINTENANCE.value, MachineEventTypeEnum.OFF.value):
            return
        if not running and machine_has_other_in_progress_step(
            session,
            workspace_id=workspace_id,
            machine_id=log.machine_id,
            exclude_stage_log_id=log.id,
        ):
            return
        target = MachineEventTypeEnum.RUNNING if running else MachineEventTypeEnum.IDLE
        if prev == target.value:
            return
        try:
            machine_manager.create_machine_event(
                session,
                event_data=MachineEventCreate(machine_id=log.machine_id, event_type=target, note=log.stage_name),
                workspace_id=workspace_id,
                user_id=user_id,
                extra_metadata={"batch_id": log.batch_id, "stage_log_id": log.id},
            )
        except HTTPException:
            return

    def _get_machine(self, session: Session, machine_id: int, workspace_id: int) -> Machine:
        machine = (
            session.query(Machine)
            .filter(Machine.id == machine_id, Machine.workspace_id == workspace_id, Machine.is_deleted.is_(False))
            .first()
        )
        if not machine:
            raise ValueError(f"Machine {machine_id} not found")
        return machine

    def _require_machine(self, session: Session, machine_id: int, workspace_id: int) -> None:
        self._get_machine(session, machine_id, workspace_id)

    def _workspace_machine_pick_policy(self, session: Session, workspace_id: int):
        workspace = workspace_dao.get(session, id=workspace_id)
        return parse_production_machine_pick_policy(workspace.settings if workspace else None)

    def _enforce_machine_pick_policy(
        self,
        session: Session,
        *,
        workspace_id: int,
        machine_id: int,
        batch: ProductionBatch,
        stage_log: ProductionBatchStageLog | None,
    ) -> None:
        policy = self._workspace_machine_pick_policy(session, workspace_id)
        if policy == "soft":
            return
        machine = self._get_machine(session, machine_id, workspace_id)
        assert_machine_pick_allowed_for_batch_step(
            session,
            workspace_id=workspace_id,
            machine=machine,
            policy=policy,
            batch=batch,
            stage_log=stage_log,
            machine_id=machine_id,
        )

    def _machine_ids_for_line(
        self, session: Session, *, production_line_id: int, workspace_id: int
    ) -> List[int]:
        machine_ids = production_line_machine_dao.get_machine_ids_for_line(
            session, production_line_id=production_line_id, workspace_id=workspace_id
        )
        if machine_ids:
            return machine_ids
        line = production_line_dao.get_by_id_and_workspace(
            session, id=production_line_id, workspace_id=workspace_id
        )
        if line and line.machine_id:
            return [line.machine_id]
        return []

    def _validate_machine_on_line(
        self,
        session: Session,
        *,
        machine_id: int,
        production_line_id: int,
        workspace_id: int,
    ) -> None:
        self._require_machine(session, machine_id, workspace_id)
        allowed = self._machine_ids_for_line(
            session, production_line_id=production_line_id, workspace_id=workspace_id
        )
        if machine_id not in allowed:
            raise ValueError(f"Machine {machine_id} is not assigned to production line {production_line_id}")

    def _validate_sales_order_item(self, session: Session, item_id: int, workspace_id: int) -> None:
        from app.models.sales_order import SalesOrder
        from app.models.sales_order_item import SalesOrderItem

        item = (
            session.query(SalesOrderItem)
            .filter(SalesOrderItem.id == item_id, SalesOrderItem.workspace_id == workspace_id)
            .first()
        )
        if not item:
            raise ValueError(f"Sales order item {item_id} not found")
        order = (
            session.query(SalesOrder)
            .filter(SalesOrder.id == item.sales_order_id, SalesOrder.workspace_id == workspace_id)
            .first()
        )
        if not order:
            raise ValueError(f"Sales order item {item_id} not found")
        status_name = order.current_status.name if order.current_status else ""
        if status_name.lower() in ("cancelled", "canceled"):
            raise ValueError(f"Sales order {order.sales_order_number} is cancelled")

    def _route_factory_id(self, session: Session, route_id: int, workspace_id: int) -> int:
        from app.dao.production_route import production_route_dao

        route = production_route_dao.get_by_id_and_workspace(session, id=route_id, workspace_id=workspace_id)
        if not route:
            raise ValueError(f"Production route {route_id} not found")
        return route.factory_id


# Singleton instance
production_batch_manager = ProductionBatchManager()
