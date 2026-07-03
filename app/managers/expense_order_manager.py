"""Expense Order Manager - business logic for expense orders"""
from datetime import date, datetime
from decimal import Decimal
from typing import Any, List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.dao.expense_order import expense_order_dao, expense_order_item_dao
from app.dao.expense_order_approver import expense_order_approver_dao
from app.dao.expense_order_event import expense_order_event_dao
from app.dao.profile import profile_dao
from app.dao.workspace_member import workspace_member_dao
from app.managers.base_manager import BaseManager
from app.managers.order_template_manager import order_template_manager
from app.models.expense_order import ExpenseOrder
from app.models.expense_order_approver import ExpenseOrderApprover
from app.models.expense_order_event import ExpenseOrderEvent
from app.models.expense_order_item import ExpenseOrderItem
from app.models.profile import Profile
from app.schemas.expense_order import (
    ExpenseOrderCreate,
    ExpenseOrderFromTemplateCreate,
    ExpenseOrderItemCreate,
    ExpenseOrderItemUpdate,
    ExpenseOrderUpdate,
)

DETAILS_FIELDS = frozenset({
    'account_id', 'expense_category', 'cost_center_id', 'expense_date', 'due_date',
    'description',
})
ORDER_UPDATE_LOG_FIELDS = {
    'account_id': 'Account',
    'expense_category': 'Category',
    'cost_center_id': 'Cost center',
    'expense_date': 'Expense date',
    'due_date': 'Due date',
    'description': 'Description',
    'required_approvals': 'Required approvals',
}
VALID_ALLOCATION_TYPES = frozenset({'factory', 'department', 'other'})


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

    def _has_recorded_approvals(self, session: Session, eo_id: int, workspace_id: int) -> bool:
        approvers = self.approver_dao.get_by_order(
            session, expense_order_id=eo_id, workspace_id=workspace_id
        )
        return any(a.approved for a in approvers)

    def is_approvable(self, session: Session, eo: ExpenseOrder) -> bool:
        """Minimal readiness gate before approving or auto-creating the draft invoice."""
        if not eo.expense_category or not eo.expense_date:
            return False
        if eo.expense_category != 'other' and eo.cost_center_id is None:
            return False
        if not (eo.description or '').strip():
            return False
        items = self.item_dao.get_by_order(session, expense_order_id=eo.id, workspace_id=eo.workspace_id)
        if not items:
            return False
        return all(
            (i.description or '').strip() and Decimal(str(i.quantity or 0)) > 0
            for i in items
        )

    def approvability_gap_reason(self, session: Session, eo: ExpenseOrder) -> str | None:
        if not eo.expense_category or not eo.expense_date:
            return 'Set category and expense date before approvals can proceed'
        if eo.expense_category != 'other' and eo.cost_center_id is None:
            return f'Select a {eo.expense_category} for this expense order before approvals can proceed'
        if not (eo.description or '').strip():
            return 'Add a description before approvals can proceed'
        items = self.item_dao.get_by_order(session, expense_order_id=eo.id, workspace_id=eo.workspace_id)
        if not items:
            return 'Add at least one expense line before approvals can proceed'
        return None

    def _validate_order_allocation(
        self, session: Session, workspace_id: int,
        expense_category: str, cost_center_id: int | None,
    ) -> None:
        if expense_category not in VALID_ALLOCATION_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f'Invalid category: {expense_category}. Must be factory, department, or other.',
            )
        if expense_category == 'other':
            return
        if cost_center_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f'Select a {expense_category} for this expense order',
            )
        if expense_category == 'factory':
            from app.dao.factory import factory_dao
            if not factory_dao.get_by_id_and_workspace(session, id=cost_center_id, workspace_id=workspace_id):
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Selected factory not found')
        else:
            from app.dao.department import department_dao
            if not department_dao.get_by_id_and_workspace(session, id=cost_center_id, workspace_id=workspace_id):
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Selected department not found')

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

    def _guard_confirmed_updates(self, record: ExpenseOrder, update_dict: dict) -> None:
        if self._is_completed(record) and update_dict:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Expense order is complete and cannot be edited',
            )

    def _guard_item_mutations(self, record: ExpenseOrder) -> None:
        if self._is_completed(record):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Expense order is complete',
            )

    def _prepare_item_dict(self, item_dict: dict) -> dict:
        qty = Decimal(str(item_dict.get('quantity', 1)))
        price = Decimal(str(item_dict.get('unit_price') or 0))
        item_dict['line_subtotal'] = qty * price
        return item_dict

    # ─── CRUD ────────────────────────────────────────────────────
    def create_expense_order(
        self, session: Session, data: ExpenseOrderCreate,
        workspace_id: int, user_id: int
    ) -> ExpenseOrder:
        self._validate_order_allocation(session, workspace_id, data.expense_category, data.cost_center_id)
        if not (data.description or '').strip():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Description is required')

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

        if 'expense_category' in update_dict or 'cost_center_id' in update_dict:
            merged_category = update_dict.get('expense_category', record.expense_category)
            merged_cost_center_id = update_dict.get('cost_center_id', record.cost_center_id)
            self._validate_order_allocation(session, workspace_id, merged_category, merged_cost_center_id)

        changes = self._collect_field_changes(record, update_dict)

        approvals_reset = False
        if DETAILS_FIELDS.intersection(update_dict) and self._has_recorded_approvals(session, eo_id, workspace_id):
            self.reset_approvals(session, eo_id, workspace_id, user_id, reason='Order details edited')
            approvals_reset = True

        if changes:
            self.log_event(
                session, eo_id, workspace_id, 'updated', 'Order details updated', user_id,
                metadata={'changes': changes},
            )

        update_dict['updated_by'] = user_id
        updated = self.eo_dao.update(session, db_obj=record, obj_in=update_dict)
        updated._approvals_reset = approvals_reset
        return updated

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
        if self._has_recorded_approvals(session, eo_id, workspace_id):
            self.reset_approvals(session, eo_id, workspace_id, user_id, reason='Expense items edited')
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
        if self._has_recorded_approvals(session, eo.id, workspace_id):
            self.reset_approvals(session, eo.id, workspace_id, user_id, reason='Expense items edited')
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
        if self._has_recorded_approvals(session, eo.id, workspace_id):
            self.reset_approvals(session, eo.id, workspace_id, user_id, reason='Expense items edited')
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
        if approved and not self.is_approvable(session, eo):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=self.approvability_gap_reason(session, eo) or 'Order is not ready for approval',
            )
        if not approved and self._is_completed(eo):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Cannot withdraw approval — order is complete',
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

    # ─── Templates ───────────────────────────────────────────────
    def create_expense_order_from_template(
        self, session: Session, template_id: int, workspace_id: int, user_id: int,
        overrides: ExpenseOrderFromTemplateCreate,
    ) -> ExpenseOrder:
        template = order_template_manager.get_template(session, template_id, workspace_id)
        if not template.is_active:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Template is inactive')
        tpl_items = order_template_manager.get_items(session, template_id, workspace_id)

        eo = self.create_expense_order(
            session,
            data=ExpenseOrderCreate(
                account_id=template.account_id,
                expense_category=template.expense_category or 'other',
                cost_center_id=template.cost_center_id,
                expense_date=overrides.expense_date or date.today(),
                due_date=overrides.due_date,
                description=overrides.description or template.description,
                order_template_id=template.id,
                items=[
                    ExpenseOrderItemCreate(
                        description=ti.description,
                        quantity=ti.quantity,
                        unit=ti.unit,
                        unit_price=ti.unit_price,
                        notes=ti.notes,
                    )
                    for ti in sorted(tpl_items, key=lambda x: x.line_number)
                ],
            ),
            workspace_id=workspace_id, user_id=user_id,
        )

        if not template.requires_approval:
            eo.required_approvals = 0
            session.flush()
        elif template.auto_approve:
            eo.required_approvals = 0
            session.flush()
            self.log_event(
                session, eo.id, workspace_id, 'auto_approved',
                'Auto-approved — following template instructions', user_id,
                metadata={'order_template_id': template.id},
            )
        elif template.default_approver_id and template.default_approver_id != user_id:
            existing = self.approver_dao.get_by_order_and_user(
                session, expense_order_id=eo.id, user_id=template.default_approver_id, workspace_id=workspace_id
            )
            if not existing:
                self.add_approver(
                    session, eo_id=eo.id, user_id=template.default_approver_id,
                    workspace_id=workspace_id, assigned_by=user_id,
                )

        self.log_event(
            session, eo.id, workspace_id, 'created_from_template',
            f'Generated from template "{template.template_name}"', user_id,
            metadata={'order_template_id': template.id},
        )
        return eo


expense_order_manager = ExpenseOrderManager()
