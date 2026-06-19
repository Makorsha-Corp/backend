"""Expense Order Manager - business logic for expense orders"""
from datetime import date, datetime
from decimal import Decimal
from typing import Any, List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.dao.account_invoice import account_invoice_dao
from app.dao.expense_order import expense_order_dao, expense_order_item_dao
from app.dao.expense_order_approver import expense_order_approver_dao
from app.dao.expense_order_event import expense_order_event_dao
from app.dao.profile import profile_dao
from app.dao.workspace_member import workspace_member_dao
from app.managers.base_manager import BaseManager
from app.models.expense_order import ExpenseOrder
from app.models.expense_order_approver import ExpenseOrderApprover
from app.models.expense_order_event import ExpenseOrderEvent
from app.models.expense_order_item import ExpenseOrderItem
from app.models.profile import Profile
from app.schemas.expense_order import (
    ExpenseOrderCreate,
    ExpenseOrderItemCreate,
    ExpenseOrderItemUpdate,
    ExpenseOrderUpdate,
)

DETAILS_UPDATE_FIELDS = frozenset({
    'account_id', 'expense_category', 'expense_date', 'due_date',
    'description', 'expense_note', 'internal_note',
})
ORDER_UPDATE_LOG_FIELDS = {
    'account_id': 'Account',
    'expense_category': 'Category',
    'expense_date': 'Expense date',
    'due_date': 'Due date',
    'description': 'Description',
    'expense_note': 'Expense note',
    'internal_note': 'Internal note',
    'required_approvals': 'Required approvals',
}
SECTION_CONFIRM_FIELDS = {
    'details_confirmed': ('details', 'Order details'),
    'items_confirmed': ('items', 'Expenses'),
    'invoice_confirmed': ('invoice', 'Draft invoice'),
}
VALID_COST_CENTER_TYPES = frozenset({'factory', 'machine', 'project', 'department'})


