"""Resolve human-readable entity labels for notifications."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.managers.attachment_manager import attachment_manager
from app.models.enums import AttachmentEntityTypeEnum

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

    label = _ENTITY_TYPE_LABEL.get(entity_type, entity_type.replace("_", " "))
    return f"{label} #{entity_id}"
