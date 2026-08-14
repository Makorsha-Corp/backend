"""Attachment business logic — validation, public_id minting, URL derivation."""
from __future__ import annotations

import re
import time
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.core.cloudinary_client import (
    AUTHENTICATED_DELIVERY_TYPE,
    CloudinaryNotConfiguredError,
    build_signed_delivery_url,
    destroy_resource,
    generate_upload_signature,
    get_resource,
)
from app.core.config import settings
from app.dao.account_invoice import account_invoice_dao
from app.dao.attachment import attachment_dao
from app.dao.attachment_ledger import attachment_ledger_dao
from app.dao.attachment_link import AttachmentLinkCreateSchema, attachment_link_dao
from app.dao.expense_order import expense_order_dao
from app.dao.item import item_dao
from app.dao.machine import machine_dao
from app.dao.project import project_dao
from app.dao.project_component import project_component_dao
from app.dao.help_ticket import help_ticket_dao
from app.dao.purchase_order import purchase_order_dao
from app.dao.sales_order import sales_order_dao
from app.dao.transfer_order import transfer_order_dao
from app.dao.work_order import work_order_dao
from app.models.attachment import Attachment
from app.models.enums import (
    AttachmentEntityTypeEnum,
    AttachmentLedgerTransactionTypeEnum,
    UploadStatusEnum,
)
from app.models.profile import Profile
from app.schemas.attachment import (
    AttachmentConfirmRequest,
    AttachmentCreateInternal,
    AttachmentDerivedUrls,
    AttachmentLinkInfo,
    AttachmentResponse,
    AttachmentSignRequest,
    AttachmentSignResponse,
    AttachmentUpdateInternal,
)
from app.utils.attachment_allowlist import (
    ALLOWED_MIME_TYPES,
    MAX_FILE_SIZE_BYTES,
    AttachmentConfirmError,
    AttachmentValidationError,
    NormalizedUploadRequest,
    normalize_upload_request,
    validate_cloudinary_resource,
)

ENTITY_TYPE_FOLDER_LABELS: dict[AttachmentEntityTypeEnum, str] = {
    AttachmentEntityTypeEnum.PURCHASE_ORDER: "Purchase Orders",
    AttachmentEntityTypeEnum.SALES_ORDER: "Sales Orders",
    AttachmentEntityTypeEnum.EXPENSE_ORDER: "Expense Orders",
    AttachmentEntityTypeEnum.TRANSFER_ORDER: "Transfer Orders",
    AttachmentEntityTypeEnum.WORK_ORDER: "Work Orders",
    AttachmentEntityTypeEnum.PROJECT: "Projects",
    AttachmentEntityTypeEnum.PROJECT_COMPONENT: "Project Components",
    AttachmentEntityTypeEnum.ITEM: "Items",
    AttachmentEntityTypeEnum.MACHINE: "Machines",
    AttachmentEntityTypeEnum.ACCOUNT_INVOICE: "Invoices",
    AttachmentEntityTypeEnum.SUPPORT_TICKET: "Help Tickets",
    AttachmentEntityTypeEnum.SCRATCH: "Scratch",
}

_DISPLAY_NAME_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")


class AttachmentNotFoundError(ValueError):
    """Attachment not found in workspace."""


class AttachmentLimitError(ValueError):
    """Entity has reached the maximum number of attachments."""


