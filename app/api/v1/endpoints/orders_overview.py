"""Orders overview aggregation endpoints"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_workspace
from app.models.workspace import Workspace
from app.schemas.orders_overview import OrdersOverviewStatsResponse
from app.services.orders_overview_service import orders_overview_service

router = APIRouter()


@router.get(
    '/stats',
    response_model=OrdersOverviewStatsResponse,
    summary='Orders overview leaderboards',
    description='Aggregated top items, vendors, customers, and expense categories for a date range.',
)
def get_orders_overview_stats(
    from_date: date = Query(..., alias='from_date'),
    to_date: date = Query(..., alias='to_date'),
    factory_id: Optional[int] = Query(None),
    limit: int = Query(5, ge=1, le=10),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    return orders_overview_service.get_stats(
        db,
        workspace_id=workspace.id,
        from_date=from_date,
        to_date=to_date,
        factory_id=factory_id,
        limit=limit,
    )
