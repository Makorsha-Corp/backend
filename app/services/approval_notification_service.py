"""Emit approval-related notifications for PO / TO / EXP workflows."""
from __future__ import annotations

from typing import Any, List, Optional, Set, Tuple

from sqlalchemy.orm import Session

from app.core.notification_types import (
    APPROVAL_ASSIGNED,
    APPROVAL_PENDING,
    INVOICE_ACTION,
    SECTION_CONFIRM,
    SOURCE_APPROVER,
    SOURCE_INVOICE,
    SOURCE_ORDER,
    SOURCE_SECTION,
)
from app.dao.notification import notification_dao
from app.dao.workspace_member import workspace_member_dao
from app.models.profile import Profile

ORDER_PREFIX = {
    "purchase_order": "PO",
    "transfer_order": "TO",
    "expense_order": "EXP",
}


def format_order_ref(entity_type: str, entity_id: int) -> str:
    prefix = ORDER_PREFIX.get(entity_type)
    if prefix:
        return f"{prefix}-{entity_id}"
    return f"{entity_type.replace('_', ' ')} #{entity_id}"


def _active_member_ids(db: Session, workspace_id: int) -> Set[int]:
    members = workspace_member_dao.get_workspace_members(
        db, workspace_id=workspace_id, status="active"
    )
    return {member.user_id for member in members}


def _notify_user(
    db: Session,
    *,
    workspace_id: int,
    recipient_user_id: int,
    actor_user_id: int | None,
    notification_type: str,
    entity_type: str,
    entity_id: int,
    source_type: str,
    source_id: int,
    preview: str | None = None,
) -> None:
    allowed = _active_member_ids(db, workspace_id)
    if recipient_user_id not in allowed:
        return
    notification_dao.create(
        db=db,
        workspace_id=workspace_id,
        recipient_user_id=recipient_user_id,
        actor_user_id=actor_user_id,
        notification_type=notification_type,
        entity_type=entity_type,
        entity_id=entity_id,
        source_type=source_type,
        source_id=source_id,
        preview=preview,
    )


def _actor_name(db: Session, user_id: int | None) -> str:
    if user_id is None:
        return "Someone"
    profile = db.query(Profile).filter(Profile.id == user_id).first()
    return profile.name if profile and profile.name else f"User {user_id}"


def _approval_summary(
    db: Session, entity_type: str, entity_id: int, workspace_id: int
) -> Tuple[int, int, bool]:
    if entity_type == "purchase_order":
        from app.managers.purchase_order_manager import purchase_order_manager

        po = purchase_order_manager.get_purchase_order(db, entity_id, workspace_id)
        return purchase_order_manager.approval_summary(db, po)
    if entity_type == "transfer_order":
        from app.managers.transfer_order_manager import transfer_order_manager

        to = transfer_order_manager.get_transfer_order(db, entity_id, workspace_id)
        return transfer_order_manager.approval_summary(db, to)
    if entity_type == "expense_order":
        from app.managers.expense_order_manager import expense_order_manager

        eo = expense_order_manager.get_expense_order(db, entity_id, workspace_id)
        return expense_order_manager.approval_summary(db, eo)
    return 0, 0, True


def build_approval_preview(
    db: Session, entity_type: str, entity_id: int, workspace_id: int
) -> str:
    approved_count, required, _met = _approval_summary(db, entity_type, entity_id, workspace_id)
    if required <= 0:
        return "Ready for review"
    return f"{approved_count} of {required} approval(s) collected"


def _is_approval_ready(db: Session, entity_type: str, order: Any, workspace_id: int) -> bool:
    if entity_type == "purchase_order":
        from app.managers.purchase_order_manager import purchase_order_manager

        return purchase_order_manager._base_sections_confirmed(order)
    if entity_type == "expense_order":
        from app.managers.expense_order_manager import expense_order_manager

        return expense_order_manager.is_approvable(db, order)
    if entity_type == "transfer_order":
        from app.managers.transfer_order_manager import transfer_order_manager

        return transfer_order_manager._ready_for_approval(db, order, workspace_id)
    return False


def _section_gap_preview(db: Session, entity_type: str, order: Any) -> str:
    if entity_type == "purchase_order":
        from app.managers.purchase_order_manager import SECTION_CONFIRM_FIELDS

        gaps: List[str] = []
        for field, (_key, label) in SECTION_CONFIRM_FIELDS.items():
            if field == "invoice_confirmed":
                continue
            if not getattr(order, field, False):
                gaps.append(label)
        if gaps:
            return f"Confirm {', '.join(gaps)} before approvals can proceed"
        return "Complete remaining sections before approvals can proceed"
    if entity_type == "expense_order":
        from app.managers.expense_order_manager import expense_order_manager

        return expense_order_manager.approvability_gap_reason(db, order) or "Complete remaining details before approvals can proceed"
    if entity_type == "transfer_order":
        from app.managers.transfer_order_manager import transfer_order_manager

        if not transfer_order_manager._route_defined(order):
            return "Set source and destination before approvals can proceed"
        return "Add at least one item before approvals can proceed"


