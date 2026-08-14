"""Mobile upload session API — QR phone-to-desktop handoff."""
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.core.cloudinary_client import CloudinaryNotConfiguredError
from app.core.deps import get_current_active_user, get_current_workspace, get_db
from app.core.limiter import limiter
from app.models.profile import Profile
from app.models.workspace import Workspace
from app.schemas.attachment import AttachmentResponse
from app.schemas.mobile_upload import (
    MobileUploadPromoteRequest,
    MobileUploadPublicConfirmRequest,
    MobileUploadPublicSessionResponse,
    MobileUploadPublicSignRequest,
    MobileUploadPublicSignResponse,
    MobileUploadSessionCreateRequest,
    MobileUploadSessionCreateResponse,
    MobileUploadSessionResponse,
)
from app.managers.attachment_manager import AttachmentLimitError
from app.services.mobile_upload_service import (
    AttachmentConfirmError,
    AttachmentValidationError,
    MobileUploadSessionError,
    MobileUploadSessionNotFoundError,
    mobile_upload_service,
)

router = APIRouter()


def _not_found(exc: Exception) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Upload session not found.")


@router.post(
    "/sessions",
    response_model=MobileUploadSessionCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a mobile upload QR session",
)
@limiter.limit("10/minute")
def create_mobile_upload_session(
    request: Request,
    payload: MobileUploadSessionCreateRequest,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    try:
        return mobile_upload_service.create_session(
            db,
            workspace=workspace,
            user=current_user,
            payload=payload,
        )
    except CloudinaryNotConfiguredError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


@router.get(
    "/sessions/{session_id}",
    response_model=MobileUploadSessionResponse,
    summary="Poll mobile upload session status",
)
def get_mobile_upload_session(
    session_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    try:
        return mobile_upload_service.get_session(
            db,
            workspace_id=workspace.id,
            user_id=current_user.id,
            session_id=session_id,
        )
    except MobileUploadSessionNotFoundError as exc:
        raise _not_found(exc) from exc


@router.post(
    "/sessions/{session_id}/promote",
    response_model=AttachmentResponse,
    summary="Promote staged Cloudinary asset into an attachment",
)
def promote_mobile_upload_session(
    session_id: int,
    payload: MobileUploadPromoteRequest,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    try:
        return mobile_upload_service.promote_session(
            db,
            workspace=workspace,
            user=current_user,
            session_id=session_id,
            payload=payload,
        )
    except MobileUploadSessionNotFoundError as exc:
        raise _not_found(exc) from exc
    except AttachmentValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except AttachmentLimitError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except AttachmentConfirmError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except MobileUploadSessionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except CloudinaryNotConfiguredError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


@router.post(
    "/sessions/{session_id}/cancel",
    response_model=MobileUploadSessionResponse,
    summary="Cancel a waiting mobile upload session",
)
def cancel_mobile_upload_session(
    session_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    try:
        return mobile_upload_service.cancel_session(
            db,
            workspace_id=workspace.id,
            user_id=current_user.id,
            session_id=session_id,
        )
    except MobileUploadSessionNotFoundError as exc:
        raise _not_found(exc) from exc


@router.get(
    "/public",
    response_model=MobileUploadPublicSessionResponse,
    summary="Public session info for phone page (token only)",
)
@limiter.limit("30/minute")
def get_public_mobile_upload_session(
    request: Request,
    token: str = Query(..., min_length=16, max_length=512),
    db: Session = Depends(get_db),
):
    try:
        return mobile_upload_service.get_public_session(db, raw_token=token)
    except MobileUploadSessionNotFoundError as exc:
        raise _not_found(exc) from exc


@router.post(
    "/public/sign",
    response_model=MobileUploadPublicSignResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Request signed Cloudinary params for phone upload (token only)",
)
@limiter.limit("20/minute")
def public_sign_mobile_upload(
    request: Request,
    payload: MobileUploadPublicSignRequest,
    db: Session = Depends(get_db),
):
    try:
        return mobile_upload_service.public_sign(db, payload=payload)
    except MobileUploadSessionNotFoundError as exc:
        raise _not_found(exc) from exc
    except AttachmentValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except MobileUploadSessionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except CloudinaryNotConfiguredError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


@router.post(
    "/public/confirm",
    response_model=MobileUploadPublicSessionResponse,
    summary="Confirm phone upload into staging (token only)",
)
@limiter.limit("20/minute")
def public_confirm_mobile_upload(
    request: Request,
    payload: MobileUploadPublicConfirmRequest,
    db: Session = Depends(get_db),
):
    try:
        return mobile_upload_service.public_confirm(db, payload=payload)
    except MobileUploadSessionNotFoundError as exc:
        raise _not_found(exc) from exc
    except AttachmentConfirmError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except MobileUploadSessionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except CloudinaryNotConfiguredError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