class AttachmentManager:
    """Manager for attachment upload workflows."""

    def normalize_upload_request(self, payload: AttachmentSignRequest) -> NormalizedUploadRequest:
        return normalize_upload_request(payload)

    def assert_entity_attachment_capacity(
        self,
        session: Session,
        *,
        workspace_id: int,
        entity_type: AttachmentEntityTypeEnum,
        entity_id: int,
    ) -> None:
        max_per_entity = settings.MAX_ATTACHMENTS_PER_ENTITY
        current = attachment_link_dao.count_linked_attachments_for_entity(
            session,
            workspace_id=workspace_id,
            entity_type=entity_type.value,
            entity_id=entity_id,
        )
        if current >= max_per_entity:
            raise AttachmentLimitError(
                f"This record already has the maximum of {max_per_entity} attachments."
            )

    def _upload_env(self) -> str:
        return settings.CLOUDINARY_UPLOAD_ENV or settings.ENVIRONMENT

    def _is_production(self) -> bool:
        return self._upload_env() == "production"

    def build_public_id(self, *, workspace_id: int) -> str:
        """Opaque public_id stored in DB and sent to Cloudinary (delivery URL identity)."""
        token = uuid.uuid4().hex
        base = f"ws-{workspace_id}/{token}"
        if self._is_production():
            return base
        return f"{self._upload_env()}/{base}"

    def build_asset_folder(
        self,
        *,
        workspace_name: str,
        entity_type: AttachmentEntityTypeEnum,
        entity_label: str,
    ) -> str:
        """Human-readable Media Library folder (mutable, no URL impact)."""
        type_label = ENTITY_TYPE_FOLDER_LABELS[entity_type]
        folder = f"{workspace_name}/{type_label}/{entity_label}"
        if self._is_production():
            return folder
        return f"Dev/{folder}"

    def build_display_name(self, file_name: str) -> str:
        """Sanitize filename for Cloudinary display_name (no slashes or control chars)."""
        cleaned = file_name.replace("/", "-").replace("\\", "-")
        cleaned = _DISPLAY_NAME_CONTROL_CHARS.sub("", cleaned).strip()
        if not cleaned:
            cleaned = "upload"
        return cleaned[:255]

    def resolve_entity_label(
        self,
        session: Session,
        *,
        workspace_id: int,
        entity_type: AttachmentEntityTypeEnum,
        entity_id: int,
    ) -> str:
        """Workspace-scoped business label for asset_folder (falls back to type-id)."""
        fallback = f"{entity_type.value}-{entity_id}"

        if entity_type == AttachmentEntityTypeEnum.SCRATCH:
            return fallback

        row = self._fetch_entity_row(
            session,
            workspace_id=workspace_id,
            entity_type=entity_type,
            entity_id=entity_id,
        )
        if row is None:
            return fallback

        label = self._extract_entity_label(entity_type, row)
        return label or fallback

    def _fetch_entity_row(
        self,
        session: Session,
        *,
        workspace_id: int,
        entity_type: AttachmentEntityTypeEnum,
        entity_id: int,
    ) -> Any | None:
        dao_map = {
            AttachmentEntityTypeEnum.PURCHASE_ORDER: purchase_order_dao,
            AttachmentEntityTypeEnum.SALES_ORDER: sales_order_dao,
            AttachmentEntityTypeEnum.EXPENSE_ORDER: expense_order_dao,
            AttachmentEntityTypeEnum.TRANSFER_ORDER: transfer_order_dao,
            AttachmentEntityTypeEnum.WORK_ORDER: work_order_dao,
            AttachmentEntityTypeEnum.PROJECT: project_dao,
            AttachmentEntityTypeEnum.PROJECT_COMPONENT: project_component_dao,
            AttachmentEntityTypeEnum.ITEM: item_dao,
            AttachmentEntityTypeEnum.MACHINE: machine_dao,
            AttachmentEntityTypeEnum.ACCOUNT_INVOICE: account_invoice_dao,
            AttachmentEntityTypeEnum.SUPPORT_TICKET: help_ticket_dao,
        }
        dao = dao_map.get(entity_type)
        if dao is None:
            return None
        return dao.get_by_id_and_workspace(session, id=entity_id, workspace_id=workspace_id)

    def _extract_entity_label(
        self,
        entity_type: AttachmentEntityTypeEnum,
        row: Any,
    ) -> str | None:
        if entity_type == AttachmentEntityTypeEnum.PURCHASE_ORDER:
            return row.po_number
        if entity_type == AttachmentEntityTypeEnum.SALES_ORDER:
            return row.sales_order_number
        if entity_type == AttachmentEntityTypeEnum.EXPENSE_ORDER:
            return row.expense_number
        if entity_type == AttachmentEntityTypeEnum.TRANSFER_ORDER:
            return row.transfer_number
        if entity_type == AttachmentEntityTypeEnum.WORK_ORDER:
            return row.work_order_number
        if entity_type == AttachmentEntityTypeEnum.PROJECT:
            return row.name
        if entity_type == AttachmentEntityTypeEnum.PROJECT_COMPONENT:
            return row.name
        if entity_type == AttachmentEntityTypeEnum.MACHINE:
            return row.name
        if entity_type == AttachmentEntityTypeEnum.ITEM:
            return row.sku or row.name
        if entity_type == AttachmentEntityTypeEnum.ACCOUNT_INVOICE:
            return row.invoice_number
        if entity_type == AttachmentEntityTypeEnum.SUPPORT_TICKET:
            return row.ticket_number
        return None

    def _attachment_event_metadata(self, attachment: Attachment) -> dict[str, Any]:
        return {
            "attachment_id": attachment.id,
            "file_name": attachment.file_name,
            "mime_type": attachment.mime_type,
            "file_size": attachment.file_size,
        }

    def _append_attachment_ledger(
        self,
        session: Session,
        *,
        attachment: Attachment,
        workspace_id: int,
        transaction_type: AttachmentLedgerTransactionTypeEnum | str,
        entity_type: str | None = None,
        entity_id: int | None = None,
        performed_by: int | None = None,
        notes: str | None = None,
    ) -> None:
        if entity_type is None or entity_id is None:
            links = attachment_link_dao.get_links_for_attachment(
                session,
                workspace_id=workspace_id,
                attachment_id=attachment.id,
            )
            if links:
                entity_type = links[0].entity_type
                entity_id = links[0].entity_id

        tx_type = (
            transaction_type.value
            if isinstance(transaction_type, AttachmentLedgerTransactionTypeEnum)
            else transaction_type
        )
        attachment_ledger_dao.create(
            session,
            obj_in={
                "workspace_id": workspace_id,
                "attachment_id": attachment.id,
                "transaction_type": tx_type,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "file_name": attachment.file_name,
                "mime_type": attachment.mime_type,
                "file_size": attachment.file_size,
                "notes": notes,
                "performed_by": performed_by,
            },
        )
        session.flush()

    def _log_attachment_entity_events(
        self,
        session: Session,
        *,
        attachment: Attachment,
        workspace_id: int,
        event_type: str,
        performed_by: int | None,
    ) -> None:
        """Write attachment add/remove events to the linked entity's activity log."""
        from app.managers.account_invoice_manager import account_invoice_manager
        from app.managers.expense_order_manager import expense_order_manager
        from app.managers.machine_activity_manager import machine_activity_manager
        from app.managers.project_component_activity_manager import (
            project_component_activity_manager,
        )
        from app.managers.project_manager import project_manager
        from app.managers.purchase_order_manager import purchase_order_manager
        from app.managers.sales_manager import sales_manager
        from app.managers.transfer_order_manager import transfer_order_manager
        from app.managers.work_order_manager import work_order_manager

        description = (
            f"Attached {attachment.file_name}"
            if event_type == "attachment_added"
            else f"Removed {attachment.file_name}"
        )
        metadata = self._attachment_event_metadata(attachment)

        links = attachment_link_dao.get_links_for_attachment(
            session,
            workspace_id=workspace_id,
            attachment_id=attachment.id,
        )
        for link in links:
            entity_type = AttachmentEntityTypeEnum(link.entity_type)
            entity_id = link.entity_id

            if entity_type == AttachmentEntityTypeEnum.PURCHASE_ORDER:
                purchase_order_manager.log_event(
                    session,
                    entity_id,
                    workspace_id,
                    event_type,
                    description,
                    performed_by,
                    metadata,
                )
            elif entity_type == AttachmentEntityTypeEnum.SALES_ORDER:
                sales_manager.log_event(
                    session,
                    entity_id,
                    workspace_id,
                    event_type,
                    description,
                    performed_by,
                    metadata,
                )
            elif entity_type == AttachmentEntityTypeEnum.EXPENSE_ORDER:
                expense_order_manager.log_event(
                    session,
                    entity_id,
                    workspace_id,
                    event_type,
                    description,
                    performed_by,
                    metadata,
                )
            elif entity_type == AttachmentEntityTypeEnum.TRANSFER_ORDER:
                transfer_order_manager.log_event(
                    session,
                    entity_id,
                    workspace_id,
                    event_type,
                    description,
                    performed_by,
                    metadata,
                )
            elif entity_type == AttachmentEntityTypeEnum.WORK_ORDER:
                work_order_manager.log_event(
                    session,
                    entity_id,
                    workspace_id,
                    event_type,
                    description,
                    performed_by,
                    metadata,
                )
            elif entity_type == AttachmentEntityTypeEnum.PROJECT:
                project_manager.log_event(
                    session,
                    entity_id,
                    workspace_id,
                    event_type,
                    description,
                    performed_by,
                    metadata,
                )
            elif entity_type == AttachmentEntityTypeEnum.PROJECT_COMPONENT:
                project_component_activity_manager.log_event(
                    session,
                    entity_id,
                    workspace_id,
                    event_type,
                    description,
                    performed_by,
                    metadata,
                )
            elif entity_type == AttachmentEntityTypeEnum.MACHINE:
                machine_activity_manager.log_event(
                    session,
                    entity_id,
                    workspace_id,
                    event_type,
                    description,
                    performed_by,
                    metadata,
                )
            elif entity_type == AttachmentEntityTypeEnum.ACCOUNT_INVOICE:
                invoice = account_invoice_dao.get_by_id_and_workspace(
                    session,
                    id=entity_id,
                    workspace_id=workspace_id,
                )
                if invoice is not None:
                    account_invoice_manager._log_event(
                        session,
                        invoice,
                        event_type,
                        description,
                        performed_by=performed_by,
                        metadata=metadata,
                    )

    def create_pending_attachment(
        self,
        session: Session,
        *,
        workspace_id: int,
        user: Profile,
        payload: AttachmentSignRequest,
        normalized: NormalizedUploadRequest,
        stored_public_id: str,
        asset_folder: str,
    ) -> Attachment:
        self.assert_entity_attachment_capacity(
            session,
            workspace_id=workspace_id,
            entity_type=payload.entity_type,
            entity_id=payload.entity_id,
        )
        create_data = AttachmentCreateInternal(
            workspace_id=workspace_id,
            file_name=normalized.file_name,
            mime_type=normalized.mime_type,
            file_size=payload.file_size,
            uploaded_by=user.id,
            note=payload.note,
            public_id=stored_public_id,
            asset_folder=asset_folder,
            resource_type=normalized.resource_type,
            delivery_type=AUTHENTICATED_DELIVERY_TYPE,
            upload_status=UploadStatusEnum.PENDING.value,
        )
        attachment = attachment_dao.create(session, obj_in=create_data.model_dump())
        link_data = AttachmentLinkCreateSchema(
            workspace_id=workspace_id,
            attachment_id=attachment.id,
            entity_type=payload.entity_type.value,
            entity_id=payload.entity_id,
            linked_by=user.id,
        )
        attachment_link_dao.create(session, obj_in=link_data.model_dump())
        session.flush()
        self._append_attachment_ledger(
            session,
            attachment=attachment,
            workspace_id=workspace_id,
            transaction_type=AttachmentLedgerTransactionTypeEnum.PENDING,
            entity_type=payload.entity_type.value,
            entity_id=payload.entity_id,
            performed_by=user.id,
        )
        return attachment

    def build_sign_response(
        self,
        *,
        attachment: Attachment,
        public_id: str,
        asset_folder: str,
        display_name: str,
    ) -> AttachmentSignResponse:
        if not settings.CLOUDINARY_CLOUD_NAME or not settings.CLOUDINARY_API_KEY:
            raise CloudinaryNotConfiguredError("Cloudinary cloud name and API key are required.")

        timestamp = int(time.time())
        signature = generate_upload_signature(
            public_id=public_id,
            asset_folder=asset_folder,
            display_name=display_name,
            timestamp=timestamp,
            delivery_type=AUTHENTICATED_DELIVERY_TYPE,
        )
        cloud_name = settings.CLOUDINARY_CLOUD_NAME
        resource_type = attachment.resource_type or "image"
        upload_url = f"https://api.cloudinary.com/v1_1/{cloud_name}/{resource_type}/upload"

        return AttachmentSignResponse(
            attachment_id=attachment.id,
            cloud_name=cloud_name,
            api_key=settings.CLOUDINARY_API_KEY,
            timestamp=timestamp,
            public_id=public_id,
            asset_folder=asset_folder,
            display_name=display_name,
            type=AUTHENTICATED_DELIVERY_TYPE,
            signature=signature,
            resource_type=resource_type,
            upload_url=upload_url,
        )

    def derive_urls(self, attachment: Attachment) -> AttachmentDerivedUrls:
        if attachment.upload_status != UploadStatusEnum.READY.value:
            return AttachmentDerivedUrls()
        if not attachment.public_id or not attachment.version or not attachment.format:
            return AttachmentDerivedUrls()

        if not settings.CLOUDINARY_CLOUD_NAME or not settings.CLOUDINARY_API_SECRET:
            return AttachmentDerivedUrls()

        resource_type = attachment.resource_type or "image"
        delivery_type = attachment.delivery_type or "upload"
        public_id = attachment.public_id
        fmt = attachment.format
        version = int(attachment.version)

        if resource_type == "raw":
            download_url = build_signed_delivery_url(
                public_id=public_id,
                resource_type=resource_type,
                delivery_type=delivery_type,
                version=version,
                fmt=fmt,
                flags="attachment",
            )
            return AttachmentDerivedUrls(
                thumb_url=None,
                preview_url=None,
                download_url=download_url,
            )

        is_pdf = attachment.mime_type == "application/pdf" or fmt == "pdf"
        if is_pdf:
            thumb_url = build_signed_delivery_url(
                public_id=public_id,
                resource_type=resource_type,
                delivery_type=delivery_type,
                version=version,
                fmt="jpg",
                transformation=[
                    {"page": 1, "fetch_format": "jpg", "quality": "auto", "width": 400, "crop": "limit"},
                ],
            )
        else:
            thumb_url = build_signed_delivery_url(
                public_id=public_id,
                resource_type=resource_type,
                delivery_type=delivery_type,
                version=version,
                fmt=fmt,
                transformation=[
                    {"fetch_format": "auto", "quality": "auto", "width": 400, "crop": "limit"},
                ],
            )

        preview_url = build_signed_delivery_url(
            public_id=public_id,
            resource_type=resource_type,
            delivery_type=delivery_type,
            version=version,
            fmt=fmt,
            transformation=[
                {"fetch_format": "auto", "quality": "auto", "width": 1600, "crop": "limit"},
            ],
        )
        download_url = build_signed_delivery_url(
            public_id=public_id,
            resource_type=resource_type,
            delivery_type=delivery_type,
            version=version,
            fmt=fmt,
            flags="attachment",
        )

        return AttachmentDerivedUrls(
            thumb_url=thumb_url,
            preview_url=preview_url,
            download_url=download_url,
        )

    def build_pdf_page_image_url(self, attachment: Attachment, *, page: int, width: int = 1600) -> str:
        """Signed JPG for a single PDF page (Cloudinary page=N rasterization)."""
        if page < 1:
            raise AttachmentValidationError("Page number must be at least 1.")
        if attachment.upload_status != UploadStatusEnum.READY.value:
            raise AttachmentConfirmError("Attachment is not ready.")
        if attachment.mime_type != "application/pdf" and attachment.format != "pdf":
            raise AttachmentValidationError("Attachment is not a PDF.")
        if not attachment.public_id or not attachment.version:
            raise AttachmentConfirmError("Attachment is missing Cloudinary metadata.")

        if attachment.page_count is not None and page > attachment.page_count:
            raise AttachmentValidationError(
                f"Page {page} is out of range (document has {attachment.page_count} pages)."
            )

        if not settings.CLOUDINARY_CLOUD_NAME or not settings.CLOUDINARY_API_SECRET:
            raise CloudinaryNotConfiguredError("Cloudinary is not configured.")

        resource_type = attachment.resource_type or "image"
        delivery_type = attachment.delivery_type or "upload"
        return build_signed_delivery_url(
            public_id=attachment.public_id,
            resource_type=resource_type,
            delivery_type=delivery_type,
            version=int(attachment.version),
            fmt="jpg",
            transformation=[
                {
                    "page": page,
                    "fetch_format": "jpg",
                    "quality": "auto",
                    "width": width,
                    "crop": "limit",
                },
            ],
        )

    def get_pdf_page_image(
        self,
        session: Session,
        *,
        attachment_id: int,
        workspace_id: int,
        page: int,
    ) -> dict[str, Any]:
        attachment = attachment_dao.get_active(session, attachment_id, workspace_id)
        if not attachment:
            raise AttachmentNotFoundError(f"Attachment {attachment_id} not found.")
        url = self.build_pdf_page_image_url(attachment, page=page)
        return {
            "url": url,
            "page": page,
            "page_count": attachment.page_count,
        }

    def to_response(
        self,
        session: Session,
        attachment: Attachment,
        *,
        workspace_id: int | None = None,
    ) -> AttachmentResponse:
        ws_id = workspace_id or attachment.workspace_id
        links = attachment_link_dao.get_links_for_attachment(
            session, workspace_id=ws_id, attachment_id=attachment.id
        )
        link_infos = [
            AttachmentLinkInfo(
                entity_type=AttachmentEntityTypeEnum(link.entity_type),
                entity_id=link.entity_id,
            )
            for link in links
        ]

        return AttachmentResponse(
            id=attachment.id,
            file_name=attachment.file_name,
            mime_type=attachment.mime_type,
            file_size=attachment.file_size,
            note=attachment.note,
            uploaded_by=attachment.uploaded_by,
            uploaded_at=attachment.uploaded_at,
            upload_status=attachment.upload_status,
            public_id=attachment.public_id,
            format=attachment.format,
            version=attachment.version,
            width=attachment.width,
            height=attachment.height,
            page_count=attachment.page_count,
            file_url=attachment.file_url,
            links=link_infos,
            urls=self.derive_urls(attachment),
        )

    def confirm_attachment(
        self,
        session: Session,
        *,
        attachment_id: int,
        workspace_id: int,
        performed_by: int | None = None,
        _payload: AttachmentConfirmRequest | None = None,
    ) -> Attachment:
        attachment = attachment_dao.get_active(session, attachment_id, workspace_id)
        if not attachment:
            raise AttachmentNotFoundError(f"Attachment {attachment_id} not found.")

        if attachment.upload_status == UploadStatusEnum.READY.value:
            return attachment

        was_pending = attachment.upload_status == UploadStatusEnum.PENDING.value

        if not attachment.public_id:
            raise AttachmentConfirmError("Attachment has no public_id.")

        try:
            resource: dict[str, Any] = get_resource(
                public_id=attachment.public_id,
                resource_type=attachment.resource_type or "image",
                delivery_type=attachment.delivery_type or AUTHENTICATED_DELIVERY_TYPE,
            )
        except Exception as exc:
            attachment.upload_status = UploadStatusEnum.FAILED.value
            session.add(attachment)
            session.flush()
            actor_id = performed_by if performed_by is not None else attachment.uploaded_by
            self._append_attachment_ledger(
                session,
                attachment=attachment,
                workspace_id=workspace_id,
                transaction_type=AttachmentLedgerTransactionTypeEnum.FAILED,
                performed_by=actor_id,
                notes=str(exc),
            )
            raise AttachmentConfirmError(f"Cloudinary verification failed: {exc}") from exc

        try:
            validate_cloudinary_resource(file_name=attachment.file_name, resource=resource)
        except AttachmentConfirmError as exc:
            attachment.upload_status = UploadStatusEnum.FAILED.value
            session.add(attachment)
            session.flush()
            actor_id = performed_by if performed_by is not None else attachment.uploaded_by
            self._append_attachment_ledger(
                session,
                attachment=attachment,
                workspace_id=workspace_id,
                transaction_type=AttachmentLedgerTransactionTypeEnum.FAILED,
                performed_by=actor_id,
                notes=str(exc),
            )
            raise exc

        update = AttachmentUpdateInternal(
            file_url=resource.get("secure_url") or resource.get("url"),
            file_size=resource.get("bytes") or attachment.file_size,
            format=resource.get("format"),
            version=resource.get("version"),
            width=resource.get("width"),
            height=resource.get("height"),
            page_count=resource.get("pages"),
            asset_id=resource.get("asset_id"),
            etag=resource.get("etag"),
            upload_status=UploadStatusEnum.READY.value,
        )
        if resource.get("resource_type") == "image" and resource.get("format") == "pdf":
            update.mime_type = "application/pdf"

        attachment_dao.update(session, db_obj=attachment, obj_in=update.model_dump(exclude_unset=True))
        session.flush()
        session.refresh(attachment)
        actor_id = performed_by if performed_by is not None else attachment.uploaded_by
        self._append_attachment_ledger(
            session,
            attachment=attachment,
            workspace_id=workspace_id,
            transaction_type=AttachmentLedgerTransactionTypeEnum.READY,
            performed_by=actor_id,
        )
        if was_pending:
            self._log_attachment_entity_events(
                session,
                attachment=attachment,
                workspace_id=workspace_id,
                event_type="attachment_added",
                performed_by=actor_id,
            )
        return attachment

    def delete_attachment(
        self,
        session: Session,
        *,
        attachment_id: int,
        workspace_id: int,
        deleted_by: int,
    ) -> Attachment | None:
        attachment = attachment_dao.soft_delete(
            session, id=attachment_id, workspace_id=workspace_id, deleted_by=deleted_by
        )
        if attachment:
            self._append_attachment_ledger(
                session,
                attachment=attachment,
                workspace_id=workspace_id,
                transaction_type=AttachmentLedgerTransactionTypeEnum.DELETED,
                performed_by=deleted_by,
            )
            self._log_attachment_entity_events(
                session,
                attachment=attachment,
                workspace_id=workspace_id,
                event_type="attachment_removed",
                performed_by=deleted_by,
            )
        if attachment and attachment.public_id and attachment.upload_status == UploadStatusEnum.READY.value:
            try:
                destroy_resource(
                    public_id=attachment.public_id,
                    resource_type=attachment.resource_type or "image",
                    delivery_type=attachment.delivery_type or AUTHENTICATED_DELIVERY_TYPE,
                )
            except CloudinaryNotConfiguredError:
                pass
            except Exception:
                pass
        return attachment


attachment_manager = AttachmentManager()
