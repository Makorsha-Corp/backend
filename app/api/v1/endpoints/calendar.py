"""Calendar API — unified dated events feed."""
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_workspace, get_db
from app.models.workspace import Workspace
from app.schemas.calendar import CalendarCategory, CalendarEventsResponse
from app.services.calendar_service import calendar_service

router = APIRouter()


@router.get(
    "/events",
    response_model=CalendarEventsResponse,
    status_code=status.HTTP_200_OK,
    summary="List calendar events in a date range",
)
def list_calendar_events(
    start: date = Query(..., description="Range start (inclusive), YYYY-MM-DD"),
    end: date = Query(..., description="Range end (inclusive), YYYY-MM-DD"),
    types: Optional[List[CalendarCategory]] = Query(
        None,
        description="Optional category filter; omit for all categories",
    ),
    db: Session = Depends(get_db),
    workspace: Workspace = Depends(get_current_workspace),
):
    try:
        events = calendar_service.get_events(
            db,
            workspace_id=workspace.id,
            start=start,
            end=end,
            types=types,
        )
        return CalendarEventsResponse(events=events, total=len(events))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Internal server error") from exc