class ExpenseOrderManager(BaseManager[ExpenseOrder]):
    """Manager for expense order business logic."""

    def __init__(self):
        super().__init__(ExpenseOrder)
        self.eo_dao = expense_order_dao
        self.item_dao = expense_order_item_dao
        self.approver_dao = expense_order_approver_dao
        self.event_dao = expense_order_event_dao

    # ─── Helpers ─────────────────────────────────────────────────
    def _is_completed(self, record: ExpenseOrder) -> bool:
        return record.completed_at is not None

    def _base_sections_confirmed(self, record: ExpenseOrder) -> bool:
        return bool(record.details_confirmed and record.items_confirmed)

    def _validate_allocation_fields(self, item_dict: dict) -> None:
        ctype = item_dict.get('cost_center_type')
        cid = item_dict.get('cost_center_id')
        if ctype is not None or cid is not None:
            if not ctype or cid is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail='Cost center type and ID must both be set',
                )
            if str(ctype).lower() not in VALID_COST_CENTER_TYPES:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f'Invalid cost center type: {ctype}',
                )

    def _validate_item_row(self, item: ExpenseOrderItem) -> None:
        if not (item.description or '').strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Each expense line needs a description',
            )
        qty = Decimal(str(item.quantity or 0))
        if qty <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Each expense line needs a positive quantity',
            )

    def resolve_invoice_account_id(self, record: ExpenseOrder) -> int:
        if record.account_id:
            return record.account_id
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail='Set an account on the expense order before creating an invoice',
        )

    def reset_approvals(
        self,
        session: Session,
        eo_id: int,
        workspace_id: int,
        user_id: int,
        reason: str = 'Section unconfirmed',
    ) -> None:
        approvers = self.approver_dao.get_by_order(
            session, expense_order_id=eo_id, workspace_id=workspace_id
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
                session, eo_id, workspace_id, 'approvals_reset',
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

    def _collect_field_changes(
        self,
        record: ExpenseOrder,
        update_dict: dict,
    ) -> List[dict]:
        changes: List[dict] = []
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
                'from_value': self._format_scalar_value(field, old_val),
                'to_value': self._format_scalar_value(field, new_val),
            })
        return changes

    def _validate_section_confirm(
        self,
        record: ExpenseOrder,
        update_dict: dict,
        session: Session,
        workspace_id: int,
    ) -> None:
        if update_dict.get('details_confirmed') is True and not record.details_confirmed:
            category = update_dict.get('expense_category', record.expense_category)
            exp_date = update_dict.get('expense_date', record.expense_date)
            if not category or not exp_date:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail='Set category and expense date before confirming order details',
                )
        if update_dict.get('items_confirmed') is True and not record.items_confirmed:
            items = self.item_dao.get_by_order(
                session, expense_order_id=record.id, workspace_id=workspace_id
            )
            if not items:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail='Add at least one expense line before confirming',
                )
            for item in items:
                self._validate_item_row(item)
        if update_dict.get('invoice_confirmed') is True and not record.invoice_confirmed:
            if not record.invoice_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail='Create a draft invoice before confirming',
                )
            invoice = account_invoice_dao.get_by_id_and_workspace(
                session, id=record.invoice_id, workspace_id=workspace_id
            )
            if not invoice or invoice.invoice_status != 'confirmed':
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail='Confirm the linked invoice before confirming this section',
                )

    def _guard_confirmed_updates(self, record: ExpenseOrder, update_dict: dict) -> None:
        if self._is_completed(record):
            blocked = set(update_dict.keys()) - {'internal_note'}
            if blocked:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail='Expense order is complete and cannot be edited',
                )
        if 'current_status_id' in update_dict:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Status is derived from workflow state — use Mark complete instead',
            )
        if record.details_confirmed and DETAILS_UPDATE_FIELDS.intersection(update_dict):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Order details are confirmed',
            )
        if record.invoice_confirmed and record.invoice_id and 'invoice_id' in update_dict:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Invoice section is confirmed',
            )

    def _guard_item_mutations(self, record: ExpenseOrder) -> None:
        if self._is_completed(record):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Expense order is complete',
            )
        if record.items_confirmed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Expenses are confirmed',
            )

    def _prepare_item_dict(self, item_dict: dict) -> dict:
        self._validate_allocation_fields(item_dict)
        qty = Decimal(str(item_dict.get('quantity', 1)))
        price = Decimal(str(item_dict.get('unit_price') or 0))
        item_dict['line_subtotal'] = qty * price
        return item_dict

    # ─── CRUD ────────────────────────────────────────────────────
    def create_expense_order(
        self, session: Session, data: ExpenseOrderCreate,
        workspace_id: int, user_id: int
    ) -> ExpenseOrder:
        exp_number = self.eo_dao.get_next_number(session, workspace_id=workspace_id)
        items_data = data.items or []
        eo_dict = data.model_dump(exclude={'items'})
        eo_dict['workspace_id'] = workspace_id
        eo_dict['expense_number'] = exp_number
        eo_dict['created_by'] = user_id
        if not eo_dict.get('expense_date'):
            eo_dict['expense_date'] = date.today()

        eo = self.eo_dao.create(session, obj_in=eo_dict)

        session.add(ExpenseOrderApprover(
            workspace_id=workspace_id,
            expense_order_id=eo.id,
            user_id=user_id,
            assigned_by=user_id,
            approved=False,
        ))
        session.flush()

        subtotal = Decimal('0')
        for idx, item_data in enumerate(items_data, start=1):
            item_dict = self._prepare_item_dict(item_data.model_dump())
            item_dict['workspace_id'] = workspace_id
            item_dict['expense_order_id'] = eo.id
            item_dict['line_number'] = idx
            subtotal += item_dict['line_subtotal']
            self.item_dao.create(session, obj_in=item_dict)

        eo.subtotal = subtotal
        eo.total_amount = subtotal
        session.flush()
        self.log_event(session, eo.id, workspace_id, 'created', 'Expense order created', user_id)
        return eo

    def update_expense_order(
        self, session: Session, eo_id: int, data: ExpenseOrderUpdate,
        workspace_id: int, user_id: int
    ) -> ExpenseOrder:
        record = self.eo_dao.get_by_id_and_workspace(session, id=eo_id, workspace_id=workspace_id)
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Expense order with ID {eo_id} not found")

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
                    session, eo_id, workspace_id,
                    f'{section_key}_{event_suffix}',
                    f'{label} {event_suffix}',
                    user_id,
                )

        if section_unconfirmed:
            self.reset_approvals(session, eo_id, workspace_id, user_id)

        changes = self._collect_field_changes(record, update_dict)
        if changes:
            self.log_event(
                session, eo_id, workspace_id, 'updated', 'Order details updated', user_id,
                metadata={'changes': changes},
            )

        update_dict['updated_by'] = user_id
        return self.eo_dao.update(session, db_obj=record, obj_in=update_dict)

    def get_expense_order(self, session: Session, eo_id: int, workspace_id: int) -> ExpenseOrder:
        record = self.eo_dao.get_by_id_and_workspace(session, id=eo_id, workspace_id=workspace_id)
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Expense order with ID {eo_id} not found")
        return record

    def list_expense_orders(
        self, session: Session, workspace_id: int,
        expense_category: Optional[str] = None,
        account_id: Optional[int] = None,
        invoice_id: Optional[int] = None,
        skip: int = 0, limit: int = 100
    ) -> List[ExpenseOrder]:
        return self.eo_dao.get_by_workspace(
            session, workspace_id=workspace_id,
            expense_category=expense_category, account_id=account_id,
            invoice_id=invoice_id,
            skip=skip, limit=limit
        )

    def delete_expense_order(self, session: Session, eo_id: int, workspace_id: int) -> None:
        record = self.eo_dao.get_by_id_and_workspace(session, id=eo_id, workspace_id=workspace_id)
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Expense order with ID {eo_id} not found")
        if self._is_completed(record):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Cannot delete a completed expense order',
            )
        line_items = self.item_dao.get_by_order(
            session, expense_order_id=eo_id, workspace_id=workspace_id
        )
        for line_item in line_items:
            session.delete(line_item)
        session.flush()
        session.delete(record)
        session.flush()

    def mark_order_complete(
        self,
        session: Session,
        eo_id: int,
        workspace_id: int,
        user_id: int,
    ) -> ExpenseOrder:
        record = self.get_expense_order(session, eo_id, workspace_id)
        if self._is_completed(record):
            return record

        if not self._base_sections_confirmed(record):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Confirm order details and expenses before completing',
            )
        if not record.invoice_confirmed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Confirm the draft invoice before completing',
            )
        if not record.invoice_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Create and confirm an invoice before completing',
            )
        if not self.approvals_met(session, record):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Required approvals are not met',
            )

        invoice = account_invoice_dao.get_by_id_and_workspace(
            session, id=record.invoice_id, workspace_id=workspace_id
        )
        if not invoice or invoice.invoice_status != 'confirmed':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Linked invoice must be confirmed before completing',
            )

        record.completed_at = datetime.utcnow()
        record.completed_by = user_id
        record.updated_by = user_id
        session.flush()
        self.log_event(
            session, eo_id, workspace_id, 'order_completed',
            'Expense order marked complete', user_id,
        )
        return record

    # ─── Items ───────────────────────────────────────────────────
    def add_item(
        self, session: Session, eo_id: int, data: ExpenseOrderItemCreate,
        workspace_id: int, user_id: int,
    ) -> ExpenseOrderItem:
        eo = self.get_expense_order(session, eo_id, workspace_id)
        self._guard_item_mutations(eo)

        existing = self.item_dao.get_by_order(session, expense_order_id=eo_id, workspace_id=workspace_id)
        next_line = max((i.line_number for i in existing), default=0) + 1

        item_dict = self._prepare_item_dict(data.model_dump())
        item_dict['workspace_id'] = workspace_id
        item_dict['expense_order_id'] = eo_id
        item_dict['line_number'] = next_line
        item = self.item_dao.create(session, obj_in=item_dict)
        self._recalc_totals(session, eo)
        self.log_event(
            session, eo_id, workspace_id, 'item_added',
            f'Line {next_line} added', user_id,
            metadata={'line_number': next_line},
        )
        return item

    def update_item(
        self, session: Session, item_id: int, data: ExpenseOrderItemUpdate,
        workspace_id: int, user_id: int
    ) -> ExpenseOrderItem:
        record = self.item_dao.get_by_id_and_workspace(session, id=item_id, workspace_id=workspace_id)
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expense order item not found")

        eo = self.get_expense_order(session, record.expense_order_id, workspace_id)
        self._guard_item_mutations(eo)

        update_dict = data.model_dump(exclude_unset=True, exclude_none=True)
        if any(k in update_dict for k in ('cost_center_type', 'cost_center_id')):
            merged = {
                'cost_center_type': update_dict.get('cost_center_type', record.cost_center_type),
                'cost_center_id': update_dict.get('cost_center_id', record.cost_center_id),
            }
            self._validate_allocation_fields(merged)

        if 'quantity' in update_dict or 'unit_price' in update_dict:
            qty = Decimal(str(update_dict.get('quantity', record.quantity)))
            price = Decimal(str(update_dict.get('unit_price', record.unit_price) or 0))
            update_dict['line_subtotal'] = qty * price

        result = self.item_dao.update(session, db_obj=record, obj_in=update_dict)
        self._recalc_totals(session, eo)
        self.log_event(
            session, eo.id, workspace_id, 'item_updated',
            f'Line {result.line_number} updated', user_id,
        )
        return result

    def remove_item(
        self, session: Session, item_id: int, workspace_id: int, user_id: int
    ) -> ExpenseOrderItem:
        record = self.item_dao.get_by_id_and_workspace(session, id=item_id, workspace_id=workspace_id)
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expense order item not found")

        eo = self.get_expense_order(session, record.expense_order_id, workspace_id)
        self._guard_item_mutations(eo)

        line_number = record.line_number
        session.delete(record)
        session.flush()
        self._recalc_totals(session, eo)
        self.log_event(
            session, eo.id, workspace_id, 'item_removed',
            f'Line {line_number} removed', user_id,
        )
        return record

    def get_items(self, session: Session, eo_id: int, workspace_id: int) -> List[ExpenseOrderItem]:
        self.get_expense_order(session, eo_id, workspace_id)
        return self.item_dao.get_by_order(session, expense_order_id=eo_id, workspace_id=workspace_id)

    def _recalc_totals(self, session: Session, eo: ExpenseOrder):
        items = self.item_dao.get_by_order(session, expense_order_id=eo.id, workspace_id=eo.workspace_id)
        subtotal = sum((i.line_subtotal or Decimal('0')) for i in items)
        eo.subtotal = subtotal
        eo.total_amount = subtotal
        session.flush()

    # ─── Approvers ───────────────────────────────────────────────
    def list_approvers(
        self, session: Session, eo_id: int, workspace_id: int
    ) -> List[Tuple[ExpenseOrderApprover, Optional[Profile], Optional[str]]]:
        self.get_expense_order(session, eo_id, workspace_id)
        approvers = self.approver_dao.get_by_order(
            session, expense_order_id=eo_id, workspace_id=workspace_id
        )
        result: List[Tuple[ExpenseOrderApprover, Optional[Profile], Optional[str]]] = []
        for approver in approvers:
            profile = profile_dao.get(session, id=approver.user_id)
            member = workspace_member_dao.get_by_workspace_and_user(
                session, workspace_id=workspace_id, user_id=approver.user_id
            )
            result.append((approver, profile, member.position if member else None))
        return result

    def approval_summary(self, session: Session, eo: ExpenseOrder) -> Tuple[int, int, bool]:
        approvers = self.approver_dao.get_by_order(
            session, expense_order_id=eo.id, workspace_id=eo.workspace_id
        )
        approved_count = sum(1 for a in approvers if a.approved)
        if eo.required_approvals is not None:
            required = eo.required_approvals
        elif len(approvers) > 0:
            required = len(approvers)
        else:
            required = 0
        return approved_count, required, approved_count >= required

    def approvals_met(self, session: Session, eo: ExpenseOrder) -> bool:
        return self.approval_summary(session, eo)[2]

    def add_approver(
        self, session: Session, eo_id: int, user_id: int, workspace_id: int, assigned_by: int
    ) -> ExpenseOrderApprover:
        self.get_expense_order(session, eo_id, workspace_id)
        member = workspace_member_dao.get_by_workspace_and_user(
            session, workspace_id=workspace_id, user_id=user_id
        )
        if not member or member.status != 'active':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='User is not an active member of this workspace',
            )
        existing = self.approver_dao.get_by_order_and_user(
            session, expense_order_id=eo_id, user_id=user_id, workspace_id=workspace_id
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail='User is already an approver for this order',
            )
        obj = ExpenseOrderApprover(
            workspace_id=workspace_id,
            expense_order_id=eo_id,
            user_id=user_id,
            assigned_by=assigned_by,
            approved=False,
        )
        session.add(obj)
        session.flush()
        profile = profile_dao.get(session, id=user_id)
        user_name = profile.name if profile else f'User #{user_id}'
        self.log_event(
            session, eo_id, workspace_id, 'approver_added',
            f'Added {user_name} as approver',
            assigned_by,
            metadata={'user_id': user_id, 'user_name': user_name},
        )
        return obj

    def remove_approver(
        self, session: Session, eo_id: int, user_id: int, workspace_id: int,
        performed_by: Optional[int] = None,
    ) -> None:
        rec = self.approver_dao.get_by_order_and_user(
            session, expense_order_id=eo_id, user_id=user_id, workspace_id=workspace_id
        )
        if not rec:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Approver not found')
        profile = profile_dao.get(session, id=user_id)
        user_name = profile.name if profile else f'User #{user_id}'
        session.delete(rec)
        session.flush()
        self.log_event(
            session, eo_id, workspace_id, 'approver_removed',
            f'Removed {user_name} as approver',
            performed_by,
            metadata={'user_id': user_id, 'user_name': user_name},
        )

    def set_approval(
        self, session: Session, eo_id: int, user_id: int, workspace_id: int, approved: bool
    ) -> ExpenseOrderApprover:
        rec = self.approver_dao.get_by_order_and_user(
            session, expense_order_id=eo_id, user_id=user_id, workspace_id=workspace_id
        )
        if not rec:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail='You are not an assigned approver for this order',
            )
        eo = self.get_expense_order(session, eo_id, workspace_id)
        if approved and not self._base_sections_confirmed(eo):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Confirm order details and expenses before approving',
            )
        rec.approved = approved
        rec.approved_at = datetime.utcnow() if approved else None
        session.flush()
        self.log_event(
            session, eo_id, workspace_id,
            'approved' if approved else 'approval_withdrawn',
            'Approved expense order' if approved else 'Withdrew approval',
            user_id,
        )
        return rec

    # ─── Events ──────────────────────────────────────────────────
    def log_event(
        self, session: Session, eo_id: int, workspace_id: int,
        event_type: str, description: str, performed_by: Optional[int] = None,
        metadata: dict | None = None,
    ) -> ExpenseOrderEvent:
        ev = ExpenseOrderEvent(
            workspace_id=workspace_id,
            expense_order_id=eo_id,
            event_type=event_type,
            description=description,
            metadata_json=metadata,
            performed_by=performed_by,
        )
        session.add(ev)
        session.flush()
        return ev

    def list_events(
        self, session: Session, eo_id: int, workspace_id: int
    ) -> List[Tuple[ExpenseOrderEvent, Optional[Profile]]]:
        self.get_expense_order(session, eo_id, workspace_id)
        events = self.event_dao.get_by_order(
            session, expense_order_id=eo_id, workspace_id=workspace_id
        )
        return [
            (e, profile_dao.get(session, id=e.performed_by) if e.performed_by else None)
            for e in events
        ]


expense_order_manager = ExpenseOrderManager()
