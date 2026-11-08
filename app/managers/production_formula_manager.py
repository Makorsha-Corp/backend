"""Production Formula Manager for business logic"""
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from app.managers.base_manager import BaseManager
from app.models.production_formula import ProductionFormula
from app.dao.production_formula import production_formula_dao
from app.dao.production_formula_stage import production_formula_stage_dao
from app.dao.production_formula_stage_item import production_formula_stage_item_dao
from app.dao.production_formula_stage_parameter import production_formula_stage_parameter_dao
from app.dao.production_line import production_line_dao
from app.dao.production_route import production_route_dao, production_route_step_dao
from app.dao.item import item_dao
from app.models.production_formula_stage import ProductionFormulaStage
from app.models.production_formula_stage_item import ProductionFormulaStageItem
from app.models.production_formula_stage_parameter import ProductionFormulaStageParameter
from app.models.production_route import ProductionRoute, ProductionRouteStep
from app.models.machine import Machine
from app.schemas.production_formula import ProductionFormulaCreate, ProductionFormulaUpdate
from app.schemas.production_formula_stage import ProductionFormulaStageCreate, ProductionFormulaStageUpdate
from app.utils.recipe_derived_metrics import finished_good_output_quantity
from app.schemas.production_formula_stage_item import (
    ProductionFormulaStageItemCreate,
    ProductionFormulaStageItemUpdate,
)
from app.schemas.production_formula_stage_parameter import (
    ProductionFormulaStageParameterCreate,
    ProductionFormulaStageParameterUpdate,
)
from app.utils.production_parameter_numeric import optional_numeric_from_text


