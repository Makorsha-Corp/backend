"""Work Order Manager - business logic for work orders"""
from datetime import date, datetime
from decimal import Decimal
from typing import Any, List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.managers.base_manager import BaseManager
from app.managers.inventory_movements import (
    item_name, post_stock_in, post_stock_out, ensure_machine_item, get_machine_unit_cost,
)
from app.managers.machine_activity_manager import machine_activity_manager
from app.managers.machine_manager import machine_manager
from app.managers.project_component_activity_manager import project_component_activity_manager
from app.managers.work_order_template_manager import work_order_template_manager
from app.models.work_order import WorkOrder
from app.models.work_order_approver import WorkOrderApprover
from app.models.work_order_event import WorkOrderEvent
from app.models.work_order_item import WorkOrderItem
from app.models.profile import Profile
from app.models.enums import WorkOrderPriorityEnum, WorkOrderStatusEnum, MachineEventTypeEnum
from app.schemas.work_order import WorkOrderCreate, WorkOrderUpdate, WorkOrderSheetEntryCreate
from app.schemas.work_order_item import WorkOrderItemCreate, WorkOrderItemUpdate
from app.schemas.work_order_template import WorkOrderFromTemplateCreate
from app.schemas.machine_event import MachineEventCreate
from app.dao.work_order import work_order_dao
from app.dao.work_order_item import work_order_item_dao
from app.dao.work_order_approver import work_order_approver_dao
from app.dao.work_order_event import work_order_event_dao
from app.dao.work_order_type import work_order_type_dao
from app.dao.factory import factory_dao
from app.dao.account import account_dao
from app.dao.item import item_dao
from app.dao.machine import machine_dao
from app.dao.machine_item import machine_item_dao
from app.dao.profile import profile_dao
from app.dao.workspace_member import workspace_member_dao

DETAILS_FIELDS = frozenset({
    'work_order_type_id', 'title', 'description', 'priority', 'machine_id', 'project_component_id',
    'cost', 'account_id',
})
ORDER_UPDATE_LOG_FIELDS = {
    'work_order_type_id': 'Work order type',
    'title': 'Title',
    'description': 'Description',
    'priority': 'Priority',
    'machine_id': 'Machine',
    'project_component_id': 'Project component',
    'start_date': 'Start date',
    'end_date': 'End date',
    'cost': 'Cost',
    'account_id': 'Account',
    'assigned_to': 'Assigned to',
    'required_approvals': 'Required approvals',
    'completion_notes': 'Completion notes',
}


