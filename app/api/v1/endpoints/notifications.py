"""Notification endpoints — /me/notifications/"""
from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_active_user, get_current_workspace
from app.models.profile import Profile
from app.models.workspace import Workspace
from app.schemas.notification import (
    MarkReadRequest,
    NotificationActor,
    NotificationListResponse,
    NotificationResponse,
)
from app.services.notification_service import notification_service
from app.services.notification_stream import notification_event_generator
from app.utils.notification_entity_label import resolve_notification_entity_label

router = APIRouter()


def _to_notification_response(
    db: Session,
    workspace_id: int,
    notification,
) -> NotificationResponse:
    actor = None
    if notification.actor is not None:
        actor = NotificationActor.model_validate(notification.actor)

    return NotificationResponse(
        id=notification.id,
        workspace_id=notification.workspace_id,
        notification_type=notification.notification_type,
        entity_type=notification.entity_type,
        entity_id=notification.entity_id,
        entity_label=resolve_notification_entity_label(
            db,
            workspace_id=workspace_id,
            entity_type=notification.entity_type,
            entity_id=notification.entity_id,
        ),
        source_type=notification.source_type,
        source_id=notification.source_id,
        preview=notification.preview,
        is_read=notification.is_read,
        read_at=notification.read_at,
        created_at=notification.created_at,
        actor=actor,
    )


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
    return NotificationListResponse(
        items=[_to_notification_response(db, workspace.id, n) for n in items],
        total=total,
        unread_count=unread_count,
    )


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
