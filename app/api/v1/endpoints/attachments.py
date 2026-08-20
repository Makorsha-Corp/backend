"""Attachment upload API endpoints (Cloudinary signed direct upload)."""
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.core.cloudinary_client import CloudinaryNotConfiguredError
from app.core.deps import get_current_active_user, get_current_workspace, get_db
from app.managers.attachment_manager import AttachmentLimitError
from app.models.enums import AttachmentEntityTypeEnum
from app.models.profile import Profile
from app.models.workspace import Workspace
from app.schemas.attachment import (
    AttachmentConfirmRequest,
    AttachmentListResponse,
    AttachmentPdfPageResponse,
    AttachmentResponse,
    AttachmentSignRequest,
    AttachmentSignResponse,
)
from app.schemas.attachment_markup import (
    AttachmentMarkupLayerResponse,
    AttachmentMarkupListResponse,
    AttachmentMarkupPutRequest,
)
from app.services.attachment_service import (
    AttachmentConfirmError,
    AttachmentNotFoundError,
    AttachmentValidationError,
    attachment_service,
)
from app.services.attachment_markup_service import attachment_markup_service

router = APIRouter()


@router.post(
    "/sign",
    response_model=AttachmentSignResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Request signed upload parameters",
)
def sign_attachment_upload(
    payload: AttachmentSignRequest,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Validate file metadata, create pending attachment row, return Cloudinary signature."""
    try:
        return attachment_service.sign_upload(
            db,
            workspace=workspace,
            user=current_user,
            payload=payload,
        )
    except AttachmentValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except AttachmentLimitError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except CloudinaryNotConfiguredError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to prepare upload.",
        ) from exc


@router.post(
    "/{attachment_id}/confirm",
    response_model=AttachmentResponse,
    status_code=status.HTTP_200_OK,
    summary="Confirm upload after Cloudinary direct POST",
)
def confirm_attachment_upload(
    attachment_id: int,
    payload: AttachmentConfirmRequest | None = None,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Verify asset exists in Cloudinary and mark attachment ready."""
    try:
        return attachment_service.confirm_upload(
            db,
            workspace_id=workspace.id,
            attachment_id=attachment_id,
            performed_by=current_user.id,
            payload=payload,
        )
    except AttachmentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AttachmentConfirmError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except CloudinaryNotConfiguredError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to confirm upload.",
        ) from exc


@router.get(
    "/",
    response_model=AttachmentListResponse,
    status_code=status.HTTP_200_OK,
    summary="List attachments for an entity",
)
def list_attachments(
    entity_type: AttachmentEntityTypeEnum = Query(...),
    entity_id: int = Query(..., ge=1),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    """List ready attachments linked to a workspace entity (lazy-load friendly)."""
    return attachment_service.list_attachments(
        db,
        workspace_id=workspace.id,
        entity_type=entity_type,
        entity_id=entity_id,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{attachment_id}",
    response_model=AttachmentResponse,
    status_code=status.HTTP_200_OK,
    summary="Get a single attachment",
)
def get_attachment(
    attachment_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    """Get attachment metadata and derived URLs."""
    try:
        return attachment_service.get_attachment(
            db,
            workspace_id=workspace.id,
            attachment_id=attachment_id,
        )
    except AttachmentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get(
    "/{attachment_id}/pdf-page",
    response_model=AttachmentPdfPageResponse,
    status_code=status.HTTP_200_OK,
    summary="Get signed JPG URL for a PDF page",
)
def get_attachment_pdf_page(
    attachment_id: int,
    page: int = Query(1, ge=1),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    """Return a signed Cloudinary JPG for one page of a ready PDF attachment."""
    try:
        return attachment_service.get_pdf_page_image(
            db,
            workspace_id=workspace.id,
            attachment_id=attachment_id,
            page=page,
        )
    except AttachmentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AttachmentValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except AttachmentConfirmError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except CloudinaryNotConfiguredError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


@router.get(
    "/{attachment_id}/markups",
    response_model=AttachmentMarkupListResponse,
    status_code=status.HTTP_200_OK,
    summary="List markup overlay layers for an attachment",
)
def list_attachment_markups(
    attachment_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Return all users' markup layers for a ready image or PDF attachment."""
    try:
        return attachment_markup_service.list_layers(
            db,
            workspace_id=workspace.id,
            attachment_id=attachment_id,
            current_user_id=current_user.id,
        )
    except AttachmentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AttachmentValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.put(
    "/{attachment_id}/markups/me",
    response_model=AttachmentMarkupLayerResponse,
    status_code=status.HTTP_200_OK,
    summary="Save your markup overlay layer",
    responses={
        204: {"description": "Layer cleared (empty payload)"},
    },
)
def put_my_attachment_markup(
    attachment_id: int,
    body: AttachmentMarkupPutRequest,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Save or update the current user's markup layer. Empty payload removes the layer."""
    try:
        layer = attachment_markup_service.put_own_layer(
            db,
            workspace_id=workspace.id,
            attachment_id=attachment_id,
            user_id=current_user.id,
            payload=body.payload,
        )
        if layer is None:
            return Response(status_code=status.HTTP_204_NO_CONTENT)
        return layer
    except AttachmentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AttachmentValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.delete(
    "/{attachment_id}/markups/me",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete your markup overlay layer",
)
def delete_my_attachment_markup(
    attachment_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Remove the current user's markup layer for this attachment."""
    try:
        attachment_markup_service.delete_own_layer(
            db,
            workspace_id=workspace.id,
            attachment_id=attachment_id,
            user_id=current_user.id,
        )
    except AttachmentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AttachmentValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.delete(
    "/{attachment_id}",
    response_model=AttachmentResponse,
    status_code=status.HTTP_200_OK,
    summary="Soft-delete attachment",
)
def delete_attachment(
    attachment_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Soft-delete attachment and remove from Cloudinary when configured."""
    try:
        return attachment_service.delete_attachment(
            db,
            workspace_id=workspace.id,
            attachment_id=attachment_id,
            deleted_by=current_user.id,
        )
    except AttachmentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete attachment.",
        ) from exc