class WorkOrderManager(BaseManager[WorkOrder]):
    """Manager for work order business logic."""

    def __init__(self):
        super().__init__(WorkOrder)
        self.wo_dao = work_order_dao
        self.item_dao = work_order_item_dao
        self.approver_dao = work_order_approver_dao
        self.event_dao = work_order_event_dao

    # ─── Helpers ─────────────────────────────────────────────────
    def _is_locked(self, record: WorkOrder) -> bool:
        return record.status in (WorkOrderStatusEnum.COMPLETED.value, WorkOrderStatusEnum.VOIDED.value)

    def _has_recorded_approvals(self, session: Session, wo_id: int, workspace_id: int) -> bool:
        approvers = self.approver_dao.get_by_order(session, work_order_id=wo_id, workspace_id=workspace_id)
        return any(a.approved for a in approvers)

    def is_approvable(self, session: Session, wo: WorkOrder) -> bool:
        return bool((wo.title or '').strip()) and wo.factory_id is not None

    def approvability_gap_reason(self, session: Session, wo: WorkOrder) -> str | None:
        if not (wo.title or '').strip():
            return 'Add a title before approvals can proceed'
        if wo.factory_id is None:
            return 'Set a factory before approvals can proceed'
        return None

    def _format_scalar_value(self, field: str, value: Any) -> str:
        if value is None:
            return '—'
        if isinstance(value, date):
            return value.isoformat()
        if isinstance(value, Decimal):
            return str(int(value)) if value == value.to_integral_value() else str(value.normalize())
        if hasattr(value, 'value'):
            return str(value.value)
        text = str(value).strip()
        return text if text else '—'

    def _collect_field_changes(self, session: Session, record: WorkOrder, update_dict: dict) -> List[dict]:
        changes: List[dict] = []
        for field, label in ORDER_UPDATE_LOG_FIELDS.items():
            if field not in update_dict:
                continue
            old_val = getattr(record, field)
            new_val = update_dict[field]
            if old_val == new_val:
                continue
            if field == 'work_order_type_id':
                from_display = self._work_order_type_name(session, old_val, record.workspace_id)
                to_display = self._work_order_type_name(session, new_val, record.workspace_id)
            else:
                from_display = self._format_scalar_value(field, old_val)
                to_display = self._format_scalar_value(field, new_val)
            changes.append({
                'field': field,
                'label': label,
                'from_value': from_display,
                'to_value': to_display,
            })
        return changes

    def _work_order_type_name(self, session: Session, type_id: Optional[int], workspace_id: int) -> str:
        if type_id is None:
            return '—'
        wo_type = work_order_type_dao.get_by_id_and_workspace(session, id=type_id, workspace_id=workspace_id)
        return wo_type.name if wo_type else f'#{type_id}'

    def resolve_invoice_account_id(self, record: WorkOrder) -> int:
        if record.account_id:
            return record.account_id
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail='Set an account on the work order before creating an invoice',
        )

    # ─── CRUD ────────────────────────────────────────────────────
    def create_work_order(
        self, session: Session, data: WorkOrderCreate,
        workspace_id: int, user_id: int
    ) -> WorkOrder:
        """Create work order with auto-generated number."""
        factory = factory_dao.get_by_id_and_workspace(
            session, id=data.factory_id, workspace_id=workspace_id
        )
        if not factory:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Factory with ID {data.factory_id} not found"
            )
        wo_type = work_order_type_dao.get_by_id_and_workspace(
            session, id=data.work_order_type_id, workspace_id=workspace_id
        )
        if not wo_type:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Work order type with ID {data.work_order_type_id} not found"
            )
        if data.account_id is not None:
            account = account_dao.get_by_id_and_workspace(session, id=data.account_id, workspace_id=workspace_id)
            if not account:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Account with ID {data.account_id} not found")

        wo_number = self.wo_dao.get_next_number(session, workspace_id=workspace_id)

        wo_dict = data.model_dump()
        wo_dict['workspace_id'] = workspace_id
        wo_dict['work_order_number'] = wo_number
        wo_dict['created_by'] = user_id
        wo_dict['status'] = WorkOrderStatusEnum.DRAFT.value

        wo = self.wo_dao.create(session, obj_in=wo_dict)
        self.log_event(session, wo.id, workspace_id, 'created', f'Work order {wo.work_order_number} created', user_id)
        # No approvers assigned yet ⇒ trivially approved; auto-advance immediately.
        self._recompute_approval_status(session, wo, workspace_id, user_id)
        return wo

    def create_work_order_from_template(
        self, session: Session, template_id: int, workspace_id: int, user_id: int,
        overrides: WorkOrderFromTemplateCreate,
    ) -> WorkOrder:
        """Generate a work order from a saved template — the template supplies type,
        priority, parts, billing, and default approvers; the caller only has to say
        which machine it's for (parts sourcing resolves to that machine's own factory)."""
        template = work_order_template_manager.get_template(session, template_id, workspace_id)
        if not template.is_active:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Template is inactive')

        machine = machine_dao.get_by_id_and_workspace(session, id=overrides.machine_id, workspace_id=workspace_id)
        if not machine:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Machine with ID {overrides.machine_id} not found")
        factory_id = machine.factory_id

        type_name = template.work_order_type_name or 'Maintenance'
        wo = self.create_work_order(
            session,
            data=WorkOrderCreate(
                work_order_type_id=template.work_order_type_id,
                title=overrides.title or f'{type_name} — {machine.name}',
                description=overrides.description or template.description,
                priority=template.priority,
                factory_id=factory_id,
                machine_id=machine.id,
                start_date=overrides.start_date,
                uses_inventory=template.uses_inventory,
                account_id=template.account_id,
                cost=template.cost,
                assigned_to=overrides.assigned_to or template.assigned_to,
            ),
            workspace_id=workspace_id, user_id=user_id,
        )
        wo.work_order_template_id = template.id
        session.flush()

        if template.uses_inventory:
            tpl_items = work_order_template_manager.get_items(session, template_id, workspace_id)
            for ti in tpl_items:
                self.add_item(
                    session,
                    data=WorkOrderItemCreate(
                        work_order_id=wo.id, item_id=ti.item_id, quantity=ti.quantity,
                        uses_inventory=True, source_location_type='storage', source_location_id=factory_id,
                        action_type=ti.action_type, replaced_item_id=ti.replaced_item_id, notes=ti.notes,
                    ),
                    workspace_id=workspace_id, user_id=user_id,
                )

        if template.requires_approval:
            tpl_approvers = work_order_template_manager.get_approvers(session, template_id, workspace_id)
            for a in tpl_approvers:
                try:
                    self.add_approver(
                        session, wo_id=wo.id, user_id=a.user_id, workspace_id=workspace_id,
                        assigned_by=user_id, approver_slot=getattr(a, 'approver_slot', None),
                    )
                except HTTPException:
                    continue

        self.log_event(
            session, wo.id, workspace_id, 'created_from_template',
            f'Generated from template "{template.template_name}"', user_id,
            metadata={'work_order_template_id': template.id},
        )
        return wo

    def update_work_order(
        self, session: Session, wo_id: int, data: WorkOrderUpdate,
        workspace_id: int, user_id: int
    ) -> WorkOrder:
        """Update work order. Handles field-change logging + approval reset."""
        record = self.wo_dao.get_by_id_and_workspace(session, id=wo_id, workspace_id=workspace_id)
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Work order with ID {wo_id} not found")
        if record.is_deleted:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot update a deleted work order")

        update_dict = data.model_dump(exclude_unset=True, exclude_none=True)
        # These fields are nullable-by-design (clearing them is a real, meaningful update —
        # e.g. "no target", "internal work", "require all assigned approvers") — exclude_none
        # above would otherwise silently drop an explicit null-out request. machine_id and
        # project_component_id are additionally mutually exclusive: setting one always clears
        # the other server-side.
        explicit_fields = data.model_fields_set
        if 'machine_id' in explicit_fields:
            update_dict['machine_id'] = data.machine_id
            update_dict['project_component_id'] = None
        elif 'project_component_id' in explicit_fields:
            update_dict['project_component_id'] = data.project_component_id
            update_dict['machine_id'] = None
        if 'account_id' in explicit_fields:
            update_dict['account_id'] = data.account_id
        if 'required_approvals' in explicit_fields:
            update_dict['required_approvals'] = data.required_approvals
        if not update_dict:
            record._approvals_reset = False
            return record

        if self._is_locked(record):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Work order is {record.status.lower()} and cannot be edited",
            )
        if record.status == WorkOrderStatusEnum.IN_PROGRESS.value and DETAILS_FIELDS.intersection(update_dict):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Work order is in progress — structural fields (target, type, cost, account) are locked",
            )
        if 'account_id' in update_dict and update_dict['account_id'] is not None:
            account = account_dao.get_by_id_and_workspace(session, id=update_dict['account_id'], workspace_id=workspace_id)
            if not account:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Selected account not found")
        if 'work_order_type_id' in update_dict:
            wo_type = work_order_type_dao.get_by_id_and_workspace(
                session, id=update_dict['work_order_type_id'], workspace_id=workspace_id
            )
            if not wo_type:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Selected work order type not found")

        changes = self._collect_field_changes(session, record, update_dict)

        approvals_reset = False
        if (
            DETAILS_FIELDS.intersection(update_dict)
            and record.status == WorkOrderStatusEnum.DRAFT.value
            and self._has_recorded_approvals(session, wo_id, workspace_id)
        ):
            self.reset_approvals(session, wo_id, workspace_id, user_id, reason='Order details edited')
            approvals_reset = True

        if changes:
            self.log_event(
                session, wo_id, workspace_id, 'updated', 'Order details updated', user_id,
                metadata={'changes': changes},
            )

        update_dict['updated_by'] = user_id
        updated = self.wo_dao.update(session, db_obj=record, obj_in=update_dict)
        self._recompute_approval_status(session, updated, workspace_id, user_id)
        updated._approvals_reset = approvals_reset
        return updated

    def get_work_order(self, session: Session, wo_id: int, workspace_id: int) -> WorkOrder:
        record = self.wo_dao.get_by_id_and_workspace(session, id=wo_id, workspace_id=workspace_id)
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Work order with ID {wo_id} not found")
        return record

    def list_work_orders(
        self, session: Session, workspace_id: int,
        work_order_type_id: Optional[int] = None,
        wo_status: Optional[WorkOrderStatusEnum] = None,
        priority: Optional[WorkOrderPriorityEnum] = None,
        factory_id: Optional[int] = None,
        machine_id: Optional[int] = None,
        skip: int = 0, limit: int = 100
    ) -> List[WorkOrder]:
        return self.wo_dao.get_by_workspace(
            session, workspace_id=workspace_id,
            work_order_type_id=work_order_type_id, status=wo_status, priority=priority,
            factory_id=factory_id, machine_id=machine_id,
            skip=skip, limit=limit
        )

    def delete_work_order(self, session: Session, wo_id: int, workspace_id: int, user_id: int) -> WorkOrder:
        record = self.wo_dao.get_by_id_and_workspace(session, id=wo_id, workspace_id=workspace_id)
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Work order with ID {wo_id} not found")
        if record.is_deleted:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Work order is already deleted")
        if record.status != WorkOrderStatusEnum.DRAFT.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only a draft work order can be deleted — void it instead",
            )
        return self.wo_dao.soft_delete(session, db_obj=record, deleted_by=user_id)

    # ─── Approvals ───────────────────────────────────────────────
    def list_approvers(
        self, session: Session, wo_id: int, workspace_id: int
    ) -> List[Tuple[WorkOrderApprover, Optional[Profile], Optional[str]]]:
        self.get_work_order(session, wo_id, workspace_id)
        approvers = self.approver_dao.get_by_order(session, work_order_id=wo_id, workspace_id=workspace_id)
        result: List[Tuple[WorkOrderApprover, Optional[Profile], Optional[str]]] = []
        for approver in approvers:
            profile = profile_dao.get(session, id=approver.user_id)
            member = workspace_member_dao.get_by_workspace_and_user(
                session, workspace_id=workspace_id, user_id=approver.user_id
            )
            result.append((approver, profile, member.position if member else None))
        return result

    def approval_summary(self, session: Session, wo: WorkOrder) -> Tuple[int, int, bool]:
        approvers = self.approver_dao.get_by_order(session, work_order_id=wo.id, workspace_id=wo.workspace_id)
        approved_count = sum(1 for a in approvers if a.approved)
        if wo.required_approvals is not None:
            required = wo.required_approvals
        else:
            required = len(approvers)
        return approved_count, required, approved_count >= required

    def approvals_met(self, session: Session, wo: WorkOrder) -> bool:
        return self.approval_summary(session, wo)[2]

    def reset_approvals(
        self, session: Session, wo_id: int, workspace_id: int, user_id: int,
        reason: str = 'Section unconfirmed',
    ) -> None:
        approvers = self.approver_dao.get_by_order(session, work_order_id=wo_id, workspace_id=workspace_id)
        reset_count = 0
        for approver in approvers:
            if approver.approved:
                approver.approved = False
                approver.approved_at = None
                reset_count += 1
        if reset_count:
            session.flush()
            self.log_event(
                session, wo_id, workspace_id, 'approvals_reset',
                f'{reason} ({reset_count} approval(s) cleared)', user_id,
            )

    def _recompute_approval_status(
        self, session: Session, wo: WorkOrder, workspace_id: int, actor_user_id: Optional[int],
    ) -> None:
        """Approvals no longer gate a visible status — they gate `start_work_order` directly
        (see `approvals_met`). This just stamps `approved_by`/`approved_at` informationally,
        the first time the order clears its approval requirement, and clears them if it stops
        being met (e.g. an edit reset recorded approvals)."""
        if wo.status != WorkOrderStatusEnum.DRAFT.value:
            return
        _approved_count, required, met = self.approval_summary(session, wo)

        if met and wo.approved_at is None:
            wo.approved_by = actor_user_id
            wo.approved_at = datetime.utcnow()
            session.flush()
            self.log_event(
                session, wo.id, workspace_id,
                'auto_approved' if required == 0 else 'approved',
                'Ready to start — no approval required' if required == 0 else 'All required approvals collected',
                actor_user_id,
            )
        elif not met and wo.approved_at is not None:
            wo.approved_by = None
            wo.approved_at = None
            session.flush()
            self.log_event(
                session, wo.id, workspace_id, 'approval_revoked',
                'No longer meets approval requirements', actor_user_id,
            )

    def add_approver(
        self, session: Session, wo_id: int, user_id: int, workspace_id: int, assigned_by: int,
        approver_slot: str | None = None,
    ) -> WorkOrderApprover:
        wo = self.get_work_order(session, wo_id, workspace_id)
        if self._is_locked(wo):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Work order is {wo.status.lower()}")
        member = workspace_member_dao.get_by_workspace_and_user(session, workspace_id=workspace_id, user_id=user_id)
        if not member or member.status != 'active':
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='User is not an active member of this workspace')
        existing = self.approver_dao.get_by_order_and_user(session, work_order_id=wo_id, user_id=user_id, workspace_id=workspace_id)
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='User is already an approver for this order')

        obj = WorkOrderApprover(
            workspace_id=workspace_id, work_order_id=wo_id, user_id=user_id,
            assigned_by=assigned_by, approved=False, approver_slot=approver_slot,
        )
        session.add(obj)
        session.flush()
        profile = profile_dao.get(session, id=user_id)
        user_name = profile.name if profile else f'User #{user_id}'
        self.log_event(
            session, wo_id, workspace_id, 'approver_added', f'Added {user_name} as approver', assigned_by,
            metadata={'user_id': user_id, 'user_name': user_name},
        )
        self._recompute_approval_status(session, wo, workspace_id, assigned_by)
        return obj

    def remove_approver(
        self, session: Session, wo_id: int, user_id: int, workspace_id: int,
        performed_by: Optional[int] = None,
    ) -> None:
        wo = self.get_work_order(session, wo_id, workspace_id)
        if self._is_locked(wo):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Work order is {wo.status.lower()}")
        rec = self.approver_dao.get_by_order_and_user(session, work_order_id=wo_id, user_id=user_id, workspace_id=workspace_id)
        if not rec:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Approver not found')
        profile = profile_dao.get(session, id=user_id)
        user_name = profile.name if profile else f'User #{user_id}'
        session.delete(rec)
        session.flush()
        self.log_event(
            session, wo_id, workspace_id, 'approver_removed', f'Removed {user_name} as approver', performed_by,
            metadata={'user_id': user_id, 'user_name': user_name},
        )
        self._recompute_approval_status(session, wo, workspace_id, performed_by)

    def set_approval(
        self, session: Session, wo_id: int, user_id: int, workspace_id: int, approved: bool
    ) -> WorkOrderApprover:
        rec = self.approver_dao.get_by_order_and_user(session, work_order_id=wo_id, user_id=user_id, workspace_id=workspace_id)
        if not rec:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='You are not an assigned approver for this order')
        wo = self.get_work_order(session, wo_id, workspace_id)
        if self._is_locked(wo):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Work order is {wo.status.lower()}")
        if approved and not self.is_approvable(session, wo):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=self.approvability_gap_reason(session, wo) or 'Order is not ready for approval',
            )
        rec.approved = approved
        rec.approved_at = datetime.utcnow() if approved else None
        session.flush()
        self.log_event(
            session, wo_id, workspace_id,
            'approved' if approved else 'approval_withdrawn',
            'Approved work order' if approved else 'Withdrew approval', user_id,
        )
        self._recompute_approval_status(session, wo, workspace_id, user_id)
        return rec

    # ─── Lifecycle: start / complete / void ──────────────────────
    def _consume_item(self, session: Session, wo: WorkOrder, item: WorkOrderItem, user_id: int) -> None:
        if not item.uses_inventory or item.consumed_at is not None:
            return
        if not item.source_location_type or not item.source_location_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f'Item line {item.id} uses inventory but has no source location set',
            )
        qty = int(item.quantity) if item.quantity == item.quantity.to_integral_value() else None
        if qty is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f'Item line {item.id} has a fractional quantity; inventory consumption requires whole units',
            )
        name = item_name(session, item.item_id, wo.workspace_id)
        unit_cost = post_stock_out(
            session,
            location_type=item.source_location_type,
            location_id=item.source_location_id,
            item_id=item.item_id,
            qty=qty,
            transaction_type='consumption',
            source_type='work_order',
            source_id=wo.id,
            notes=f'{wo.work_order_number} — {name}',
            workspace_id=wo.workspace_id,
            user_id=user_id,
            activity_event_type='consumption',
            activity_description=f'Consumed for work order {wo.work_order_number}: {qty} units of {name}',
        )
        item.consumed_at = datetime.utcnow()
        item.consumed_by = user_id
        item.unit_cost = unit_cost
        item.total_cost = (unit_cost * Decimal(qty)).quantize(Decimal('0.01'))
        session.flush()

        source_label = (
            f"machine #{item.source_location_id}" if item.source_location_type == 'machine' else 'storage'
        )
        if wo.machine_id:
            machine_activity_manager.log_event(
                session, wo.machine_id, wo.workspace_id, 'work_order_item_used',
                f'Used {qty} {name} from {source_label} for work order {wo.work_order_number}',
                performed_by=user_id, metadata={'item_id': item.item_id, 'item_name': name, 'quantity': qty, 'work_order_id': wo.id},
            )
        if wo.project_component_id:
            project_component_activity_manager.log_event(
                session, wo.project_component_id, wo.workspace_id, 'work_order_item_used',
                f'Used {qty} {name} from {source_label} for work order {wo.work_order_number}',
                performed_by=user_id, metadata={'item_id': item.item_id, 'item_name': name, 'quantity': qty, 'work_order_id': wo.id},
            )

    def _reverse_item_consumption(self, session: Session, wo: WorkOrder, item: WorkOrderItem, user_id: int) -> None:
        if item.consumed_at is None:
            return
        qty = int(item.quantity)
        name = item_name(session, item.item_id, wo.workspace_id)
        post_stock_in(
            session,
            location_type=item.source_location_type,
            location_id=item.source_location_id,
            item_id=item.item_id,
            qty=qty,
            unit_cost=item.unit_cost or Decimal('0'),
            transaction_type='consumption_reversal',
            source_type='work_order',
            source_id=wo.id,
            notes=f'{wo.work_order_number} voided — {name} returned',
            workspace_id=wo.workspace_id,
            user_id=user_id,
            activity_event_type='consumption_reversed',
            activity_description=f'Returned {qty} {name} — work order {wo.work_order_number} voided',
        )
        item.consumed_at = None
        item.consumed_by = None
        item.unit_cost = None
        item.total_cost = None
        session.flush()

    def _apply_item_completion(self, session: Session, wo: WorkOrder, item: WorkOrderItem, user_id: int) -> None:
        """Apply the completion-time inventory movement implied by an item's action_type.
        CONSUME (the default) is a no-op here — it was fully handled at start. Only
        consumed, inventory-tracked items on a machine-targeted order do anything."""
        if not item.uses_inventory or item.consumed_at is None or wo.machine_id is None:
            return
        if item.action_type == 'CONSUME':
            return

        qty = int(item.quantity)
        name = item_name(session, item.item_id, wo.workspace_id)

        if item.action_type == 'INSTALL':
            post_stock_in(
                session,
                location_type='machine', location_id=wo.machine_id, item_id=item.item_id, qty=qty,
                unit_cost=item.unit_cost or Decimal('0'),
                transaction_type='work_order_install', source_type='work_order', source_id=wo.id,
                notes=f'{wo.work_order_number} — {name} installed',
                workspace_id=wo.workspace_id, user_id=user_id,
                activity_event_type='item_installed',
                activity_description=f'Installed {qty} {name} — work order {wo.work_order_number}',
            )

        elif item.action_type == 'REPLACE':
            replaced_name = item_name(session, item.replaced_item_id, wo.workspace_id)
            mi = machine_item_dao.get_by_machine_and_item(
                session, machine_id=wo.machine_id, item_id=item.replaced_item_id, workspace_id=wo.workspace_id,
            )
            on_hand = mi.qty if mi else 0

            if on_hand >= qty:
                post_stock_out(
                    session,
                    location_type='machine', location_id=wo.machine_id, item_id=item.replaced_item_id, qty=qty,
                    transaction_type='work_order_replace_out', source_type='work_order', source_id=wo.id,
                    notes=f'{wo.work_order_number} — {replaced_name} removed for replacement',
                    workspace_id=wo.workspace_id, user_id=user_id,
                    activity_event_type='item_replaced_removed',
                    activity_description=f'Removed {qty} {replaced_name} (replaced) — work order {wo.work_order_number}',
                )
                post_stock_in(
                    session,
                    location_type='damaged', location_id=wo.factory_id, item_id=item.replaced_item_id, qty=qty,
                    unit_cost=Decimal('0'),
                    transaction_type='work_order_replace_damaged', source_type='work_order', source_id=wo.id,
                    notes=f'{wo.work_order_number} — {replaced_name} moved to damaged stock',
                    workspace_id=wo.workspace_id, user_id=user_id,
                )
            else:
                self.log_event(
                    session, wo.id, wo.workspace_id, 'item_replace_degraded',
                    f'Machine only had {on_hand} of {replaced_name} on hand (needed {qty}) — '
                    f'installed {qty} {name} without removing anything',
                    user_id,
                )

            post_stock_in(
                session,
                location_type='machine', location_id=wo.machine_id, item_id=item.item_id, qty=qty,
                unit_cost=item.unit_cost or Decimal('0'),
                transaction_type='work_order_replace_in', source_type='work_order', source_id=wo.id,
                notes=f'{wo.work_order_number} — {name} installed (replacement)',
                workspace_id=wo.workspace_id, user_id=user_id,
                activity_event_type='item_replaced',
                activity_description=f'Installed {qty} {name} as a replacement — work order {wo.work_order_number}',
            )

        elif item.action_type == 'BORROW':
            post_stock_in(
                session,
                location_type=item.source_location_type, location_id=item.source_location_id,
                item_id=item.item_id, qty=qty,
                unit_cost=item.unit_cost or Decimal('0'),
                transaction_type='work_order_borrow_returned', source_type='work_order', source_id=wo.id,
                notes=f'{wo.work_order_number} — {name} returned',
                workspace_id=wo.workspace_id, user_id=user_id,
                activity_event_type='item_borrowed_returned',
                activity_description=f'Returned {qty} {name} — work order {wo.work_order_number}',
            )

    def _set_machine_status(
        self, session: Session, machine_id: int, workspace_id: int, user_id: int,
        new_status: MachineEventTypeEnum, *,
        work_order_number: Optional[str] = None, work_order_id: Optional[int] = None,
    ) -> Optional[str]:
        """Best-effort machine status flip via the existing manual-status mechanism
        (`machine_manager.create_machine_event`). No-ops (and returns the current value)
        if the machine is already in that state — that call 400s on a same-status set.

        `work_order_number`/`work_order_id`, when given, are stamped onto the resulting
        machine event's note/metadata so the machine's event log makes it clear a work
        order (not a manual click) drove the status change, and so the frontend can
        group it with that work order's other log entries."""
        latest = machine_activity_manager.get_latest_status(session, machine_id, workspace_id)
        prev_status = machine_activity_manager.status_from_activity(latest)
        if prev_status == new_status.value:
            return prev_status
        note = f"Work order {work_order_number}" if work_order_number else None
        machine_manager.create_machine_event(
            session,
            event_data=MachineEventCreate(machine_id=machine_id, event_type=new_status, note=note),
            workspace_id=workspace_id, user_id=user_id,
            work_order_id=work_order_id,
        )
        return prev_status

    def _previous_machine_status(self, session: Session, wo: WorkOrder) -> Optional[str]:
        events = self.event_dao.get_by_order(session, work_order_id=wo.id, workspace_id=wo.workspace_id)
        for e in events:
            if e.event_type == 'started':
                return (e.metadata_json or {}).get('previous_machine_status')
        return None

    def start_work_order(self, session: Session, wo_id: int, workspace_id: int, user_id: int) -> WorkOrder:
        wo = self.get_work_order(session, wo_id, workspace_id)
        if wo.status != WorkOrderStatusEnum.DRAFT.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Work order must be in draft to be started',
            )
        if not self.approvals_met(session, wo):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Assigned approvers must approve before work can start',
            )
        items = self.item_dao.get_by_work_order(session, work_order_id=wo_id, workspace_id=workspace_id)
        pending = [i for i in items if i.uses_inventory and i.consumed_at is None]
        for item in pending:
            self._consume_item(session, wo, item, user_id)

        previous_machine_status = None
        if wo.machine_id is not None:
            previous_machine_status = self._set_machine_status(
                session, wo.machine_id, workspace_id, user_id, MachineEventTypeEnum.MAINTENANCE,
                work_order_number=wo.work_order_number, work_order_id=wo.id,
            )

        wo.status = WorkOrderStatusEnum.IN_PROGRESS.value
        wo.started_by = user_id
        wo.started_at = datetime.utcnow()
        session.flush()
        summary = f'{len(pending)} item(s) consumed' if pending else 'no inventory items to consume'
        self.log_event(
            session, wo_id, workspace_id, 'started',
            f'Work started — {summary}', user_id,
            metadata={'items_consumed': len(pending), 'previous_machine_status': previous_machine_status},
        )
        return wo

    def finalize_completion(
        self, session: Session, wo: WorkOrder, user_id: int,
        completion_notes: Optional[str] = None,
        machine_status: Optional[MachineEventTypeEnum] = None,
    ) -> WorkOrder:
        """Stamp completion and write the usage record onto the target (machine or component).

        `machine_status`, when given, is the caller's explicit choice of what state to leave
        the machine in (asked interactively at completion time) and takes priority over the
        auto-detected pre-start status."""
        wo.status = WorkOrderStatusEnum.COMPLETED.value
        wo.completed_by = user_id
        wo.completed_at = datetime.utcnow()
        if completion_notes is not None:
            wo.completion_notes = completion_notes
        session.flush()

        if wo.machine_id is not None:
            items = self.item_dao.get_by_work_order(session, work_order_id=wo.id, workspace_id=wo.workspace_id)
            for item in items:
                self._apply_item_completion(session, wo, item, user_id)

        if wo.machine_id is not None:
            machine_activity_manager.log_event(
                session, wo.machine_id, wo.workspace_id, 'work_order_completed',
                f'Work order completed: {wo.work_order_number} — {wo.title}',
                performed_by=user_id, metadata={'work_order_id': wo.id},
            )
            if machine_status is not None:
                revert_to = machine_status
            else:
                previous_status = self._previous_machine_status(session, wo)
                revert_to = MachineEventTypeEnum(previous_status) if previous_status else MachineEventTypeEnum.IDLE
            self._set_machine_status(
                session, wo.machine_id, wo.workspace_id, user_id, revert_to,
                work_order_number=wo.work_order_number, work_order_id=wo.id,
            )

        if wo.project_component_id is not None:
            summary = f'Work order {wo.work_order_number} completed: {wo.title}'
            if wo.completion_notes:
                summary = f'{summary}. {wo.completion_notes}'
            project_component_activity_manager.log_event(
                session, wo.project_component_id, wo.workspace_id, 'work_order_completed',
                summary, performed_by=user_id, metadata={'work_order_id': wo.id},
            )

        self.log_event(session, wo.id, wo.workspace_id, 'completed', f'Work order {wo.work_order_number} marked complete', user_id)
        return wo

    def void_work_order(self, session: Session, wo_id: int, workspace_id: int, user_id: int, void_note: str) -> WorkOrder:
        wo = self.get_work_order(session, wo_id, workspace_id)
        if wo.status == WorkOrderStatusEnum.COMPLETED.value:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Cannot void a completed work order')
        if wo.status == WorkOrderStatusEnum.VOIDED.value:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Work order is already voided')

        if wo.status == WorkOrderStatusEnum.IN_PROGRESS.value:
            items = self.item_dao.get_by_work_order(session, work_order_id=wo_id, workspace_id=workspace_id)
            for item in items:
                if item.consumed_at is not None:
                    self._reverse_item_consumption(session, wo, item, user_id)

            if wo.machine_id is not None:
                previous_status = self._previous_machine_status(session, wo)
                revert_to = MachineEventTypeEnum(previous_status) if previous_status else MachineEventTypeEnum.IDLE
                self._set_machine_status(
                    session, wo.machine_id, workspace_id, user_id, revert_to,
                    work_order_number=wo.work_order_number, work_order_id=wo.id,
                )

        self.reset_approvals(session, wo_id, workspace_id, user_id, reason='Work order voided')

        wo.status = WorkOrderStatusEnum.VOIDED.value
        wo.void_note = void_note
        wo.voided_at = datetime.utcnow()
        wo.voided_by = user_id
        session.flush()
        self.log_event(
            session, wo_id, workspace_id, 'voided',
            f'Work order {wo.work_order_number} voided. Reason: {void_note}', user_id,
            metadata={'void_note': void_note},
        )
        return wo

    # ─── Work Order Items ────────────────────────────────────────
    def _ensure_catalog_item_not_on_wo(
        self, session: Session, work_order_id: int, item_id: int, workspace_id: int,
        *, exclude_item_id: Optional[int] = None,
    ) -> None:
        from app.utils.order_catalog_items import catalog_item_already_on_order_detail

        for line in self.item_dao.get_by_work_order(session, work_order_id=work_order_id, workspace_id=workspace_id):
            if line.item_id == item_id and line.id != exclude_item_id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=catalog_item_already_on_order_detail(session, item_id=item_id, workspace_id=workspace_id),
                )

    def _guard_item_mutations(self, wo: WorkOrder) -> None:
        if not wo.uses_inventory:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='This work order does not use stock items')
        if self._is_locked(wo):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f'Work order is {wo.status.lower()}')

    def add_item(
        self, session: Session, data: WorkOrderItemCreate, workspace_id: int, user_id: int
    ) -> WorkOrderItem:
        wo = self.get_work_order(session, data.work_order_id, workspace_id)
        self._guard_item_mutations(wo)
        if data.uses_inventory and (not data.source_location_type or not data.source_location_id):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Select a source location for this item')
        if data.action_type != 'CONSUME':
            if not data.uses_inventory:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f'{data.action_type.title()} requires "uses inventory" to be on')
            if wo.machine_id is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Install/Replace/Borrow only apply to work orders that target a machine')
        if data.action_type == 'REPLACE':
            if data.replaced_item_id is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Select the item being replaced')
            replaced = item_dao.get_by_id_and_workspace(session, id=data.replaced_item_id, workspace_id=workspace_id)
            if not replaced:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f'Item with ID {data.replaced_item_id} not found')
        elif data.replaced_item_id is not None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='replaced_item_id only applies to Replace')

        self._ensure_catalog_item_not_on_wo(session, data.work_order_id, data.item_id, workspace_id)

        item_dict = data.model_dump()
        item_dict['workspace_id'] = workspace_id
        item_dict['created_by'] = user_id
        item = self.item_dao.create(session, obj_in=item_dict)

        name = item_name(session, item.item_id, workspace_id)
        self.log_event(
            session, wo.id, workspace_id, 'item_added', f'Added {item.quantity} {name}', user_id,
            metadata={'item_id': item.item_id, 'item_name': name},
        )
        if wo.status == WorkOrderStatusEnum.DRAFT.value:
            if self._has_recorded_approvals(session, wo.id, workspace_id):
                self.reset_approvals(session, wo.id, workspace_id, user_id, reason='Items edited')
        elif wo.status == WorkOrderStatusEnum.IN_PROGRESS.value:
            self._consume_item(session, wo, item, user_id)
        return item

    def update_item(
        self, session: Session, item_id: int, data: WorkOrderItemUpdate, workspace_id: int, user_id: int
    ) -> WorkOrderItem:
        record = self.item_dao.get_by_id_and_workspace(session, id=item_id, workspace_id=workspace_id)
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work order item not found")
        wo = self.get_work_order(session, record.work_order_id, workspace_id)
        self._guard_item_mutations(wo)
        if record.consumed_at is not None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Item has already been consumed — void the order to reverse it')

        update_dict = data.model_dump(exclude_unset=True, exclude_none=True)
        update_dict['updated_by'] = user_id
        result = self.item_dao.update(session, db_obj=record, obj_in=update_dict)

        self.log_event(session, wo.id, workspace_id, 'item_updated', f'Item line {result.id} updated', user_id)
        if wo.status == WorkOrderStatusEnum.DRAFT.value:
            if self._has_recorded_approvals(session, wo.id, workspace_id):
                self.reset_approvals(session, wo.id, workspace_id, user_id, reason='Items edited')
        elif wo.status == WorkOrderStatusEnum.IN_PROGRESS.value:
            self._consume_item(session, wo, result, user_id)
        return result

    def remove_item(self, session: Session, item_id: int, workspace_id: int, user_id: int) -> WorkOrderItem:
        record = self.item_dao.get_by_id_and_workspace(session, id=item_id, workspace_id=workspace_id)
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work order item not found")
        wo = self.get_work_order(session, record.work_order_id, workspace_id)
        self._guard_item_mutations(wo)
        if record.consumed_at is not None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Item has already been consumed — void the order to reverse it')

        name = item_name(session, record.item_id, workspace_id)
        session.delete(record)
        session.flush()
        self.log_event(session, wo.id, workspace_id, 'item_removed', f'Removed {name}', user_id)
        if self._has_recorded_approvals(session, wo.id, workspace_id):
            self.reset_approvals(session, wo.id, workspace_id, user_id, reason='Items edited')
        return record

    def get_items(self, session: Session, wo_id: int, workspace_id: int) -> List[WorkOrderItem]:
        self.get_work_order(session, wo_id, workspace_id)
        return self.item_dao.get_by_work_order(session, work_order_id=wo_id, workspace_id=workspace_id)

    # ─── Sheet workflow ──────────────────────────────────────────
    def sheet_entry(
        self, session: Session, data: WorkOrderSheetEntryCreate,
        workspace_id: int, user_id: int,
    ) -> WorkOrder:
        """Find-or-create WO for machine+date+type; optionally append item lines."""
        has_items = bool(data.items)

        machine = machine_dao.get_by_id_and_workspace(session, id=data.machine_id, workspace_id=workspace_id)
        if not machine:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Machine with ID {data.machine_id} not found")
        factory_id = machine.factory_id

        wo_type = work_order_type_dao.get_by_id_and_workspace(
            session, id=data.work_order_type_id, workspace_id=workspace_id
        )
        if not wo_type:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Work order type not found')

        wo = self.wo_dao.get_by_machine_date_type(
            session,
            workspace_id=workspace_id,
            machine_id=data.machine_id,
            start_date=data.start_date,
            work_order_type_id=data.work_order_type_id,
        )
        if wo is None:
            wo = self.create_work_order(
                session,
                data=WorkOrderCreate(
                    work_order_type_id=data.work_order_type_id,
                    title=f'{wo_type.name} — {machine.name}',
                    description=data.description,
                    priority=data.priority,
                    factory_id=factory_id,
                    machine_id=machine.id,
                    start_date=data.start_date,
                    uses_inventory=has_items,
                    assigned_to=data.assigned_to,
                    account_id=data.account_id,
                    cost=data.cost,
                ),
                workspace_id=workspace_id,
                user_id=user_id,
            )
            if data.template_id:
                wo.work_order_template_id = data.template_id
                session.flush()
        else:
            if data.assigned_to:
                wo.assigned_to = data.assigned_to
            if data.description:
                wo.description = data.description
            if data.priority:
                wo.priority = data.priority
            if data.account_id is not None and wo.account_id is None:
                wo.account_id = data.account_id
            if data.cost is not None and wo.cost is None:
                wo.cost = data.cost
            if data.template_id is not None and wo.work_order_template_id is None:
                wo.work_order_template_id = data.template_id
            if has_items and not wo.uses_inventory:
                wo.uses_inventory = True
            session.flush()

        if has_items:
            for line in data.items:
                source_type = line.source_location_type or 'storage'
                source_id = line.source_location_id
                if source_id is None:
                    source_id = data.machine_id if source_type == 'machine' else factory_id
                self.add_item(
                    session,
                    data=WorkOrderItemCreate(
                        work_order_id=wo.id,
                        item_id=line.item_id,
                        quantity=line.quantity,
                        uses_inventory=True,
                        source_location_type=source_type,
                        source_location_id=source_id,
                        action_type=line.action_type,
                        replaced_item_id=line.replaced_item_id,
                    ),
                    workspace_id=workspace_id,
                    user_id=user_id,
                )

        for approver_line in data.approvers:
            try:
                self.add_approver(
                    session,
                    wo_id=wo.id,
                    user_id=approver_line.user_id,
                    workspace_id=workspace_id,
                    assigned_by=user_id,
                    approver_slot=approver_line.approver_slot,
                )
            except HTTPException as exc:
                if exc.status_code != status.HTTP_409_CONFLICT:
                    raise

        return wo

    def list_sheet_orders(
        self, session: Session, workspace_id: int,
        factory_id: Optional[int] = None,
        machine_id: Optional[int] = None,
        start_date_from: Optional[date] = None,
        start_date_to: Optional[date] = None,
        skip: int = 0,
        limit: int = 1000,
    ) -> List[WorkOrder]:
        return self.wo_dao.list_for_sheet(
            session,
            workspace_id=workspace_id,
            factory_id=factory_id,
            machine_id=machine_id,
            start_date_from=start_date_from,
            start_date_to=start_date_to,
            skip=skip,
            limit=limit,
        )

    # ─── Events ──────────────────────────────────────────────────
    def log_event(
        self, session: Session, wo_id: int, workspace_id: int,
        event_type: str, description: str, performed_by: Optional[int] = None,
        metadata: dict | None = None,
    ) -> WorkOrderEvent:
        ev = WorkOrderEvent(
            workspace_id=workspace_id, work_order_id=wo_id,
            event_type=event_type, description=description,
            metadata_json=metadata, performed_by=performed_by,
        )
        session.add(ev)
        session.flush()
        return ev

    def list_events(self, session: Session, wo_id: int, workspace_id: int) -> List[Tuple[WorkOrderEvent, Optional[Profile]]]:
        self.get_work_order(session, wo_id, workspace_id)
        events = self.event_dao.get_by_order(session, work_order_id=wo_id, workspace_id=workspace_id)
        return [
            (e, profile_dao.get(session, id=e.performed_by) if e.performed_by else None)
            for e in events
        ]


work_order_manager = WorkOrderManager()
