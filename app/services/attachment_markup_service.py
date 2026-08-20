"""Service for attachment markup overlay workflows."""
from typing import List, Optional

from sqlalchemy.orm import Session

from app.managers.attachment_markup_manager import (
    AttachmentMarkupManager,
    attachment_markup_manager,
)
from app.schemas.attachment_markup import (
    AttachmentMarkupLayerResponse,
    AttachmentMarkupListResponse,
    MarkupPayload,
)
from app.services.base_service import BaseService


class AttachmentMarkupService(BaseService):
    """Transaction orchestration for markup layers."""

    def __init__(self) -> None:
        super().__init__()
        self.manager: AttachmentMarkupManager = attachment_markup_manager

    def list_layers(
        self,
        db: Session,
        *,
        workspace_id: int,
        attachment_id: int,
        current_user_id: int,
    ) -> AttachmentMarkupListResponse:
        try:
            items = self.manager.list_layers(
                db,
                workspace_id=workspace_id,
                attachment_id=attachment_id,
                current_user_id=current_user_id,
            )
            self._commit_transaction(db)
            return AttachmentMarkupListResponse(items=items)
        except Exception:
            self._rollback_transaction(db)
            raise

    def put_own_layer(
        self,
        db: Session,
        *,
        workspace_id: int,
        attachment_id: int,
        user_id: int,
        payload: MarkupPayload,
    ) -> Optional[AttachmentMarkupLayerResponse]:
        try:
            layer = self.manager.put_own_layer(
                db,
                workspace_id=workspace_id,
                attachment_id=attachment_id,
                user_id=user_id,
                payload=payload,
            )
            self._commit_transaction(db)
            return layer
        except Exception:
            self._rollback_transaction(db)
            raise

    def delete_own_layer(
        self,
        db: Session,
        *,
        workspace_id: int,
        attachment_id: int,
        user_id: int,
    ) -> None:
        try:
            self.manager.delete_own_layer(
                db,
                workspace_id=workspace_id,
                attachment_id=attachment_id,
                user_id=user_id,
            )
            self._commit_transaction(db)
        except Exception:
            self._rollback_transaction(db)
            raise


attachment_markup_service = AttachmentMarkupService()
