"""Notification endpoints — /me/notifications/"""
from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_active_user, get_current_workspace
from app.models.profile import Profile
from app.models.workspace import Workspace
from app.schemas.notification import NotificationListResponse, MarkReadRequest
from app.services.notification_service import notification_service
from app.services.notification_stream import notification_event_generator

router = APIRouter()


@router.get("/", response_model=NotificationListResponse, status_code=status.HTTP_200_OK)
def list_notifications(
    unread_only:  bool    = Query(False),
    skip:         int     = Query(0, ge=0),
    limit:        int     = Query(50, ge=1, le=200),
    db:           Session = Depends(get_db),
    workspace:    Workspace = Depends(get_current_workspace),
    current_user: Profile   = Depends(get_current_active_user),
):
    items, total, unread_count = notification_service.list_for_user(
        db, workspace.id, current_user.id, unread_only, skip, limit
    )
    return NotificationListResponse(items=items, total=total, unread_count=unread_count)


@router.get("/stream", status_code=status.HTTP_200_OK)
def stream_notifications(
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
):
    return StreamingResponse(
        notification_event_generator(current_user.id, workspace.id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/read/", status_code=status.HTTP_200_OK)
def mark_read(
    data:         MarkReadRequest = ...,
    db:           Session         = Depends(get_db),
    workspace:    Workspace       = Depends(get_current_workspace),
    current_user: Profile         = Depends(get_current_active_user),
):
    count = notification_service.mark_read(db, workspace.id, current_user.id, data)
    return {"marked_read": count}