def _pending_approver_ids(db: Session, entity_type: str, entity_id: int, workspace_id: int) -> List[int]:
    if entity_type == "purchase_order":
        from app.dao.purchase_order_approver import purchase_order_approver_dao

        approvers = purchase_order_approver_dao.get_by_order(
            db, purchase_order_id=entity_id, workspace_id=workspace_id
        )
    elif entity_type == "transfer_order":
        from app.dao.transfer_order_approver import transfer_order_approver_dao

        approvers = transfer_order_approver_dao.get_by_order(
            db, transfer_order_id=entity_id, workspace_id=workspace_id
        )
    elif entity_type == "expense_order":
        from app.dao.expense_order_approver import expense_order_approver_dao

        approvers = expense_order_approver_dao.get_by_order(
            db, expense_order_id=entity_id, workspace_id=workspace_id
        )
    else:
        return []
    return [a.user_id for a in approvers if not a.approved]


def _has_approvers(db: Session, entity_type: str, entity_id: int, workspace_id: int) -> bool:
    _approved, required, _met = _approval_summary(db, entity_type, entity_id, workspace_id)
    return required > 0


def notify_approval_assigned(
    db: Session,
    *,
    workspace_id: int,
    entity_type: str,
    entity_id: int,
    actor_user_id: int,
    approver_user_id: int,
    approver_record_id: int,
    order: Any,
    ready_for_approval: bool = False,
) -> None:
    ref = format_order_ref(entity_type, entity_id)
    actor = _actor_name(db, actor_user_id)
    if ready_for_approval:
        approval_progress = build_approval_preview(db, entity_type, entity_id, workspace_id)
        preview = f"Assigned by {actor} · ready for your approval · {approval_progress}"
    else:
        preview = f"Assigned by {actor} on {ref}"
    _notify_user(
        db,
        workspace_id=workspace_id,
        recipient_user_id=approver_user_id,
        actor_user_id=actor_user_id,
        notification_type=APPROVAL_ASSIGNED,
        entity_type=entity_type,
        entity_id=entity_id,
        source_type=SOURCE_APPROVER,
        source_id=approver_record_id,
        preview=preview,
    )


def notify_approval_pending_for_order(
    db: Session,
    *,
    workspace_id: int,
    entity_type: str,
    entity_id: int,
    actor_user_id: int | None,
    exclude_user_ids: Optional[Set[int]] = None,
) -> None:
    exclude = exclude_user_ids or set()
    preview = build_approval_preview(db, entity_type, entity_id, workspace_id)
    for uid in _pending_approver_ids(db, entity_type, entity_id, workspace_id):
        if uid in exclude:
            continue
        _notify_user(
            db,
            workspace_id=workspace_id,
            recipient_user_id=uid,
            actor_user_id=actor_user_id,
            notification_type=APPROVAL_PENDING,
            entity_type=entity_type,
            entity_id=entity_id,
            source_type=SOURCE_ORDER,
            source_id=entity_id,
            preview=preview,
        )


def notify_section_confirm_needed(
    db: Session,
    *,
    workspace_id: int,
    entity_type: str,
    entity_id: int,
    actor_user_id: int,
    order: Any,
    reason: str | None = None,
) -> None:
    created_by = getattr(order, "created_by", None)
    if created_by is None:
        return
    preview = reason or _section_gap_preview(db, entity_type, order)
    _notify_user(
        db,
        workspace_id=workspace_id,
        recipient_user_id=created_by,
        actor_user_id=actor_user_id,
        notification_type=SECTION_CONFIRM,
        entity_type=entity_type,
        entity_id=entity_id,
        source_type=SOURCE_SECTION,
        source_id=entity_id,
        preview=preview,
    )


