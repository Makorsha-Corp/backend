"""Production route service — owns commit/rollback."""
from typing import List, Optional

from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, NotFoundError
from app.managers.production_route_manager import production_route_manager
from app.models.production_route import ProductionRoute, ProductionRouteStep
from app.schemas.production_route import (
    ProductionRouteCreate,
    ProductionRouteStepCreate,
    ProductionRouteStepUpdate,
    ProductionRouteUpdate,
)
from app.services.base_service import BaseService


class ProductionRouteService(BaseService):
    def create_route(self, db: Session, data: ProductionRouteCreate, workspace_id: int, user_id: int) -> ProductionRoute:
        return self._run(db, lambda: production_route_manager.create_route(db, data, workspace_id, user_id))

    def update_route(
        self, db: Session, route_id: int, data: ProductionRouteUpdate, workspace_id: int, user_id: int
    ) -> ProductionRoute:
        return self._run(db, lambda: production_route_manager.update_route(db, route_id, data, workspace_id, user_id))

    def get_route(self, db: Session, route_id: int, workspace_id: int) -> ProductionRoute:
        route = production_route_manager.get_route(db, route_id, workspace_id)
        if not route:
            raise NotFoundError(f"Production route {route_id} not found")
        return route

    def get_routes(
        self, db: Session, workspace_id: int, factory_id: Optional[int] = None, skip: int = 0, limit: int = 100
    ) -> List[ProductionRoute]:
        return production_route_manager.get_routes(db, workspace_id, factory_id, skip, limit)

    def delete_route(self, db: Session, route_id: int, workspace_id: int) -> ProductionRoute:
        return self._run(db, lambda: production_route_manager.delete_route(db, route_id, workspace_id))

    def get_steps(self, db: Session, route_id: int, workspace_id: int) -> List[ProductionRouteStep]:
        try:
            return production_route_manager.get_steps(db, route_id, workspace_id)
        except ValueError as exc:
            raise NotFoundError(str(exc)) from exc

    def add_step(
        self, db: Session, route_id: int, data: ProductionRouteStepCreate, workspace_id: int
    ) -> ProductionRouteStep:
        return self._run(db, lambda: production_route_manager.add_step(db, route_id, data, workspace_id))

    def update_step(
        self, db: Session, step_id: int, data: ProductionRouteStepUpdate, workspace_id: int
    ) -> ProductionRouteStep:
        return self._run(db, lambda: production_route_manager.update_step(db, step_id, data, workspace_id))

    def delete_step(self, db: Session, step_id: int, workspace_id: int) -> ProductionRouteStep:
        return self._run(db, lambda: production_route_manager.delete_step(db, step_id, workspace_id))

    def _run(self, db: Session, action):
        try:
            result = action()
            self._commit_transaction(db)
            db.refresh(result)
            return result
        except ValueError as exc:
            self._rollback_transaction(db)
            message = str(exc)
            if message.endswith("not found"):
                raise NotFoundError(message) from exc
            raise BusinessRuleError(message) from exc
        except Exception:
            self._rollback_transaction(db)
            raise


production_route_service = ProductionRouteService()
