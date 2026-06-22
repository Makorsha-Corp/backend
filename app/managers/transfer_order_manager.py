"""Transfer Order Manager - business logic for transfer orders"""
from datetime import date, datetime
from decimal import Decimal
from typing import Any, List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.dao.factory import factory_dao
from app.dao.machine import machine_dao
from app.dao.profile import profile_dao
from app.dao.project_component import project_component_dao
from app.dao.transfer_order import transfer_order_dao, transfer_order_item_dao
from app.dao.transfer_order_approver import transfer_order_approver_dao
from app.dao.transfer_order_event import transfer_order_event_dao
from app.dao.workspace_member import workspace_member_dao
from app.managers.base_manager import BaseManager
from app.managers.to_inventory import post_transfer_order_inventory
from app.models.profile import Profile
from app.models.transfer_order import TransferOrder
from app.models.transfer_order_approver import TransferOrderApprover
from app.models.transfer_order_event import TransferOrderEvent
from app.models.transfer_order_item import TransferOrderItem
from app.schemas.transfer_order import (
    TransferOrderCreate,
    TransferOrderItemCreate,
    TransferOrderItemUpdate,
    TransferOrderUpdate,
)

ROUTE_UPDATE_FIELDS = frozenset({
    'source_location_type', 'source_location_id',
    'destination_location_type', 'destination_location_id',
    'order_date', 'description', 'note', 'expected_completion_date',
})
ORDER_UPDATE_LOG_FIELDS = {
    'source_location_type': 'Source type',
    'source_location_id': 'Source location',
    'destination_location_type': 'Destination type',
    'destination_location_id': 'Destination location',
    'order_date': 'Order date',
    'expected_completion_date': 'Expected completion',
    'description': 'Description',
    'note': 'Note',
    'required_approvals': 'Required approvals',
}
SECTION_CONFIRM_FIELDS = {
    'route_confirmed': ('route', 'Order details'),
    'items_confirmed': ('items', 'Transfer items'),
}
LOCATION_TYPE_LABELS = {
    'storage': 'Storage',
    'machine': 'Machine',
    'damaged': 'Damaged',
    'project': 'Project',
}