def notify_invoice_action(
    db: Session,
    *,
    workspace_id: int,
    entity_type: str,
    entity_id: int,
    actor_user_id: int,
    invoice_id: int,
    action: str,
    order: Any,
) -> None:
    ref = format_order_ref(entity_type, entity_id)
    if action == "draft":
        preview = "Linked payable invoice is in draft — confirm when details look correct"
        title_hint = "draft"
    else:
        preview = f"Invoice confirmed on {ref} — order locked"
        title_hint = "confirmed"

    recipient_ids: Set[int] = set(_pending_approver_ids(db, entity_type, entity_id, workspace_id))
    approved_count, required, _ = _approval_summary(db, entity_type, entity_id, workspace_id)
    if required > 0:
        if entity_type == "purchase_order":
            from app.dao.purchase_order_approver import purchase_order_approver_dao

            for a in purchase_order_approver_dao.get_by_order(
                db, purchase_order_id=entity_id, workspace_id=workspace_id
            ):
                recipient_ids.add(a.user_id)
        elif entity_type == "transfer_order":
            from app.dao.transfer_order_approver import transfer_order_approver_dao

            for a in transfer_order_approver_dao.get_by_order(
                db, transfer_order_id=entity_id, workspace_id=workspace_id
            ):
                recipient_ids.add(a.user_id)
        elif entity_type == "expense_order":
            from app.dao.expense_order_approver import expense_order_approver_dao

            for a in expense_order_approver_dao.get_by_order(
                db, expense_order_id=entity_id, workspace_id=workspace_id
            ):
                recipient_ids.add(a.user_id)

    created_by = getattr(order, "created_by", None)
    if created_by is not None:
        recipient_ids.add(created_by)

    full_preview = f"{title_hint}|{preview}"
    for uid in recipient_ids:
        _notify_user(
            db,
            workspace_id=workspace_id,
            recipient_user_id=uid,
            actor_user_id=actor_user_id,
            notification_type=INVOICE_ACTION,
            entity_type=entity_type,
            entity_id=entity_id,
            source_type=SOURCE_INVOICE,
            source_id=invoice_id,
            preview=full_preview,
        )


def handle_add_approver(
    db: Session,
    *,
    workspace_id: int,
    entity_type: str,
    entity_id: int,
    actor_user_id: int,
    approver_user_id: int,
    approver_record_id: int,
    order: Any,
) -> None:
    ready = _is_approval_ready(db, entity_type, order, workspace_id)
    notify_approval_assigned(
        db,
        workspace_id=workspace_id,
        entity_type=entity_type,
        entity_id=entity_id,
        actor_user_id=actor_user_id,
        approver_user_id=approver_user_id,
        approver_record_id=approver_record_id,
        order=order,
        ready_for_approval=ready,
    )
    if ready:
        notify_approval_pending_for_order(
            db,
            workspace_id=workspace_id,
            entity_type=entity_type,
            entity_id=entity_id,
            actor_user_id=actor_user_id,
            exclude_user_ids={actor_user_id, approver_user_id},
        )
    else:
        notify_section_confirm_needed(
            db,
            workspace_id=workspace_id,
            entity_type=entity_type,
            entity_id=entity_id,
            actor_user_id=actor_user_id,
            order=order,
        )


def handle_order_update_notifications(
    db: Session,
    *,
    workspace_id: int,
    entity_type: str,
    entity_id: int,
    actor_user_id: int,
    order: Any,
    was_ready: bool,
    section_was_unconfirmed: bool = False,
) -> None:
    now_ready = _is_approval_ready(db, entity_type, order, workspace_id)
    has_approvers = _has_approvers(db, entity_type, entity_id, workspace_id)

    if section_was_unconfirmed and has_approvers:
        notify_section_confirm_needed(
            db,
            workspace_id=workspace_id,
            entity_type=entity_type,
            entity_id=entity_id,
            actor_user_id=actor_user_id,
            order=order,
            reason="Approvals were reset — re-confirm sections before approving",
        )
        return

    if was_ready and not now_ready and has_approvers:
        notify_section_confirm_needed(
            db,
            workspace_id=workspace_id,
            entity_type=entity_type,
            entity_id=entity_id,
            actor_user_id=actor_user_id,
            order=order,
        )
        return

    if not was_ready and now_ready and has_approvers:
        notify_approval_pending_for_order(
            db,
            workspace_id=workspace_id,
            entity_type=entity_type,
            entity_id=entity_id,
            actor_user_id=actor_user_id,
        )


def detect_section_unconfirmed(entity_type: str, order: Any, update_dict: dict) -> bool:
    if entity_type == "purchase_order":
        from app.managers.purchase_order_manager import SECTION_CONFIRM_FIELDS

        fields = SECTION_CONFIRM_FIELDS
    else:
        return False

    for confirm_field in fields:
        if confirm_field not in update_dict:
            continue
        if not bool(update_dict[confirm_field]) and bool(getattr(order, confirm_field, False)):
            return True
    return False


approval_notification_service = {
    "handle_add_approver": handle_add_approver,
    "handle_order_update_notifications": handle_order_update_notifications,
    "notify_invoice_action": notify_invoice_action,
    "notify_section_confirm_needed": notify_section_confirm_needed,
    "detect_section_unconfirmed": detect_section_unconfirmed,
    "is_approval_ready": _is_approval_ready,
    "format_order_ref": format_order_ref,
}
