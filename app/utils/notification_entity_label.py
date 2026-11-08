"""Resolve human-readable entity labels for notifications."""
from __future__ import annotations

import logging

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.managers.attachment_manager import attachment_manager
from app.models.enums import AttachmentEntityTypeEnum
from app.services.approval_notification_service import format_order_ref

logger = logging.getLogger(__name__)

_ENTITY_TYPE_LABEL: dict[str, str] = {
    "purchase_order": "purchase order",
    "transfer_order": "transfer order",
    "expense_order": "expense order",
    "work_order": "work order",
    "sales_order": "sales order",
    "project": "project",
    "project_component": "project component",
    "machine": "machine",
    "inventory": "inventory",
    "item": "item",
}


def resolve_notification_entity_label(
    db: Session,
    *,
    workspace_id: int,
    entity_type: str,
    entity_id: int,
) -> str:
    """Business-facing label (e.g. PO-2026-015), not raw entity id."""
    fallback_label = format_order_ref(entity_type, entity_id)
    try:
        attachment_type = AttachmentEntityTypeEnum(entity_type)
        return attachment_manager.resolve_entity_label(
            db,
            workspace_id=workspace_id,
            entity_type=attachment_type,
            entity_id=entity_id,
        )
    except ValueError:
        pass
    except SQLAlchemyError:
        logger.warning(
            "notification entity label lookup failed workspace_id=%s entity_type=%s entity_id=%s",
            workspace_id,
            entity_type,
            entity_id,
            exc_info=True,
        )
        return fallback_label
    except Exception:
        logger.warning(
            "notification entity label lookup failed workspace_id=%s entity_type=%s entity_id=%s",
            workspace_id,
            entity_type,
            entity_id,
            exc_info=True,
        )
        return fallback_label

    label = _ENTITY_TYPE_LABEL.get(entity_type, entity_type.replace("_", " "))
    return f"{label} #{entity_id}"