class TransferOrderManager(BaseManager[TransferOrder]):
    """Manager for transfer order business logic."""

    def __init__(self):
        super().__init__(TransferOrder)
        self.to_dao = transfer_order_dao
        self.item_dao = transfer_order_item_dao
        self.approver_dao = transfer_order_approver_dao
        self.event_dao = transfer_order_event_dao

    # ─── Helpers ─────────────────────────────────────────────────
    def _is_completed(self, record: TransferOrder) -> bool:
        return record.completed_at is not None

    def _base_sections_confirmed(self, record: TransferOrder) -> bool:
        return bool(record.route_confirmed and record.items_confirmed)

    def _route_defined(self, record: TransferOrder) -> bool:
        return bool(
            record.source_location_type
            and record.destination_location_type
            and record.source_location_id
            and record.destination_location_id
        )

    def _all_items_transferred(self, items: List[TransferOrderItem]) -> bool:
        if not items:
            return False
        return all(i.transferred_at is not None for i in items)

    def reset_approvals(
        self,
        session: Session,
        to_id: int,
        workspace_id: int,
        user_id: int,
        reason: str = 'Section unconfirmed',
    ) -> None:
        approvers = self.approver_dao.get_by_order(
            session, transfer_order_id=to_id, workspace_id=workspace_id
        )
        reset_count = 0
        for approver in approvers:
            if approver.approved:
                approver.approved = False
                approver.approved_at = None
                reset_count += 1
        if reset_count:
            session.flush()
            self.log_event(
                session, to_id, workspace_id, 'approvals_reset',
                f'{reason} ({reset_count} approval(s) cleared)',
                user_id,
            )

    def _format_scalar_value(self, field: str, value: Any) -> str:
        if value is None:
            return '—'
        if isinstance(value, date):
            return value.isoformat()
        if isinstance(value, Decimal):
            return str(int(value)) if value == value.to_integral_value() else str(value.normalize())
        text = str(value).strip()
        return text if text else '—'

    def _format_location_id(
        self, session: Session, workspace_id: int, location_type: str | None, location_id: Any,
    ) -> str:
        if location_id is None:
            return '—'
        ltype = (location_type or '').lower()
        if ltype == 'storage' or ltype == 'damaged':
            factory = factory_dao.get_by_id_and_workspace(
                session, id=location_id, workspace_id=workspace_id
            )
            return factory.name if factory else f'Factory #{location_id}'
        if ltype == 'machine':
            machine = machine_dao.get_by_id_and_workspace(
                session, id=location_id, workspace_id=workspace_id
            )
            return machine.name if machine else f'Machine #{location_id}'
        if ltype == 'project':
            component = project_component_dao.get_by_id_and_workspace(
                session, id=location_id, workspace_id=workspace_id
            )
            return component.name if component else f'Project component #{location_id}'
        return f'#{location_id}'

    def _format_field_value(
        self,
        session: Session,
        workspace_id: int,
        field: str,
        value: Any,
        *,
        source_type: str | None = None,
        destination_type: str | None = None,
    ) -> str:
        if field == 'source_location_type':
            return LOCATION_TYPE_LABELS.get(str(value).lower(), str(value)) if value else '—'
        if field == 'destination_location_type':
            return LOCATION_TYPE_LABELS.get(str(value).lower(), str(value)) if value else '—'
        if field == 'source_location_id':
            return self._format_location_id(session, workspace_id, source_type, value)
        if field == 'destination_location_id':
            return self._format_location_id(session, workspace_id, destination_type, value)
        if field == 'required_approvals':
            return 'All assigned' if value is None else str(value)
        return self._format_scalar_value(field, value)

    def _collect_field_changes(
        self,
        session: Session,
        workspace_id: int,
        record: TransferOrder,
        update_dict: dict,
    ) -> List[dict]:
        changes: List[dict] = []
        src_type = update_dict.get('source_location_type', record.source_location_type)
        dest_type = update_dict.get('destination_location_type', record.destination_location_type)
        for field, label in ORDER_UPDATE_LOG_FIELDS.items():
            if field not in update_dict:
                continue
            old_val = getattr(record, field)
            new_val = update_dict[field]
            if old_val == new_val:
                continue
            changes.append({
                'field': field,
                'label': label,
                'from_value': self._format_field_value(
                    session, workspace_id, field, old_val,
                    source_type=record.source_location_type,
                    destination_type=record.destination_location_type,
                ),
                'to_value': self._format_field_value(
                    session, workspace_id, field, new_val,
                    source_type=src_type,
                    destination_type=dest_type,
                ),
            })
        return changes

    def _log_field_change_event(
        self,
        session: Session,
        to_id: int,
        workspace_id: int,
        user_id: int,
        event_type: str,
        description: str,
        changes: List[dict],
    ) -> None:
        if not changes:
            return
        self.log_event(
            session, to_id, workspace_id, event_type, description, user_id,
            metadata={'changes': changes},
        )

    def _validate_section_confirm(
        self,
        record: TransferOrder,
        update_dict: dict,
        session: Session,
        workspace_id: int,
    ) -> None:
        if update_dict.get('route_confirmed') is True and not record.route_confirmed:
            src_type = update_dict.get('source_location_type', record.source_location_type)
            src_id = update_dict.get('source_location_id', record.source_location_id)
            dest_type = update_dict.get('destination_location_type', record.destination_location_type)
            dest_id = update_dict.get('destination_location_id', record.destination_location_id)
            if not (src_type and dest_type and src_id and dest_id):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail='Set source and destination before confirming order details',
                )
            if src_type == dest_type and src_id == dest_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail='Source and destination cannot be the same',
                )
        if update_dict.get('items_confirmed') is True and not record.items_confirmed:
            items = self.item_dao.get_by_order(
                session, transfer_order_id=record.id, workspace_id=workspace_id
            )
            if not items:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail='Add at least one line item before confirming',
                )

    def _guard_confirmed_updates(self, record: TransferOrder, update_dict: dict) -> None:
        if self._is_completed(record):
            blocked = set(update_dict.keys()) - {'note'}
            if blocked:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail='Transfer order is complete and cannot be edited',
                )
        if 'current_status_id' in update_dict:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Status is derived from workflow state — use Mark complete instead',
            )
        if record.route_confirmed and ROUTE_UPDATE_FIELDS.intersection(update_dict):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Order details are confirmed',
            )

    def _guard_item_mutations(self, session: Session, to: TransferOrder, workspace_id: int) -> None:
        if self._is_completed(to):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Transfer order is complete',
            )
        if to.items_confirmed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Transfer items are confirmed',
            )

    # ─── CRUD ────────────────────────────────────────────────────
    def create_transfer_order(
        self, session: Session, data: TransferOrderCreate,
        workspace_id: int, user_id: int
    ) -> TransferOrder:
        """Create transfer order with auto-generated number and nested items."""
        if (
            data.source_location_type == data.destination_location_type
            and data.source_location_id == data.destination_location_id
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Source and destination cannot be the same',
            )

        tr_number = self.to_dao.get_next_number(session, workspace_id=workspace_id)
        items_data = data.items or []
        to_dict = data.model_dump(exclude={'items'})
        to_dict['workspace_id'] = workspace_id
        to_dict['transfer_number'] = tr_number
        to_dict['created_by'] = user_id
        if not to_dict.get('order_date'):
            to_dict['order_date'] = date.today()

        to = self.to_dao.create(session, obj_in=to_dict)

        session.add(TransferOrderApprover(
            workspace_id=workspace_id,
            transfer_order_id=to.id,
            user_id=user_id,
            assigned_by=user_id,
            approved=False,
        ))
        session.flush()

        from app.utils.order_catalog_items import assert_unique_catalog_item_ids

        assert_unique_catalog_item_ids(
            session,
            workspace_id,
            items_data,
            get_item_id=lambda row: row.item_id,
        )

        for idx, item_data in enumerate(items_data, start=1):
            item_dict = item_data.model_dump()
            item_dict['workspace_id'] = workspace_id
            item_dict['transfer_order_id'] = to.id
            item_dict['line_number'] = idx
            self.item_dao.create(session, obj_in=item_dict)

        self.log_event(session, to.id, workspace_id, 'created', 'Transfer order created', user_id)
        return to

    def update_transfer_order(
        self, session: Session, to_id: int, data: TransferOrderUpdate,
        workspace_id: int, user_id: int
    ) -> TransferOrder:
        """Update transfer order."""
        record = self.to_dao.get_by_id_and_workspace(session, id=to_id, workspace_id=workspace_id)
        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Transfer order with ID {to_id} not found",
            )

        update_dict = data.model_dump(exclude_unset=True, exclude_none=True)
        self._guard_confirmed_updates(record, update_dict)
        self._validate_section_confirm(record, update_dict, session, workspace_id)

        section_unconfirmed = False
        for confirm_field, (section_key, label) in SECTION_CONFIRM_FIELDS.items():
            if confirm_field not in update_dict:
                continue
            new_confirmed = bool(update_dict[confirm_field])
            old_confirmed = bool(getattr(record, confirm_field, False))
            if new_confirmed != old_confirmed:
                if not new_confirmed:
                    section_unconfirmed = True
                event_suffix = 'confirmed' if new_confirmed else 'unconfirmed'
                self.log_event(
                    session, to_id, workspace_id,
                    f'{section_key}_{event_suffix}',
                    f'{label} {event_suffix}',
                    user_id,
                )

        if section_unconfirmed:
            self.reset_approvals(session, to_id, workspace_id, user_id)

        changes = self._collect_field_changes(session, workspace_id, record, update_dict)
        if changes:
            self._log_field_change_event(
                session, to_id, workspace_id, user_id,
                'updated', 'Order details updated', changes,
            )

        update_dict['updated_by'] = user_id
        return self.to_dao.update(session, db_obj=record, obj_in=update_dict)

    def get_transfer_order(self, session: Session, to_id: int, workspace_id: int) -> TransferOrder:
        record = self.to_dao.get_by_id_and_workspace(session, id=to_id, workspace_id=workspace_id)
        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Transfer order with ID {to_id} not found",
            )
        return record

    def list_transfer_orders(
        self, session: Session, workspace_id: int,
        skip: int = 0, limit: int = 100
    ) -> List[TransferOrder]:
        return self.to_dao.get_by_workspace(
            session, workspace_id=workspace_id,
            skip=skip, limit=limit
        )

    def delete_transfer_order(self, session: Session, to_id: int, workspace_id: int) -> None:
        record = self.to_dao.get_by_id_and_workspace(session, id=to_id, workspace_id=workspace_id)
        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Transfer order with ID {to_id} not found",
            )
        if self._is_completed(record):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Cannot delete a completed transfer order',
            )

        line_items = self.item_dao.get_by_order(
            session, transfer_order_id=to_id, workspace_id=workspace_id
        )
        for line_item in line_items:
            session.delete(line_item)
        session.flush()
        session.delete(record)
        session.flush()

    def mark_order_complete(
        self,
        session: Session,
        to_id: int,
        workspace_id: int,
        user_id: int,
    ) -> TransferOrder:
        record = self.get_transfer_order(session, to_id, workspace_id)
        if self._is_completed(record):
            return record

        if not self._base_sections_confirmed(record):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Confirm order details and transfer items before completing',
            )
        if not self.approvals_met(session, record):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Required approvals are not met',
            )

        items = self.item_dao.get_by_order(
            session, transfer_order_id=record.id, workspace_id=workspace_id
        )
        if not self._all_items_transferred(items):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='All line items must be transferred before marking complete',
            )

        lines_posted = post_transfer_order_inventory(
            session, record, items, workspace_id, user_id
        )

        record.completed_at = datetime.utcnow()
        record.completed_by = user_id
        record.updated_by = user_id
        session.flush()

        if lines_posted > 0:
            self.log_event(
                session, to_id, workspace_id, 'inventory_posted',
                f'{lines_posted} line(s) posted to inventory',
                user_id,
                metadata={'lines_posted': lines_posted},
            )
        self.log_event(
            session, to_id, workspace_id, 'order_completed',
            'Transfer order marked complete', user_id,
        )
        return record

    # ─── Transfer Order Items ──────────────────────────────────
    def _ensure_catalog_item_not_on_to(
        self,
        session: Session,
        to_id: int,
        item_id: int,
        workspace_id: int,
        *,
        exclude_item_id: Optional[int] = None,
    ) -> None:
        from app.utils.order_catalog_items import catalog_item_already_on_order_detail

        for line in self.item_dao.get_by_order(
            session, transfer_order_id=to_id, workspace_id=workspace_id
        ):
            if line.item_id == item_id and line.id != exclude_item_id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=catalog_item_already_on_order_detail(
                        session, item_id=item_id, workspace_id=workspace_id
                    ),
                )

    def add_item(
        self, session: Session, to_id: int, data: TransferOrderItemCreate,
        workspace_id: int, user_id: int,
    ) -> TransferOrderItem:
        to = self.get_transfer_order(session, to_id, workspace_id)
        self._guard_item_mutations(session, to, workspace_id)

        self._ensure_catalog_item_not_on_to(session, to_id, data.item_id, workspace_id)

        existing = self.item_dao.get_by_order(session, transfer_order_id=to_id, workspace_id=workspace_id)
        next_line = max((i.line_number for i in existing), default=0) + 1

        item_dict = data.model_dump()
        item_dict['workspace_id'] = workspace_id
        item_dict['transfer_order_id'] = to_id
        item_dict['line_number'] = next_line
        item = self.item_dao.create(session, obj_in=item_dict)
        self.log_event(
            session, to_id, workspace_id, 'item_added',
            f'Line {next_line} added', user_id,
            metadata={'item_id': item.item_id, 'line_number': next_line},
        )
        return item

    def update_item(
        self, session: Session, item_id: int, data: TransferOrderItemUpdate,
        workspace_id: int, user_id: int
    ) -> TransferOrderItem:
        record = self.item_dao.get_by_id_and_workspace(session, id=item_id, workspace_id=workspace_id)
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transfer order item not found")

        to = self.get_transfer_order(session, record.transfer_order_id, workspace_id)
        if self._is_completed(to):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Transfer order is complete',
            )

        update_dict = data.model_dump(exclude_unset=True, exclude_none=True)

        if 'quantity' in update_dict and to.items_confirmed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Transfer items are confirmed',
            )

        if 'transferred_at' in update_dict and update_dict['transferred_at'] is not None:
            if not self._base_sections_confirmed(to):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail='Confirm order details and items before recording transfers',
                )
            if not self.approvals_met(session, to):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail='Required approvals are not met',
                )

        if 'approved' in update_dict and update_dict['approved'] and not record.approved:
            from sqlalchemy.sql import func
            update_dict['approved_by'] = user_id
            update_dict['approved_at'] = func.now()

        was_transferred = record.transferred_at is not None
        updated = self.item_dao.update(session, db_obj=record, obj_in=update_dict)

        if 'transferred_at' in update_dict:
            if update_dict['transferred_at'] and not was_transferred:
                self.log_event(
                    session, to.id, workspace_id, 'transfer_recorded',
                    f'Line {updated.line_number} transfer recorded', user_id,
                    metadata={'line_number': updated.line_number, 'item_id': updated.item_id},
                )
            elif update_dict['transferred_at'] is None and was_transferred:
                self.log_event(
                    session, to.id, workspace_id, 'transfer_cleared',
                    f'Line {updated.line_number} transfer cleared', user_id,
                )

        return updated

    def remove_item(self, session: Session, item_id: int, workspace_id: int, user_id: int) -> TransferOrderItem:
        record = self.item_dao.get_by_id_and_workspace(session, id=item_id, workspace_id=workspace_id)
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transfer order item not found")

        to = self.get_transfer_order(session, record.transfer_order_id, workspace_id)
        self._guard_item_mutations(session, to, workspace_id)

        line_number = record.line_number
        session.delete(record)
        session.flush()
        self.log_event(
            session, to.id, workspace_id, 'item_removed',
            f'Line {line_number} removed', user_id,
        )
        return record

    def get_items(self, session: Session, to_id: int, workspace_id: int) -> List[TransferOrderItem]:
        self.get_transfer_order(session, to_id, workspace_id)
        return self.item_dao.get_by_order(session, transfer_order_id=to_id, workspace_id=workspace_id)

    # ─── Approvers ─────────────────────────────────────────────
    def list_approvers(
        self, session: Session, to_id: int, workspace_id: int
    ) -> List[Tuple[TransferOrderApprover, Optional[Profile], Optional[str]]]:
        self.get_transfer_order(session, to_id, workspace_id)
        approvers = self.approver_dao.get_by_order(
            session, transfer_order_id=to_id, workspace_id=workspace_id
        )
        result: List[Tuple[TransferOrderApprover, Optional[Profile], Optional[str]]] = []
        for approver in approvers:
            profile = profile_dao.get(session, id=approver.user_id)
            member = workspace_member_dao.get_by_workspace_and_user(
                session, workspace_id=workspace_id, user_id=approver.user_id
            )
            result.append((approver, profile, member.position if member else None))
        return result

    def approval_summary(self, session: Session, to: TransferOrder) -> Tuple[int, int, bool]:
        approvers = self.approver_dao.get_by_order(
            session, transfer_order_id=to.id, workspace_id=to.workspace_id
        )
        approved_count = sum(1 for a in approvers if a.approved)
        if to.required_approvals is not None:
            required = to.required_approvals
        elif len(approvers) > 0:
            required = len(approvers)
        else:
            required = 0
        return approved_count, required, approved_count >= required

    def approvals_met(self, session: Session, to: TransferOrder) -> bool:
        return self.approval_summary(session, to)[2]

    def add_approver(
        self, session: Session, to_id: int, user_id: int, workspace_id: int, assigned_by: int
    ) -> TransferOrderApprover:
        self.get_transfer_order(session, to_id, workspace_id)
        member = workspace_member_dao.get_by_workspace_and_user(
            session, workspace_id=workspace_id, user_id=user_id
        )
        if not member or member.status != 'active':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='User is not an active member of this workspace',
            )
        existing = self.approver_dao.get_by_order_and_user(
            session, transfer_order_id=to_id, user_id=user_id, workspace_id=workspace_id
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail='User is already an approver for this order',
            )
        obj = TransferOrderApprover(
            workspace_id=workspace_id,
            transfer_order_id=to_id,
            user_id=user_id,
            assigned_by=assigned_by,
            approved=False,
        )
        session.add(obj)
        session.flush()
        profile = profile_dao.get(session, id=user_id)
        user_name = profile.name if profile else f'User #{user_id}'
        self.log_event(
            session, to_id, workspace_id, 'approver_added',
            f'Added {user_name} as approver',
            assigned_by,
            metadata={'user_id': user_id, 'user_name': user_name},
        )
        return obj

    def remove_approver(
        self, session: Session, to_id: int, user_id: int, workspace_id: int,
        performed_by: Optional[int] = None,
    ) -> None:
        rec = self.approver_dao.get_by_order_and_user(
            session, transfer_order_id=to_id, user_id=user_id, workspace_id=workspace_id
        )
        if not rec:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Approver not found')
        profile = profile_dao.get(session, id=user_id)
        user_name = profile.name if profile else f'User #{user_id}'
        session.delete(rec)
        session.flush()
        self.log_event(
            session, to_id, workspace_id, 'approver_removed',
            f'Removed {user_name} as approver',
            performed_by,
            metadata={'user_id': user_id, 'user_name': user_name},
        )

    def set_approval(
        self, session: Session, to_id: int, user_id: int, workspace_id: int, approved: bool
    ) -> TransferOrderApprover:
        rec = self.approver_dao.get_by_order_and_user(
            session, transfer_order_id=to_id, user_id=user_id, workspace_id=workspace_id
        )
        if not rec:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail='You are not an assigned approver for this order',
            )
        to = self.get_transfer_order(session, to_id, workspace_id)
        if approved and not self._base_sections_confirmed(to):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Confirm order details and transfer items before approving',
            )
        rec.approved = approved
        rec.approved_at = datetime.utcnow() if approved else None
        session.flush()
        self.log_event(
            session, to_id, workspace_id,
            'approved' if approved else 'approval_withdrawn',
            'Approved transfer order' if approved else 'Withdrew approval',
            user_id,
        )
        return rec

    # ─── Events ────────────────────────────────────────────────
    def log_event(
        self, session: Session, to_id: int, workspace_id: int,
        event_type: str, description: str, performed_by: Optional[int] = None,
        metadata: dict | None = None,
    ) -> TransferOrderEvent:
        ev = TransferOrderEvent(
            workspace_id=workspace_id,
            transfer_order_id=to_id,
            event_type=event_type,
            description=description,
            metadata_json=metadata,
            performed_by=performed_by,
        )
        session.add(ev)
        session.flush()
        return ev

    def list_events(
        self, session: Session, to_id: int, workspace_id: int
    ) -> List[Tuple[TransferOrderEvent, Optional[Profile]]]:
        self.get_transfer_order(session, to_id, workspace_id)
        events = self.event_dao.get_by_order(
            session, transfer_order_id=to_id, workspace_id=workspace_id
        )
        return [
            (e, profile_dao.get(session, id=e.performed_by) if e.performed_by else None)
            for e in events
        ]


transfer_order_manager = TransferOrderManager()
