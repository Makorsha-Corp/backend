"""Business logic for attachment markup overlay layers."""

from __future__ import annotations



from typing import List, Optional, Tuple



from sqlalchemy.orm import Session



from app.dao.attachment import attachment_dao

from app.dao.attachment_markup import attachment_markup_dao

from app.dao.attachment_markup_event import attachment_markup_event_dao

from app.dao.profile import profile_dao

from app.managers.attachment_manager import (

    AttachmentNotFoundError,

    AttachmentValidationError,

)

from app.models.attachment import Attachment

from app.models.enums import UploadStatusEnum

from app.schemas.attachment_markup import (

    AttachmentMarkupEventResponse,

    AttachmentMarkupLayerResponse,

    MarkupPayload,

    is_markup_payload_empty,

)





class AttachmentMarkupManager:

    """Per-user vector markup on ready image/PDF attachments."""



    MARKUP_UNAVAILABLE_MSG = "Markup is only available for images and PDFs."



    def _get_ready_attachment(

        self,

        session: Session,

        *,

        workspace_id: int,

        attachment_id: int,

    ) -> Attachment:

        attachment = attachment_dao.get_active(session, attachment_id, workspace_id)

        if not attachment:

            raise AttachmentNotFoundError(f"Attachment {attachment_id} not found.")

        if attachment.upload_status != UploadStatusEnum.READY.value:

            raise AttachmentValidationError(self.MARKUP_UNAVAILABLE_MSG)

        if not self._is_markupable(attachment):

            raise AttachmentValidationError(self.MARKUP_UNAVAILABLE_MSG)

        return attachment



    @staticmethod

    def _is_markupable(attachment: Attachment) -> bool:

        mime = attachment.mime_type or ""

        fmt = (attachment.format or "").lower()

        if mime == "application/pdf" or fmt == "pdf":

            return True

        return mime.startswith("image/")



    def _resolve_user_name(self, session: Session, user_id: int) -> str:

        profile = profile_dao.get(session, id=user_id)

        return profile.name if profile else f"User #{user_id}"



    def _resolve_saved_stamp(self, session: Session, user_id: int) -> dict | None:

        profile = profile_dao.get(session, user_id)

        if not profile or not profile.saved_stamp:

            return None

        if not isinstance(profile.saved_stamp, dict):

            return None

        return profile.saved_stamp



    @staticmethod

    def _summarize_payload(payload: MarkupPayload) -> Tuple[dict, str]:

        pages: List[int | str] = []



        for page_key, page in payload.pages.items():

            has_content = bool(

                page.strokes or page.texts or page.scribbles or page.stamps

            )

            if has_content:

                try:

                    pages.append(int(page_key))

                except ValueError:

                    pages.append(page_key)



        pages.sort(key=lambda value: (isinstance(value, str), value))

        metadata = {"pages": pages}



        if pages:

            page_label = ", ".join(str(page) for page in pages)

            page_phrase = f"page{'s' if len(pages) != 1 else ''} {page_label}"

            description = f"Updated marks on {page_phrase}"

        else:

            description = "Updated marks"



        return metadata, description



    def _log_markup_event(

        self,

        session: Session,

        *,

        workspace_id: int,

        attachment_id: int,

        user_id: int,

        event_type: str,

        description: str,

        session_id: Optional[str] = None,

        metadata_json: Optional[dict] = None,

    ) -> None:

        attachment_markup_event_dao.create_event(

            session,

            workspace_id=workspace_id,

            attachment_id=attachment_id,

            user_id=user_id,

            event_type=event_type,

            description=description,

            session_id=session_id,

            metadata_json=metadata_json,

        )



    def _to_layer_response(

        self,

        session: Session,

        *,

        row,

        current_user_id: int,

    ) -> AttachmentMarkupLayerResponse:

        payload = MarkupPayload.model_validate(row.payload)

        return AttachmentMarkupLayerResponse(

            user_id=row.user_id,

            user_name=self._resolve_user_name(session, row.user_id),

            is_mine=row.user_id == current_user_id,

            updated_at=row.updated_at,

            payload=payload,

            saved_stamp=self._resolve_saved_stamp(session, row.user_id),

        )



    def _to_event_response(

        self,

        session: Session,

        *,

        row,

        current_user_id: int,

    ) -> AttachmentMarkupEventResponse:

        return AttachmentMarkupEventResponse(

            id=row.id,

            user_id=row.user_id,

            user_name=self._resolve_user_name(session, row.user_id),

            is_mine=row.user_id == current_user_id,

            session_id=row.session_id,

            event_type=row.event_type,

            description=row.description,

            metadata_json=row.metadata_json,

            created_at=row.created_at,

        )



    def list_layers(

        self,

        session: Session,

        *,

        workspace_id: int,

        attachment_id: int,

        current_user_id: int,

    ) -> List[AttachmentMarkupLayerResponse]:

        self._get_ready_attachment(

            session, workspace_id=workspace_id, attachment_id=attachment_id

        )

        rows = attachment_markup_dao.get_for_attachment(

            session, workspace_id=workspace_id, attachment_id=attachment_id

        )

        return [

            self._to_layer_response(session, row=row, current_user_id=current_user_id)

            for row in rows

        ]



    def list_events(

        self,

        session: Session,

        *,

        workspace_id: int,

        attachment_id: int,

        current_user_id: int,

    ) -> List[AttachmentMarkupEventResponse]:

        self._get_ready_attachment(

            session, workspace_id=workspace_id, attachment_id=attachment_id

        )

        rows = attachment_markup_event_dao.list_for_attachment(

            session, workspace_id=workspace_id, attachment_id=attachment_id

        )

        return [

            self._to_event_response(session, row=row, current_user_id=current_user_id)

            for row in rows

        ]



    def put_own_layer(

        self,

        session: Session,

        *,

        workspace_id: int,

        attachment_id: int,

        user_id: int,

        payload: MarkupPayload,

        session_id: Optional[str] = None,

    ) -> Optional[AttachmentMarkupLayerResponse]:

        self._get_ready_attachment(

            session, workspace_id=workspace_id, attachment_id=attachment_id

        )

        previous = attachment_markup_dao.get_for_user(

            session,

            workspace_id=workspace_id,

            attachment_id=attachment_id,

            user_id=user_id,

        )



        if is_markup_payload_empty(payload):

            if previous is not None:

                attachment_markup_dao.delete_for_user(

                    session,

                    workspace_id=workspace_id,

                    attachment_id=attachment_id,

                    user_id=user_id,

                )

                self._log_markup_event(

                    session,

                    workspace_id=workspace_id,

                    attachment_id=attachment_id,

                    user_id=user_id,

                    event_type="markup_cleared",

                    description="Cleared marks",

                    session_id=session_id,

                    metadata_json={"pages": []},

                )

            return None



        row = attachment_markup_dao.upsert_for_user(

            session,

            workspace_id=workspace_id,

            attachment_id=attachment_id,

            user_id=user_id,

            payload=payload.model_dump(),

        )

        metadata, description = self._summarize_payload(payload)

        event_type = "markup_saved" if previous is None else "markup_updated"

        if event_type == "markup_saved":

            description = description.replace("Updated marks", "Saved marks", 1)



        self._log_markup_event(

            session,

            workspace_id=workspace_id,

            attachment_id=attachment_id,

            user_id=user_id,

            event_type=event_type,

            description=description,

            session_id=session_id,

            metadata_json=metadata,

        )

        session.refresh(row)

        return self._to_layer_response(session, row=row, current_user_id=user_id)



    def delete_own_layer(

        self,

        session: Session,

        *,

        workspace_id: int,

        attachment_id: int,

        user_id: int,

        session_id: Optional[str] = None,

    ) -> None:

        self._get_ready_attachment(

            session, workspace_id=workspace_id, attachment_id=attachment_id

        )

        deleted = attachment_markup_dao.delete_for_user(

            session,

            workspace_id=workspace_id,

            attachment_id=attachment_id,

            user_id=user_id,

        )

        if deleted:

            self._log_markup_event(

                session,

                workspace_id=workspace_id,

                attachment_id=attachment_id,

                user_id=user_id,

                event_type="markup_cleared",

                description="Cleared marks",

                session_id=session_id,

                metadata_json={"pages": []},

            )





attachment_markup_manager = AttachmentMarkupManager()

