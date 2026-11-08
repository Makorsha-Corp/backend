"""Production route DAO."""
from typing import List, Optional

from sqlalchemy.orm import Session

from app.dao.base import BaseDAO
from app.models.production_route import ProductionRoute, ProductionRouteStep
from app.schemas.production_route import (
    ProductionRouteCreate,
    ProductionRouteStepCreate,
    ProductionRouteStepUpdate,
    ProductionRouteUpdate,
)


class ProductionRouteDAO(BaseDAO[ProductionRoute, ProductionRouteCreate, ProductionRouteUpdate]):
    def get_by_workspace(
        self, db: Session, *, workspace_id: int, factory_id: Optional[int] = None, skip: int = 0, limit: int = 100
    ) -> List[ProductionRoute]:
        query = db.query(ProductionRoute).filter(ProductionRoute.workspace_id == workspace_id)
        if factory_id is not None:
            query = query.filter(ProductionRoute.factory_id == factory_id)
        return query.order_by(ProductionRoute.name.asc()).offset(skip).limit(limit).all()

    def get_by_id_and_workspace(
        self, db: Session, *, id: int, workspace_id: int
    ) -> Optional[ProductionRoute]:
        return (
            db.query(ProductionRoute)
            .filter(ProductionRoute.id == id, ProductionRoute.workspace_id == workspace_id)
            .first()
        )


class ProductionRouteStepDAO(BaseDAO[ProductionRouteStep, ProductionRouteStepCreate, ProductionRouteStepUpdate]):
    def get_by_route(
        self, db: Session, *, route_id: int, workspace_id: int
    ) -> List[ProductionRouteStep]:
        return (
            db.query(ProductionRouteStep)
            .filter(
                ProductionRouteStep.route_id == route_id,
                ProductionRouteStep.workspace_id == workspace_id,
            )
            .order_by(ProductionRouteStep.step_order.asc(), ProductionRouteStep.id.asc())
            .all()
        )

    def get_by_id_and_workspace(
        self, db: Session, *, id: int, workspace_id: int
    ) -> Optional[ProductionRouteStep]:
        return (
            db.query(ProductionRouteStep)
            .filter(ProductionRouteStep.id == id, ProductionRouteStep.workspace_id == workspace_id)
            .first()
        )


production_route_dao = ProductionRouteDAO(ProductionRoute)
production_route_step_dao = ProductionRouteStepDAO(ProductionRouteStep)