class ProductionFormulaManager(BaseManager[ProductionFormula]):
    """
    STANDALONE MANAGER: Production formula business logic.

    Manages: ProductionFormula and path-stage materials
    Operations: CRUD with validation, default formula management

    Does NOT commit transactions - that's the service layer's responsibility.
    """

    VALID_ITEM_ROLES = {'input', 'output', 'waste', 'byproduct'}

    def __init__(self):
        super().__init__(ProductionFormula)
        self.formula_dao = production_formula_dao
        self.formula_stage_dao = production_formula_stage_dao
        self.formula_stage_item_dao = production_formula_stage_item_dao
        self.formula_stage_parameter_dao = production_formula_stage_parameter_dao

    # ─── Formula CRUD ───────────────────────────────────────────────

    def create_formula(
        self,
        session: Session,
        formula_data: ProductionFormulaCreate,
        workspace_id: int,
        user_id: int
    ) -> ProductionFormula:
        """
        Create a new production formula with a private route (1:1), or copy from another recipe.
        """
        existing = self.formula_dao.get_by_formula_code(
            session, formula_code=formula_data.formula_code, workspace_id=workspace_id
        )
        if existing:
            raise ValueError(
                f"Formula code '{formula_data.formula_code}' already exists in this workspace"
            )

        if formula_data.is_default:
            self._clear_other_defaults(session, workspace_id)

        if formula_data.copy_from_formula_id is not None:
            return self.duplicate_formula(
                session,
                source_formula_id=formula_data.copy_from_formula_id,
                formula_code=formula_data.formula_code,
                name=formula_data.name,
                description=formula_data.description,
                factory_id=formula_data.factory_id,
                workspace_id=workspace_id,
                user_id=user_id,
            )

        if formula_data.factory_id is None:
            raise ValueError("factory_id is required when creating a blank recipe")

        self._require_factory_for_route(session, formula_data.factory_id, workspace_id)

        formula_dict = formula_data.model_dump(
            exclude={"factory_id", "copy_from_formula_id"},
        )
        formula_dict["workspace_id"] = workspace_id
        formula_dict["created_by"] = user_id
        formula_dict["route_id"] = None

        formula = self.formula_dao.create(session, obj_in=formula_dict)
        route = production_route_dao.create(
            session,
            obj_in={
                "workspace_id": workspace_id,
                "factory_id": formula_data.factory_id,
                "name": f"{formula.name} path",
                "description": None,
                "is_active": True,
                "created_by": user_id,
            },
        )
        return self.formula_dao.update(
            session, db_obj=formula, obj_in={"route_id": route.id}
        )

    def update_formula(
        self,
        session: Session,
        formula_id: int,
        formula_data: ProductionFormulaUpdate,
        workspace_id: int,
        user_id: int
    ) -> ProductionFormula:
        """
        Update an existing production formula.

        Validates workspace ownership. If is_default is set to True,
        clears default flag on other formulas in workspace.
        """
        formula = self.formula_dao.get(session, id=formula_id)
        if not formula:
            raise ValueError(f"Production formula {formula_id} not found")
        if formula.workspace_id != workspace_id:
            raise ValueError(
                f"Production formula {formula_id} does not belong to workspace {workspace_id}"
            )

        # If setting as default, clear other defaults
        update_dict = formula_data.model_dump(exclude_unset=True, exclude_none=True)
        if "route_id" in update_dict:
            raise ValueError("Recipe path is private; change lines on the recipe, not route_id")
        if update_dict.get('is_default') is True:
            self._clear_other_defaults(session, workspace_id, exclude_id=formula_id)

        update_dict['updated_by'] = user_id
        return self.formula_dao.update(session, db_obj=formula, obj_in=update_dict)

    def get_formula(
        self,
        session: Session,
        formula_id: int,
        workspace_id: int
    ) -> Optional[ProductionFormula]:
        """Get formula by ID within workspace."""
        return self.formula_dao.get_by_id_and_workspace(
            session, id=formula_id, workspace_id=workspace_id
        )

    def get_formulas(
        self,
        session: Session,
        workspace_id: int,
        active_only: bool = False,
        skip: int = 0,
        limit: int = 100
    ) -> List[ProductionFormula]:
        """Get formulas with optional filtering."""
        if active_only:
            return self.formula_dao.get_active_by_workspace(
                session, workspace_id=workspace_id, skip=skip, limit=limit
            )
        else:
            return self.formula_dao.get_by_workspace(
                session, workspace_id=workspace_id, skip=skip, limit=limit
            )

    def delete_formula(
        self,
        session: Session,
        formula_id: int,
        workspace_id: int,
        user_id: int
    ) -> ProductionFormula:
        """Soft delete a formula (set is_active=False)."""
        formula = self.formula_dao.get(session, id=formula_id)
        if not formula:
            raise ValueError(f"Production formula {formula_id} not found")
        if formula.workspace_id != workspace_id:
            raise ValueError(
                f"Production formula {formula_id} does not belong to workspace {workspace_id}"
            )
        if not formula.is_active:
            return formula  # Already deleted — idempotent

        return self.formula_dao.update(
            session, db_obj=formula, obj_in={'is_active': False, 'is_default': False, 'updated_by': user_id}
        )

    def get_formula_base_output(
        self,
        session: Session,
        formula_id: int,
        workspace_id: int
    ) -> int:
        """Finished-good qty from output materials on the last path step."""
        stages = self.formula_stage_dao.get_by_formula(
            session, formula_id=formula_id, workspace_id=workspace_id
        )
        stage_items = self.formula_stage_item_dao.get_by_formula(
            session, formula_id=formula_id, workspace_id=workspace_id
        )
        total = finished_good_output_quantity(stages, stage_items)
        if total <= 0:
            raise ValueError(
                f"Formula {formula_id} has no finished-good output on the last step. "
                f"Add output materials on the final path step before using the recipe."
            )
        return total

    # ─── Formula Stage CRUD ─────────────────────────────────────────

    def _validate_stage_refs(
        self,
        session: Session,
        workspace_id: int,
        production_line_id: Optional[int],
        machine_id: Optional[int],
        expected_output_item_id: Optional[int],
        *,
        previous_production_line_id: Optional[int] = None,
    ) -> None:
        if production_line_id is not None:
            line = production_line_dao.get_by_id_and_workspace(
                session, id=production_line_id, workspace_id=workspace_id
            )
            if not line:
                raise ValueError(f"Production line {production_line_id} not found")
            from app.utils.production_line_machines import assert_production_line_assignable

            assert_production_line_assignable(
                session,
                line_id=production_line_id,
                workspace_id=workspace_id,
                previous_line_id=previous_production_line_id,
            )
        if machine_id is not None:
            machine = (
                session.query(Machine)
                .filter(
                    Machine.id == machine_id,
                    Machine.workspace_id == workspace_id,
                    Machine.is_deleted == False,
                )
                .first()
            )
            if not machine:
                raise ValueError(f"Machine {machine_id} not found")
        if expected_output_item_id is not None:
            item = item_dao.get(session, id=expected_output_item_id)
            if not item or item.workspace_id != workspace_id:
                raise ValueError(f"Item {expected_output_item_id} not found")

    def get_formula_stages(
        self, session: Session, formula_id: int, workspace_id: int
    ) -> List[ProductionFormulaStage]:
        formula = self.formula_dao.get_by_id_and_workspace(
            session, id=formula_id, workspace_id=workspace_id
        )
        if not formula:
            raise ValueError(f"Production formula {formula_id} not found")
        return self.formula_stage_dao.get_by_formula(
            session, formula_id=formula_id, workspace_id=workspace_id
        )

    def add_formula_stage(
        self,
        session: Session,
        stage_data: ProductionFormulaStageCreate,
        workspace_id: int,
    ) -> ProductionFormulaStage:
        formula = self.formula_dao.get_by_id_and_workspace(
            session, id=stage_data.formula_id, workspace_id=workspace_id
        )
        if not formula:
            raise ValueError(f"Production formula {stage_data.formula_id} not found")
        if formula.route_id is not None:
            raise ValueError("Add steps on the route, not on a route-bound recipe")

        self._validate_stage_refs(
            session,
            workspace_id,
            stage_data.production_line_id,
            stage_data.machine_id,
            stage_data.expected_output_item_id,
        )

        existing = self.formula_stage_dao.get_by_formula(
            session, formula_id=stage_data.formula_id, workspace_id=workspace_id
        )
        if any(s.stage_order == stage_data.stage_order for s in existing):
            raise ValueError(f"Stage order {stage_data.stage_order} already exists for this formula")

        stage_dict = stage_data.model_dump()
        stage_dict["workspace_id"] = workspace_id
        stage = self.formula_stage_dao.create(session, obj_in=stage_dict)
        return stage

    def update_formula_stage(
        self,
        session: Session,
        stage_id: int,
        stage_data: ProductionFormulaStageUpdate,
        workspace_id: int,
    ) -> ProductionFormulaStage:
        stage = self.formula_stage_dao.get_by_id_and_workspace(
            session, id=stage_id, workspace_id=workspace_id
        )
        if not stage:
            raise ValueError(f"Formula stage {stage_id} not found")

        update_dict = stage_data.model_dump(exclude_unset=True)
        if not update_dict:
            return stage

        self._validate_stage_refs(
            session,
            workspace_id,
            update_dict.get("production_line_id", stage.production_line_id),
            update_dict.get("machine_id", stage.machine_id),
            update_dict.get("expected_output_item_id", stage.expected_output_item_id),
            previous_production_line_id=stage.production_line_id,
        )

        formula = self.formula_dao.get_by_id_and_workspace(
            session, id=stage.formula_id, workspace_id=workspace_id
        )
        if formula and formula.route_id is not None:
            allowed = {
                "is_used",
                "expected_duration_minutes",
                "expected_output_quantity",
                "expected_output_item_id",
                "notes",
            }
            blocked = set(update_dict) - allowed
            if blocked:
                raise ValueError(
                    "Route-bound recipe stages only allow used flag, targets, and notes"
                )

        if "stage_order" in update_dict and update_dict["stage_order"] != stage.stage_order:
            siblings = self.formula_stage_dao.get_by_formula(
                session, formula_id=stage.formula_id, workspace_id=workspace_id
            )
            if any(
                s.id != stage.id and s.stage_order == update_dict["stage_order"] for s in siblings
            ):
                raise ValueError(f"Stage order {update_dict['stage_order']} already exists for this formula")

        updated = self.formula_stage_dao.update(session, db_obj=stage, obj_in=update_dict)
        if "is_used" in update_dict:
            self._reapply_handoff_around_stage(session, updated, workspace_id)
        return updated

    def remove_formula_stage(
        self, session: Session, stage_id: int, workspace_id: int
    ) -> ProductionFormulaStage:
        stage = self.formula_stage_dao.get_by_id_and_workspace(
            session, id=stage_id, workspace_id=workspace_id
        )
        if not stage:
            raise ValueError(f"Formula stage {stage_id} not found")
        formula = self.formula_dao.get_by_id_and_workspace(
            session, id=stage.formula_id, workspace_id=workspace_id
        )
        formula_id = stage.formula_id
        legacy_route_step_id = stage.route_step_id
        self.formula_stage_dao.remove(session, id=stage.id)
        self._compact_formula_stage_orders(session, formula_id, workspace_id)
        if legacy_route_step_id is not None:
            legacy_step = production_route_step_dao.get_by_id_and_workspace(
                session, id=legacy_route_step_id, workspace_id=workspace_id
            )
            if legacy_step is not None:
                if formula and formula.route_id is not None:
                    self._assert_route_exclusive_to_formula(
                        session,
                        route_id=formula.route_id,
                        formula_id=formula.id,
                        workspace_id=workspace_id,
                    )
                production_route_step_dao.remove(session, id=legacy_step.id)
        return stage

    def _compact_formula_stage_orders(
        self, session: Session, formula_id: int, workspace_id: int
    ) -> None:
        stages = self._sorted_formula_stages(
            session, formula_id=formula_id, workspace_id=workspace_id
        )
        for index, stage in enumerate(stages, start=1):
            if stage.stage_order != index:
                self.formula_stage_dao.update(
                    session, db_obj=stage, obj_in={"stage_order": index}
                )
        session.flush()

    # ─── Helpers ────────────────────────────────────────────────────

    def _require_route(self, session: Session, route_id: int, workspace_id: int) -> ProductionRoute:
        route = production_route_dao.get_by_id_and_workspace(session, id=route_id, workspace_id=workspace_id)
        if not route:
            raise ValueError(f"Production route {route_id} not found in this workspace")
        return route

    def _validate_formula_route_link(
        self, session: Session, *, route_id: int, workspace_id: int
    ) -> ProductionRoute:
        route = self._require_route(session, route_id, workspace_id)
        if not route.is_active:
            raise ValueError(f"Production route {route_id} is not active")
        return route

    def _require_factory_for_route(self, session: Session, factory_id: int, workspace_id: int) -> None:
        from app.models.factory import Factory

        factory = (
            session.query(Factory)
            .filter(Factory.id == factory_id, Factory.workspace_id == workspace_id)
            .first()
        )
        if not factory:
            raise ValueError(f"Factory {factory_id} not found")

    def _assert_route_exclusive_to_formula(
        self,
        session: Session,
        *,
        route_id: int,
        formula_id: int,
        workspace_id: int,
    ) -> None:
        others = (
            session.query(ProductionFormula)
            .filter(
                ProductionFormula.workspace_id == workspace_id,
                ProductionFormula.route_id == route_id,
                ProductionFormula.id != formula_id,
                ProductionFormula.is_active.is_(True),
            )
            .count()
        )
        if others:
            raise ValueError("This path is linked to another recipe; copy the recipe instead")

    def _ensure_private_route(
        self,
        session: Session,
        *,
        formula: ProductionFormula,
        factory_id: int,
        workspace_id: int,
        user_id: int,
    ) -> ProductionRoute:
        if formula.route_id is not None:
            return self._require_route(session, formula.route_id, workspace_id)
        self._require_factory_for_route(session, factory_id, workspace_id)
        route = production_route_dao.create(
            session,
            obj_in={
                "workspace_id": workspace_id,
                "factory_id": factory_id,
                "name": f"{formula.name} path",
                "description": None,
                "is_active": True,
                "created_by": user_id,
            },
        )
        self.formula_dao.update(session, db_obj=formula, obj_in={"route_id": route.id})
        session.flush()
        return route

    def duplicate_formula(
        self,
        session: Session,
        *,
        source_formula_id: int,
        formula_code: str,
        name: str,
        description: Optional[str],
        factory_id: Optional[int],
        workspace_id: int,
        user_id: int,
    ) -> ProductionFormula:
        source = self.formula_dao.get_by_id_and_workspace(
            session, id=source_formula_id, workspace_id=workspace_id
        )
        if not source or not source.is_active:
            raise ValueError(f"Production formula {source_formula_id} not found")

        existing = self.formula_dao.get_by_formula_code(
            session, formula_code=formula_code, workspace_id=workspace_id
        )
        if existing:
            raise ValueError(f"Formula code '{formula_code}' already exists in this workspace")

        route_factory_id = factory_id
        if source.route_id is not None:
            source_route = self._require_route(session, source.route_id, workspace_id)
            route_factory_id = route_factory_id or source_route.factory_id
        if route_factory_id is None:
            raise ValueError("factory_id is required when copying a recipe without a path")

        self._require_factory_for_route(session, route_factory_id, workspace_id)

        new_formula = self.formula_dao.create(
            session,
            obj_in={
                "workspace_id": workspace_id,
                "formula_code": formula_code,
                "name": name,
                "description": description or source.description,
                "version": source.version,
                "is_active": True,
                "is_default": False,
                "route_id": None,
                "created_by": user_id,
            },
        )

        stage_id_map: Dict[int, int] = {}
        if source.route_id is not None:
            source_route = self._require_route(session, source.route_id, workspace_id)
            new_route = production_route_dao.create(
                session,
                obj_in={
                    "workspace_id": workspace_id,
                    "factory_id": route_factory_id,
                    "name": f"{name} path",
                    "description": source_route.description,
                    "is_active": True,
                    "created_by": user_id,
                },
            )
            self.formula_dao.update(session, db_obj=new_formula, obj_in={"route_id": new_route.id})
            steps = production_route_step_dao.get_by_route(
                session, route_id=source_route.id, workspace_id=workspace_id
            )
            step_id_map: Dict[int, int] = {}
            for step in sorted(steps, key=lambda row: row.step_order):
                new_step = production_route_step_dao.create(
                    session,
                    obj_in={
                        "workspace_id": workspace_id,
                        "route_id": new_route.id,
                        "step_order": step.step_order,
                        "production_line_id": step.production_line_id,
                        "name": step.name,
                        "notes": step.notes,
                    },
                )
                step_id_map[step.id] = new_step.id

            source_stages = self.formula_stage_dao.get_by_formula(
                session, formula_id=source.id, workspace_id=workspace_id
            )
            for stage in sorted(source_stages, key=lambda row: row.stage_order):
                new_stage = self.formula_stage_dao.create(
                    session,
                    obj_in={
                        "workspace_id": workspace_id,
                        "formula_id": new_formula.id,
                        "route_step_id": step_id_map.get(stage.route_step_id) if stage.route_step_id else None,
                        "stage_order": stage.stage_order,
                        "name": stage.name,
                        "production_line_id": stage.production_line_id,
                        "machine_id": stage.machine_id,
                        "expected_duration_minutes": stage.expected_duration_minutes,
                        "expected_output_quantity": stage.expected_output_quantity,
                        "expected_output_item_id": stage.expected_output_item_id,
                        "notes": stage.notes,
                        "is_used": getattr(stage, "is_used", True),
                    },
                )
                stage_id_map[stage.id] = new_stage.id
        else:
            self._ensure_private_route(
                session,
                formula=new_formula,
                factory_id=route_factory_id,
                workspace_id=workspace_id,
                user_id=user_id,
            )
            source_stages = self.formula_stage_dao.get_by_formula(
                session, formula_id=source.id, workspace_id=workspace_id
            )
            for stage in sorted(source_stages, key=lambda row: row.stage_order):
                new_stage = self.formula_stage_dao.create(
                    session,
                    obj_in={
                        "workspace_id": workspace_id,
                        "formula_id": new_formula.id,
                        "route_step_id": None,
                        "stage_order": stage.stage_order,
                        "name": stage.name,
                        "production_line_id": stage.production_line_id,
                        "machine_id": stage.machine_id,
                        "expected_duration_minutes": stage.expected_duration_minutes,
                        "expected_output_quantity": stage.expected_output_quantity,
                        "expected_output_item_id": stage.expected_output_item_id,
                        "notes": stage.notes,
                        "is_used": getattr(stage, "is_used", True),
                    },
                )
                stage_id_map[stage.id] = new_stage.id

        for item in self.formula_stage_item_dao.get_by_formula(
            session, formula_id=source.id, workspace_id=workspace_id
        ):
            mapped_stage = stage_id_map.get(item.formula_stage_id)
            if mapped_stage is None:
                continue
            self.formula_stage_item_dao.create(
                session,
                obj_in={
                    "workspace_id": workspace_id,
                    "formula_stage_id": mapped_stage,
                    "item_id": item.item_id,
                    "item_role": item.item_role,
                    "quantity": item.quantity,
                    "unit": item.unit,
                    "is_optional": item.is_optional,
                    "tolerance_percentage": item.tolerance_percentage,
                },
            )

        for param in self.formula_stage_parameter_dao.get_by_formula(
            session, formula_id=source.id, workspace_id=workspace_id
        ):
            mapped_stage = stage_id_map.get(param.formula_stage_id)
            if mapped_stage is None:
                continue
            self.formula_stage_parameter_dao.create(
                session,
                obj_in={
                    "workspace_id": workspace_id,
                    "formula_stage_id": mapped_stage,
                    "label": param.label,
                    "planned_value": param.planned_value,
                    "planned_value_numeric": param.planned_value_numeric,
                    "unit": param.unit,
                    "sort_order": param.sort_order,
                },
            )

        return new_formula

    def replace_stages_from_route(
        self, session: Session, formula: ProductionFormula, workspace_id: int
    ) -> None:
        """One formula stage per route step, linked by route_step_id. Replaces existing stages."""
        if formula.route_id is None:
            return
        route = self._require_route(session, formula.route_id, workspace_id)
        existing = self.formula_stage_dao.get_by_formula(
            session, formula_id=formula.id, workspace_id=workspace_id
        )
        for stage in existing:
            self.formula_stage_dao.remove(session, id=stage.id)
        session.flush()
        steps = production_route_step_dao.get_by_route(
            session, route_id=route.id, workspace_id=workspace_id
        )
        for step in sorted(steps, key=lambda row: row.step_order):
            self.formula_stage_dao.create(
                session,
                obj_in={
                    "workspace_id": workspace_id,
                    "formula_id": formula.id,
                    "route_step_id": step.id,
                    "stage_order": step.step_order,
                    "name": step.name,
                    "production_line_id": step.production_line_id,
                    "is_used": True,
                },
            )

    def append_line_step(
        self,
        session: Session,
        formula_id: int,
        production_line_id: int,
        workspace_id: int,
        user_id: int,
        name: Optional[str] = None,
        factory_id: Optional[int] = None,
    ) -> ProductionFormulaStage:
        """Add a production line to this recipe's private path."""
        formula = self.formula_dao.get_by_id_and_workspace(
            session, id=formula_id, workspace_id=workspace_id
        )
        if not formula:
            raise ValueError(f"Production formula {formula_id} not found")
        if formula.route_id is None:
            if factory_id is None:
                raise ValueError("factory_id is required to start this recipe's path")
            route = self._ensure_private_route(
                session, formula=formula, factory_id=factory_id, workspace_id=workspace_id, user_id=user_id
            )
        else:
            route = self._require_route(session, formula.route_id, workspace_id)
            self._assert_route_exclusive_to_formula(
                session, route_id=route.id, formula_id=formula.id, workspace_id=workspace_id
            )
        line = production_line_dao.get_by_id_and_workspace(
            session, id=production_line_id, workspace_id=workspace_id
        )
        if not line or line.factory_id != route.factory_id:
            raise ValueError("Production line is not in this route's factory")
        from app.utils.production_line_machines import assert_production_line_assignable

        assert_production_line_assignable(
            session,
            line_id=line.id,
            workspace_id=workspace_id,
        )
        steps = production_route_step_dao.get_by_route(
            session, route_id=route.id, workspace_id=workspace_id
        )
        next_order = max((step.step_order for step in steps), default=0) + 1
        step_name = (name or "").strip() or line.name
        step = production_route_step_dao.create(
            session,
            obj_in={
                "workspace_id": workspace_id,
                "route_id": route.id,
                "step_order": next_order,
                "production_line_id": line.id,
                "name": step_name,
            },
        )
        return self.formula_stage_dao.create(
            session,
            obj_in={
                "workspace_id": workspace_id,
                "formula_id": formula.id,
                "route_step_id": step.id,
                "stage_order": next_order,
                "name": step_name,
                "production_line_id": line.id,
                "is_used": True,
            },
        )

    def _copy_route_for_formula(
        self,
        session: Session,
        formula: ProductionFormula,
        route: ProductionRoute,
        workspace_id: int,
        user_id: int,
    ) -> ProductionRoute:
        copied = production_route_dao.create(
            session,
            obj_in={
                "workspace_id": workspace_id,
                "factory_id": route.factory_id,
                "name": f"{route.name} copy",
                "description": route.description,
                "is_active": True,
                "created_by": user_id,
            },
        )
        steps = production_route_step_dao.get_by_route(
            session, route_id=route.id, workspace_id=workspace_id
        )
        id_map: Dict[int, int] = {}
        for step in sorted(steps, key=lambda row: row.step_order):
            new_step = production_route_step_dao.create(
                session,
                obj_in={
                    "workspace_id": workspace_id,
                    "route_id": copied.id,
                    "step_order": step.step_order,
                    "production_line_id": step.production_line_id,
                    "name": step.name,
                    "notes": step.notes,
                },
            )
            id_map[step.id] = new_step.id
        for stage in self.formula_stage_dao.get_by_formula(
            session, formula_id=formula.id, workspace_id=workspace_id
        ):
            if stage.route_step_id in id_map:
                stage.route_step_id = id_map[stage.route_step_id]
        self.formula_dao.update(session, db_obj=formula, obj_in={"route_id": copied.id})
        session.flush()
        return copied

    def _used_stages(self, stages: List[ProductionFormulaStage]) -> List[ProductionFormulaStage]:
        return [stage for stage in stages if getattr(stage, "is_used", True)]

    def _delete_route_fills(self, session: Session, route_id: int, workspace_id: int) -> None:
        steps = production_route_step_dao.get_by_route(
            session, route_id=route_id, workspace_id=workspace_id
        )
        for step in steps:
            self._unlink_stage_from_step(session, step)
            production_route_step_dao.remove(session, id=step.id)
        session.flush()

    def _unlink_stage_from_step(self, session: Session, step: ProductionRouteStep) -> None:
        stages = (
            session.query(ProductionFormulaStage)
            .filter(ProductionFormulaStage.route_step_id == step.id)
            .all()
        )
        for stage in stages:
            stage.route_step_id = None
        if stages:
            session.flush()

    def _reapply_handoff_around_stage(
        self, session: Session, stage: ProductionFormulaStage, workspace_id: int
    ) -> None:
        stages = self._sorted_formula_stages(
            session, formula_id=stage.formula_id, workspace_id=workspace_id
        )
        used = self._used_stages(stages)
        for index, row in enumerate(used):
            if index == 0:
                continue
            outputs = self.formula_stage_item_dao.get_by_stage(
                session,
                formula_stage_id=used[index - 1].id,
                workspace_id=workspace_id,
                item_role="output",
            )
            self._reconcile_handoff_inputs_from_outputs(
                session,
                target_stage=row,
                source_outputs=outputs,
                workspace_id=workspace_id,
            )

    def _get_stage_for_formula(
        self, session: Session, *, formula_id: int, stage_id: int, workspace_id: int
    ) -> ProductionFormulaStage:
        stage = self.formula_stage_dao.get_by_id_and_workspace(
            session, id=stage_id, workspace_id=workspace_id
        )
        if not stage or stage.formula_id != formula_id:
            raise ValueError(f"Formula stage {stage_id} not found for formula {formula_id}")
        return stage

    # ─── Formula stage item CRUD ─────────────────────────────────────

    def get_formula_stage_items(
        self,
        session: Session,
        formula_id: int,
        stage_id: int,
        workspace_id: int,
        item_role: Optional[str] = None,
    ) -> List[ProductionFormulaStageItem]:
        self._get_stage_for_formula(
            session, formula_id=formula_id, stage_id=stage_id, workspace_id=workspace_id
        )
        if item_role is not None and item_role not in self.VALID_ITEM_ROLES:
            raise ValueError(
                f"Invalid item_role '{item_role}'. Must be one of: {', '.join(self.VALID_ITEM_ROLES)}"
            )
        return self.formula_stage_item_dao.get_by_stage(
            session, formula_stage_id=stage_id, workspace_id=workspace_id, item_role=item_role
        )

    def get_all_formula_stage_items(
        self, session: Session, formula_id: int, workspace_id: int
    ) -> List[ProductionFormulaStageItem]:
        formula = self.formula_dao.get_by_id_and_workspace(
            session, id=formula_id, workspace_id=workspace_id
        )
        if not formula:
            raise ValueError(f"Production formula {formula_id} not found")
        return self.formula_stage_item_dao.get_by_formula(
            session, formula_id=formula_id, workspace_id=workspace_id
        )

    def _sorted_formula_stages(
        self, session: Session, *, formula_id: int, workspace_id: int
    ) -> List[ProductionFormulaStage]:
        stages = self.formula_stage_dao.get_by_formula(
            session, formula_id=formula_id, workspace_id=workspace_id
        )
        return sorted(stages, key=lambda row: row.stage_order)

    def _reconcile_handoff_inputs_from_outputs(
        self,
        session: Session,
        *,
        target_stage: ProductionFormulaStage,
        source_outputs: List[ProductionFormulaStageItem],
        workspace_id: int,
    ) -> None:
        """Mirror prior-step outputs onto the next step's inputs (add/remove only; keep edited qty)."""
        target_inputs = self.formula_stage_item_dao.get_by_stage(
            session,
            formula_stage_id=target_stage.id,
            workspace_id=workspace_id,
            item_role="input",
        )
        output_by_item = {row.item_id: row for row in source_outputs}

        if not source_outputs:
            for row in list(target_inputs):
                self.formula_stage_item_dao.remove(session, id=row.id)
            return

        existing_by_item = {row.item_id: row for row in target_inputs}
        for output_row in source_outputs:
            if output_row.item_id in existing_by_item:
                continue
            self.formula_stage_item_dao.create(
                session,
                obj_in={
                    "workspace_id": workspace_id,
                    "formula_stage_id": target_stage.id,
                    "item_id": output_row.item_id,
                    "item_role": "input",
                    "quantity": int(output_row.quantity),
                    "unit": output_row.unit,
                    "is_optional": output_row.is_optional,
                    "tolerance_percentage": output_row.tolerance_percentage,
                },
            )

        for row in list(target_inputs):
            if row.item_id not in output_by_item:
                self.formula_stage_item_dao.remove(session, id=row.id)

    def _apply_output_handoff_to_next_stage(
        self, session: Session, *, formula_stage_id: int, workspace_id: int
    ) -> None:
        stage = self.formula_stage_dao.get_by_id_and_workspace(
            session, id=formula_stage_id, workspace_id=workspace_id
        )
        if not stage:
            return
        stages = self._sorted_formula_stages(
            session, formula_id=stage.formula_id, workspace_id=workspace_id
        )
        used = self._used_stages(stages)
        index = next((i for i, row in enumerate(used) if row.id == stage.id), None)
        if index is None or index >= len(used) - 1:
            return
        next_stage = used[index + 1]
        source_outputs = self.formula_stage_item_dao.get_by_stage(
            session,
            formula_stage_id=formula_stage_id,
            workspace_id=workspace_id,
            item_role="output",
        )
        self._reconcile_handoff_inputs_from_outputs(
            session,
            target_stage=next_stage,
            source_outputs=source_outputs,
            workspace_id=workspace_id,
        )

    def ensure_input_handoff_from_previous_stage(
        self,
        session: Session,
        formula_id: int,
        stage_id: int,
        workspace_id: int,
    ) -> None:
        stage = self._get_stage_for_formula(
            session, formula_id=formula_id, stage_id=stage_id, workspace_id=workspace_id
        )
        stages = self._sorted_formula_stages(
            session, formula_id=formula_id, workspace_id=workspace_id
        )
        used = self._used_stages(stages)
        index = next((i for i, row in enumerate(used) if row.id == stage.id), None)
        if index is None or index == 0:
            return
        previous_stage = used[index - 1]
        source_outputs = self.formula_stage_item_dao.get_by_stage(
            session,
            formula_stage_id=previous_stage.id,
            workspace_id=workspace_id,
            item_role="output",
        )
        if not source_outputs:
            return
        self._reconcile_handoff_inputs_from_outputs(
            session,
            target_stage=stage,
            source_outputs=source_outputs,
            workspace_id=workspace_id,
        )

    def _validate_stage_input_add(
        self,
        session: Session,
        *,
        formula_id: int,
        stage: ProductionFormulaStage,
        workspace_id: int,
    ) -> None:
        stages = self._sorted_formula_stages(
            session, formula_id=formula_id, workspace_id=workspace_id
        )
        index = next((i for i, row in enumerate(stages) if row.id == stage.id), None)
        if index is None or index == 0:
            return
        previous_stage = stages[index - 1]
        previous_outputs = self.formula_stage_item_dao.get_by_stage(
            session,
            formula_stage_id=previous_stage.id,
            workspace_id=workspace_id,
            item_role="output",
        )
        if not previous_outputs:
            raise ValueError(
                "Add outputs on the previous step before defining inputs on this step."
            )

    def add_formula_stage_item(
        self,
        session: Session,
        formula_id: int,
        stage_id: int,
        item_data: ProductionFormulaStageItemCreate,
        workspace_id: int,
        user_id: int | None = None,
    ) -> ProductionFormulaStageItem:
        stage = self._get_stage_for_formula(
            session, formula_id=formula_id, stage_id=stage_id, workspace_id=workspace_id
        )
        if item_data.formula_stage_id != stage_id:
            raise ValueError("formula_stage_id does not match path stage_id")

        item = item_dao.get(session, id=item_data.item_id)
        if not item or item.workspace_id != workspace_id:
            raise ValueError(f"Item {item_data.item_id} not found")

        if item_data.item_role not in self.VALID_ITEM_ROLES:
            raise ValueError(
                f"Invalid item_role '{item_data.item_role}'. Must be one of: {', '.join(self.VALID_ITEM_ROLES)}"
            )

        if item_data.item_role == "input":
            self._validate_stage_input_add(
                session, formula_id=formula_id, stage=stage, workspace_id=workspace_id
            )

        item_dict = item_data.model_dump()
        item_dict["workspace_id"] = workspace_id
        created = self.formula_stage_item_dao.create(session, obj_in=item_dict)
        if user_id is not None:
            from app.managers.item_manager import item_manager

            item_manager.ensure_production_role_catalog_tag(
                session,
                item_id=item_data.item_id,
                item_role=item_data.item_role,
                workspace_id=workspace_id,
                user_id=user_id,
            )
        self._sync_stage_expected_output_from_materials(
            session, formula_stage_id=stage_id, workspace_id=workspace_id
        )
        if item_data.item_role == "output":
            self._apply_output_handoff_to_next_stage(
                session, formula_stage_id=stage_id, workspace_id=workspace_id
            )
        return created

    @staticmethod
    def _pick_primary_output_stage_item(
        output_rows: List[ProductionFormulaStageItem],
    ) -> Optional[ProductionFormulaStageItem]:
        if not output_rows:
            return None
        return min(output_rows, key=lambda row: (-int(row.quantity), int(row.id)))

    def _sync_stage_expected_output_from_materials(
        self,
        session: Session,
        *,
        formula_stage_id: int,
        workspace_id: int,
    ) -> None:
        stage = self.formula_stage_dao.get_by_id_and_workspace(
            session, id=formula_stage_id, workspace_id=workspace_id
        )
        if not stage:
            return
        output_rows = self.formula_stage_item_dao.get_by_stage(
            session,
            formula_stage_id=formula_stage_id,
            workspace_id=workspace_id,
            item_role="output",
        )
        primary = self._pick_primary_output_stage_item(output_rows)
        self.formula_stage_dao.update(
            session,
            db_obj=stage,
            obj_in={
                "expected_output_quantity": primary.quantity if primary else None,
                "expected_output_item_id": primary.item_id if primary else None,
            },
        )

    def update_formula_stage_item(
        self,
        session: Session,
        stage_item_id: int,
        item_data: ProductionFormulaStageItemUpdate,
        workspace_id: int,
    ) -> ProductionFormulaStageItem:
        stage_item = self.formula_stage_item_dao.get_by_id_and_workspace(
            session, id=stage_item_id, workspace_id=workspace_id
        )
        if not stage_item:
            raise ValueError(f"Formula stage item {stage_item_id} not found")

        prior_role = stage_item.item_role
        update_dict = item_data.model_dump(exclude_unset=True, exclude_none=True)
        if "item_role" in update_dict and update_dict["item_role"] not in self.VALID_ITEM_ROLES:
            raise ValueError(
                f"Invalid item_role '{update_dict['item_role']}'. Must be one of: {', '.join(self.VALID_ITEM_ROLES)}"
            )
        updated = self.formula_stage_item_dao.update(session, db_obj=stage_item, obj_in=update_dict)
        self._sync_stage_expected_output_from_materials(
            session, formula_stage_id=updated.formula_stage_id, workspace_id=workspace_id
        )
        if prior_role == "output" or updated.item_role == "output":
            self._apply_output_handoff_to_next_stage(
                session, formula_stage_id=updated.formula_stage_id, workspace_id=workspace_id
            )
        return updated

    def remove_formula_stage_item(
        self, session: Session, stage_item_id: int, workspace_id: int
    ) -> ProductionFormulaStageItem:
        stage_item = self.formula_stage_item_dao.get_by_id_and_workspace(
            session, id=stage_item_id, workspace_id=workspace_id
        )
        if not stage_item:
            raise ValueError(f"Formula stage item {stage_item_id} not found")
        stage_id = stage_item.formula_stage_id
        was_output = stage_item.item_role == "output"
        removed = self.formula_stage_item_dao.remove(session, id=stage_item_id)
        self._sync_stage_expected_output_from_materials(
            session, formula_stage_id=stage_id, workspace_id=workspace_id
        )
        if was_output:
            self._apply_output_handoff_to_next_stage(
                session, formula_stage_id=stage_id, workspace_id=workspace_id
            )
        return removed

    # ─── Formula stage parameters (conditions) ───────────────────────

    def get_formula_stage_parameters(
        self,
        session: Session,
        formula_id: int,
        stage_id: int,
        workspace_id: int,
    ) -> List[ProductionFormulaStageParameter]:
        self._get_stage_for_formula(
            session, formula_id=formula_id, stage_id=stage_id, workspace_id=workspace_id
        )
        return self.formula_stage_parameter_dao.get_by_stage(
            session, formula_stage_id=stage_id, workspace_id=workspace_id
        )

    def get_all_formula_stage_parameters(
        self, session: Session, formula_id: int, workspace_id: int
    ) -> List[ProductionFormulaStageParameter]:
        formula = self.formula_dao.get_by_id_and_workspace(
            session, id=formula_id, workspace_id=workspace_id
        )
        if not formula:
            raise ValueError(f"Production formula {formula_id} not found")
        return self.formula_stage_parameter_dao.get_by_formula(
            session, formula_id=formula_id, workspace_id=workspace_id
        )

    def add_formula_stage_parameter(
        self,
        session: Session,
        formula_id: int,
        stage_id: int,
        param_data: ProductionFormulaStageParameterCreate,
        workspace_id: int,
    ) -> ProductionFormulaStageParameter:
        self._get_stage_for_formula(
            session, formula_id=formula_id, stage_id=stage_id, workspace_id=workspace_id
        )
        if param_data.formula_stage_id != stage_id:
            raise ValueError("formula_stage_id does not match path stage_id")
        label = param_data.label.strip()
        if not label:
            raise ValueError("Condition label is required")
        if self.formula_stage_parameter_dao.label_exists_on_stage(
            session, formula_stage_id=stage_id, workspace_id=workspace_id, label=label
        ):
            raise ValueError(f"Condition label '{label}' already exists on this step")

        param_dict = param_data.model_dump()
        param_dict["workspace_id"] = workspace_id
        param_dict["label"] = label
        param_dict["planned_value"] = param_data.planned_value.strip()
        if not param_dict["planned_value"]:
            raise ValueError("Planned value is required")
        param_dict["planned_value_numeric"] = optional_numeric_from_text(param_dict["planned_value"])
        return self.formula_stage_parameter_dao.create(session, obj_in=param_dict)

    def update_formula_stage_parameter(
        self,
        session: Session,
        parameter_id: int,
        param_data: ProductionFormulaStageParameterUpdate,
        workspace_id: int,
    ) -> ProductionFormulaStageParameter:
        param = self.formula_stage_parameter_dao.get_by_id_and_workspace(
            session, id=parameter_id, workspace_id=workspace_id
        )
        if not param:
            raise ValueError(f"Formula stage parameter {parameter_id} not found")

        update_dict = param_data.model_dump(exclude_unset=True)
        if "label" in update_dict and update_dict["label"] is not None:
            update_dict["label"] = update_dict["label"].strip()
            if not update_dict["label"]:
                raise ValueError("Condition label is required")
            if self.formula_stage_parameter_dao.label_exists_on_stage(
                session,
                formula_stage_id=param.formula_stage_id,
                workspace_id=workspace_id,
                label=update_dict["label"],
                exclude_id=param.id,
            ):
                raise ValueError(
                    f"Condition label '{update_dict['label']}' already exists on this step"
                )
        if "planned_value" in update_dict and update_dict["planned_value"] is not None:
            update_dict["planned_value"] = update_dict["planned_value"].strip()
            if not update_dict["planned_value"]:
                raise ValueError("Planned value is required")
            update_dict["planned_value_numeric"] = optional_numeric_from_text(
                update_dict["planned_value"]
            )
        return self.formula_stage_parameter_dao.update(session, db_obj=param, obj_in=update_dict)

    def remove_formula_stage_parameter(
        self, session: Session, parameter_id: int, workspace_id: int
    ) -> ProductionFormulaStageParameter:
        param = self.formula_stage_parameter_dao.get_by_id_and_workspace(
            session, id=parameter_id, workspace_id=workspace_id
        )
        if not param:
            raise ValueError(f"Formula stage parameter {parameter_id} not found")
        return self.formula_stage_parameter_dao.remove(session, id=parameter_id)

    def _clear_other_defaults(
        self,
        session: Session,
        workspace_id: int,
        exclude_id: Optional[int] = None
    ) -> None:
        """Clear is_default flag on all other formulas in the workspace."""
        default_formulas = self.formula_dao.get_default_formulas(
            session, workspace_id=workspace_id
        )
        for f in default_formulas:
            if exclude_id and f.id == exclude_id:
                continue
            if f.is_default:
                self.formula_dao.update(session, db_obj=f, obj_in={'is_default': False})


# Singleton instance
production_formula_manager = ProductionFormulaManager()
