"""Production route business rules. Does not commit."""
from typing import List, Optional

from sqlalchemy.orm import Session

from app.dao.production_line import production_line_dao
from app.dao.production_line_machine import production_line_machine_dao
from app.dao.production_route import production_route_dao, production_route_step_dao
from app.dao.machine import machine_dao
from app.models.production_batch import ProductionBatch
from app.models.production_batch_stage_log import ProductionBatchStageLog
from app.models.production_formula import ProductionFormula
from app.models.production_formula_stage import ProductionFormulaStage
from app.models.production_route import ProductionRoute, ProductionRouteStep
from app.schemas.production_route import (
    ProductionRouteCreate,
    ProductionRouteStepCreate,
    ProductionRouteStepUpdate,
    ProductionRouteUpdate,
)
from app.utils.production_line_machines import assert_production_line_assignable


class ProductionRouteManager:
    OPEN_BATCH_STATUSES = ("draft", "in_progress")

    def create_route(
        self, session: Session, data: ProductionRouteCreate, workspace_id: int, user_id: int
    ) -> ProductionRoute:
        self._require_factory(session, data.factory_id, workspace_id)
        payload = data.model_dump()
        payload.pop("formula_id", None)
        payload["workspace_id"] = workspace_id
        payload["created_by"] = user_id
        return production_route_dao.create(session, obj_in=payload)

    def update_route(
        self, session: Session, route_id: int, data: ProductionRouteUpdate, workspace_id: int, user_id: int
    ) -> ProductionRoute:
        route = self._require_route(session, route_id, workspace_id)
        update = data.model_dump(exclude_unset=True)
        update.pop("formula_id", None)
        update["updated_by"] = user_id
        return production_route_dao.update(session, db_obj=route, obj_in=update)

    def get_route(self, session: Session, route_id: int, workspace_id: int) -> Optional[ProductionRoute]:
        return production_route_dao.get_by_id_and_workspace(session, id=route_id, workspace_id=workspace_id)

    def get_routes(
        self, session: Session, workspace_id: int, factory_id: Optional[int] = None, skip: int = 0, limit: int = 100
    ) -> List[ProductionRoute]:
        return production_route_dao.get_by_workspace(
            session, workspace_id=workspace_id, factory_id=factory_id, skip=skip, limit=limit
        )

    def delete_route(self, session: Session, route_id: int, workspace_id: int) -> ProductionRoute:
        route = self._require_route(session, route_id, workspace_id)
        self._guard_route_in_use(session, route)
        return production_route_dao.remove(session, id=route.id)

    def get_steps(self, session: Session, route_id: int, workspace_id: int) -> List[ProductionRouteStep]:
        self._require_route(session, route_id, workspace_id)
        return production_route_step_dao.get_by_route(session, route_id=route_id, workspace_id=workspace_id)

    def add_step(
        self, session: Session, route_id: int, data: ProductionRouteStepCreate, workspace_id: int
    ) -> ProductionRouteStep:
        route = self._require_route(session, route_id, workspace_id)
        if data.production_line_id is None:
            raise ValueError("Production line is required")
        line = self._require_line_for_route(session, data.production_line_id, workspace_id, route.factory_id)
        siblings = production_route_step_dao.get_by_route(session, route_id=route.id, workspace_id=workspace_id)
        if any(step.step_order == data.step_order for step in siblings):
            raise ValueError(f"Step order {data.step_order} already exists on this route")
        payload = data.model_dump()
        payload.pop("machine_id", None)
        payload.pop("formula_stage_id", None)
        payload["name"] = self._default_step_name(data.name, line.name, None)
        payload["workspace_id"] = workspace_id
        payload["route_id"] = route.id
        return production_route_step_dao.create(session, obj_in=payload)

    def update_step(
        self, session: Session, step_id: int, data: ProductionRouteStepUpdate, workspace_id: int
    ) -> ProductionRouteStep:
        step = production_route_step_dao.get_by_id_and_workspace(session, id=step_id, workspace_id=workspace_id)
        if not step:
            raise ValueError(f"Route step {step_id} not found")
        route = self._require_route(session, step.route_id, workspace_id)
        update = data.model_dump(exclude_unset=True)
        update.pop("machine_id", None)
        update.pop("formula_stage_id", None)
        if "production_line_id" in update and update["production_line_id"] is None:
            raise ValueError("Production line is required")
        line_id = update.get("production_line_id", step.production_line_id)
        if line_id is not None and "production_line_id" in update:
            line = self._require_line_for_route(session, line_id, workspace_id, route.factory_id)
            if "name" not in update:
                update["name"] = self._default_step_name(None, line.name, None)
        if "step_order" in update and update["step_order"] != step.step_order:
            siblings = production_route_step_dao.get_by_route(
                session, route_id=step.route_id, workspace_id=workspace_id
            )
            if any(other.id != step.id and other.step_order == update["step_order"] for other in siblings):
                raise ValueError(f"Step order {update['step_order']} already exists on this route")
        if not update:
            return step
        updated = production_route_step_dao.update(session, db_obj=step, obj_in=update)
        return updated

    def delete_step(self, session: Session, step_id: int, workspace_id: int) -> ProductionRouteStep:
        step = production_route_step_dao.get_by_id_and_workspace(session, id=step_id, workspace_id=workspace_id)
        if not step:
            raise ValueError(f"Route step {step_id} not found")
        self._guard_step_in_use(session, step, workspace_id)
        return production_route_step_dao.remove(session, id=step.id)

    def _require_route(self, session: Session, route_id: int, workspace_id: int) -> ProductionRoute:
        route = production_route_dao.get_by_id_and_workspace(session, id=route_id, workspace_id=workspace_id)
        if not route:
            raise ValueError(f"Production route {route_id} not found")
        return route

    def _require_factory(self, session: Session, factory_id: int, workspace_id: int) -> None:
        from app.models.factory import Factory

        factory = (
            session.query(Factory)
            .filter(Factory.id == factory_id, Factory.workspace_id == workspace_id)
            .first()
        )
        if not factory:
            raise ValueError(f"Factory {factory_id} not found")

    def _require_line_for_route(self, session: Session, line_id: int, workspace_id: int, factory_id: int):
        line = production_line_dao.get_by_id_and_workspace(session, id=line_id, workspace_id=workspace_id)
        if not line:
            raise ValueError(f"Production line {line_id} not found")
        if line.factory_id != factory_id:
            raise ValueError(f"Production line {line.name} is not in this route's factory")
        return line

    def _validate_step_machine(
        self,
        session: Session,
        *,
        line_id: int,
        machine_id: Optional[int],
        workspace_id: int,
        factory_id: int,
    ):
        if machine_id is None:
            return None
        machine = machine_dao.get(session, id=machine_id)
        if not machine or machine.workspace_id != workspace_id or getattr(machine, "is_deleted", False):
            raise ValueError(f"Machine {machine_id} not found")
        if machine.factory_id != factory_id:
            raise ValueError(f"Machine {machine.name} is not in this route's factory")
        assigned = production_line_machine_dao.get_machine_ids_for_line(
            session, production_line_id=line_id, workspace_id=workspace_id
        )
        if machine_id not in assigned:
            line = production_line_dao.get(session, id=line_id)
            if not line or line.machine_id != machine_id:
                raise ValueError(f"Machine {machine.name} is not assigned to this station")
        return machine

    @staticmethod
    def _default_step_name(custom_name: Optional[str], line_name: str, machine) -> str:
        if custom_name and custom_name.strip():
            return custom_name.strip()
        if machine is not None:
            return f"{line_name} · {machine.name}"
        return line_name

    def _guard_route_in_use(self, session: Session, route: ProductionRoute) -> None:
        formulas = (
            session.query(ProductionFormula)
            .filter(
                ProductionFormula.workspace_id == route.workspace_id,
                ProductionFormula.route_id == route.id,
                ProductionFormula.is_active.is_(True),
            )
            .all()
        )
        batches = (
            session.query(ProductionBatch)
            .filter(
                ProductionBatch.workspace_id == route.workspace_id,
                ProductionBatch.route_id == route.id,
                ProductionBatch.status.in_(self.OPEN_BATCH_STATUSES),
            )
            .all()
        )
        if formulas or batches:
            names = [f"formula {row.name}" for row in formulas] + [f"batch {row.batch_number}" for row in batches]
            raise ValueError(f"Cannot delete route while in use by {', '.join(names)}")

    def _guard_step_in_use(self, session: Session, step: ProductionRouteStep, workspace_id: int) -> None:
        formulas = (
            session.query(ProductionFormula)
            .join(ProductionFormulaStage, ProductionFormulaStage.formula_id == ProductionFormula.id)
            .filter(
                ProductionFormulaStage.route_step_id == step.id,
                ProductionFormula.workspace_id == workspace_id,
                ProductionFormula.is_active.is_(True),
            )
            .all()
        )
        batches = (
            session.query(ProductionBatch)
            .join(ProductionBatchStageLog, ProductionBatchStageLog.batch_id == ProductionBatch.id)
            .filter(
                ProductionBatchStageLog.route_step_id == step.id,
                ProductionBatch.workspace_id == workspace_id,
                ProductionBatch.status.in_(self.OPEN_BATCH_STATUSES),
            )
            .all()
        )
        if formulas or batches:
            names = [f"formula {row.name}" for row in formulas] + [f"batch {row.batch_number}" for row in batches]
            raise ValueError(f"Cannot delete step while in use by {', '.join(names)}")


production_route_manager = ProductionRouteManager()
