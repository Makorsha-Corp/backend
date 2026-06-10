"""Purchase Order Manager - business logic for purchase orders"""
from typing import Any, List, Optional, Tuple
from decimal import Decimal
from datetime import date, datetime
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.managers.base_manager import BaseManager
from app.models.purchase_order import PurchaseOrder
from app.models.status import Status
from app.models.purchase_order_item import PurchaseOrderItem
from app.models.purchase_order_approver import PurchaseOrderApprover
from app.models.purchase_order_event import PurchaseOrderEvent
from app.models.profile import Profile
from app.schemas.purchase_order import (
    PurchaseOrderCreate, PurchaseOrderUpdate,
    PurchaseOrderItemCreate, PurchaseOrderItemUpdate,
    PurchaseOrderItemSyncRequest,
)
from app.dao.purchase_order import purchase_order_dao, purchase_order_item_dao
from app.dao.purchase_order_approver import purchase_order_approver_dao
from app.dao.purchase_order_event import purchase_order_event_dao
from app.dao.workspace_member import workspace_member_dao
from app.dao.profile import profile_dao
from app.dao.account import account_dao
from app.dao.factory import factory_dao
from app.dao.machine import machine_dao
from app.dao.project_component import project_component_dao
from app.dao.status import status_dao
from app.dao.item import item_dao
from app.dao.account_invoice import account_invoice_dao
from app.dao.order_workflow import order_workflow_dao
from app.models.order_workflow import OrderWorkflow
from app.db.seed_po_workflow import (
    PO_WORKFLOW_TYPE,
    ensure_po_stage_statuses,
    ensure_po_workflow_record,
)

INVOICE_CONFIRMED_DETAIL_FIELDS = frozenset({
    'destination_type', 'destination_id', 'order_date', 'description',
})
SUPPLIER_CONFIRMED_FIELDS = frozenset({'account_id'})
NOTES_FIELDS = frozenset({'order_note'})
DETAIL_LOG_FIELDS = {
    'destination_type': 'Destination type',
    'destination_id': 'Destination',
    'order_date': 'Order date',
    'expected_delivery_date': 'Expected delivery',
    'description': 'Description',
}
SUPPLIER_LOG_FIELDS = {
    'account_id': 'Supplier',
}
NOTE_LOG_FIELDS = {
    'order_note': 'Order note',
}
STATUS_LOG_FIELDS = {
    'current_status_id': 'Status',
}
THRESHOLD_LOG_FIELDS = {
    'required_approvals': 'Approval threshold',
}
ITEM_UPDATE_LOG_FIELDS = {
    'quantity_ordered': 'Quantity ordered',
    'unit_price': 'Unit price',
    'notes': 'Notes',
}
DESTINATION_TYPE_LABELS = {
    'storage': 'Storage',
    'machine': 'Machine',
    'project': 'Project',
}
INVOICE_CONFIRM_MSG = 'Confirmed after invoice creation'
SECTION_CONFIRM_FIELDS = {
    'supplier_confirmed': ('supplier', 'Supplier'),
    'details_confirmed': ('details', 'Order details'),
    'notes_confirmed': ('notes', 'Order notes'),
    'items_confirmed': ('items', 'Order items'),
    'invoice_confirmed': ('invoice', 'Draft invoice'),
}
PO_STAGE_NAMES = ('Draft', 'Planning', 'Receiving', 'Complete')


class PurchaseOrderManager(BaseManager[PurchaseOrder]):
    """Manager for purchase order business logic."""

    def __init__(self):
        super().__init__(PurchaseOrder)
        self.po_dao = purchase_order_dao
        self.item_dao = purchase_order_item_dao
        self.approver_dao = purchase_order_approver_dao
        self.event_dao = purchase_order_event_dao

    def get_po_by_invoice_id(
        self, session: Session, invoice_id: int, workspace_id: int
    ) -> Optional[PurchaseOrder]:
        return self.po_dao.get_by_invoice_id(
            session, invoice_id=invoice_id, workspace_id=workspace_id
        )

    def is_po_financially_locked(self, session: Session, po: PurchaseOrder) -> bool:
        """True when a linked invoice is confirmed or locked (PO fields locked)."""
        if po.invoice_id is None:
            return False
        invoice = account_invoice_dao.get_by_id_and_workspace(
            session, id=po.invoice_id, workspace_id=po.workspace_id
        )
        if not invoice:
            return False
        return invoice.invoice_status in ('confirmed', 'locked')

    def unlink_invoice_from_po(
        self,
        session: Session,
        po: PurchaseOrder,
        user_id: int,
        reason: str,
        event_type: str = 'invoice_unlinked',
        extra_metadata: dict | None = None,
    ) -> None:
        old_invoice_id = po.invoice_id
        po.invoice_id = None
        po.invoice_confirmed = False
        session.flush()
        metadata: dict = {'invoice_id': old_invoice_id}
        if extra_metadata:
            metadata.update(extra_metadata)
        self.log_event(
            session, po.id, po.workspace_id, event_type, reason, user_id,
            metadata=metadata,
        )

    def reset_approvals(
        self,
        session: Session,
        po_id: int,
        workspace_id: int,
        user_id: int,
        reason: str = 'Cleared approvals after invoice voided',
    ) -> None:
        approvers = self.approver_dao.get_by_order(
            session, purchase_order_id=po_id, workspace_id=workspace_id
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
                session, po_id, workspace_id, 'approvals_reset',
                f'{reason} ({reset_count} approval(s) cleared)',
                user_id,
            )

    def _ensure_po_stage_statuses(self, session: Session, workspace_id: int) -> None:
        """Lazy backfill Draft/Planning/Receiving/Complete status rows for this workspace."""
        has_draft = (
            session.query(Status.id)
            .filter(Status.workspace_id == workspace_id, Status.name == 'Draft')
            .first()
        )
        if not has_draft:
            ensure_po_stage_statuses(session, workspace_id)

    def _raise_po_workflow_setup_error(self, session: Session, workspace_id: int) -> None:
        foreign = (
            session.query(OrderWorkflow.id)
            .filter(
                OrderWorkflow.type == PO_WORKFLOW_TYPE,
                OrderWorkflow.workspace_id != workspace_id,
            )
            .first()
        )
        if foreign:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    'Purchase order workflow requires database migration '
                    '022_po_stage_workflow. Run: alembic upgrade head'
                ),
            )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail='Purchase order workflow is not configured for this workspace',
        )

    def _resolve_po_stage_status_id(
        self, session: Session, workspace_id: int, stage_name: str
    ) -> int:
        self._ensure_po_stage_statuses(session, workspace_id)
        record = (
            session.query(Status)
            .filter(Status.workspace_id == workspace_id, Status.name == stage_name)
            .first()
        )
        if not record:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Purchase order stage status '{stage_name}' not found for this workspace",
            )
        return record.id

    def _resolve_po_workflow_id(self, session: Session, workspace_id: int) -> int:
        self._ensure_po_stage_statuses(session, workspace_id)
        workflow = ensure_po_workflow_record(session, workspace_id)
        if not workflow:
            self._raise_po_workflow_setup_error(session, workspace_id)
        return workflow.id

    def _derive_po_stage_name(
        self, po: PurchaseOrder, items: List[PurchaseOrderItem]
    ) -> str:
        if items:
            if all(
                self._quantity_received_decimal(i) >= Decimal(str(i.quantity_ordered))
                for i in items
            ):
                return 'Complete'
            if any(self._quantity_received_decimal(i) > 0 for i in items):
                return 'Receiving'
        if po.supplier_confirmed or po.details_confirmed or po.items_confirmed:
            return 'Planning'
        return 'Draft'

    def sync_po_stage(
        self,
        session: Session,
        po: PurchaseOrder,
        workspace_id: int,
        user_id: Optional[int],
    ) -> bool:
        """Recompute and apply PO stage from business state. Returns True if status changed."""
        items = self.item_dao.get_by_order(
            session, purchase_order_id=po.id, workspace_id=workspace_id
        )
        target_stage = self._derive_po_stage_name(po, items)
        target_status_id = self._resolve_po_stage_status_id(
            session, workspace_id, target_stage
        )
        workflow_id = self._resolve_po_workflow_id(session, workspace_id)

        changed = False
        if po.order_workflow_id != workflow_id:
            po.order_workflow_id = workflow_id
            changed = True

        if po.current_status_id != target_status_id:
            old_status_id = po.current_status_id
            po.current_status_id = target_status_id
            changed = True
            changes = [{
                'field': 'current_status_id',
                'label': 'Status',
                'from_value': self._format_field_value(
                    session, workspace_id, 'current_status_id', old_status_id,
                    destination_type=po.destination_type,
                ),
                'to_value': target_stage,
            }]
            self._log_field_change_event(
                session,
                po.id,
                workspace_id,
                user_id,
                'status_updated',
                f'Stage updated to {target_stage}',
                changes,
            )

        if target_stage == 'Complete' and po.actual_delivery_date is None:
            po.actual_delivery_date = date.today()
            changed = True

        if changed:
            session.flush()
        return changed

    def create_purchase_order(
        self, session: Session, data: PurchaseOrderCreate,
        workspace_id: int, user_id: int
    ) -> PurchaseOrder:
        """Create purchase order with auto-generated number and nested items."""
        po_number = self.po_dao.allocate_po_number(session, workspace_id=workspace_id)

        items_data = data.items or []
        po_dict = data.model_dump(exclude={'items'})
        po_dict['workspace_id'] = workspace_id
        po_dict['po_number'] = po_number
        po_dict['current_status_id'] = self._resolve_po_stage_status_id(
            session, workspace_id, 'Draft'
        )
        po_dict['order_workflow_id'] = self._resolve_po_workflow_id(session, workspace_id)
        po_dict['created_by'] = user_id
        if not po_dict.get('order_date'):
            po_dict['order_date'] = date.today()

        po = self.po_dao.create(session, obj_in=po_dict)

        # Auto-add the creator as an approver.
        session.add(PurchaseOrderApprover(
            workspace_id=workspace_id,
            purchase_order_id=po.id,
            user_id=user_id,
            assigned_by=user_id,
            approved=False,
        ))
        session.flush()

        self.log_event(session, po.id, workspace_id, 'created', 'Order created', user_id)

        subtotal = Decimal('0')

        for idx, item_data in enumerate(items_data, start=1):
            item_dict = item_data.model_dump()
            item_dict['workspace_id'] = workspace_id
            item_dict['purchase_order_id'] = po.id
            item_dict['line_number'] = idx

            qty = Decimal(str(item_dict['quantity_ordered']))
            price = Decimal(str(item_dict['unit_price']))
            line_sub = qty * price
            item_dict['line_subtotal'] = line_sub
            item_dict['quantity_received'] = Decimal('0')

            subtotal += line_sub

            self.item_dao.create(session, obj_in=item_dict)

        po.subtotal = subtotal
        po.total_amount = subtotal
        session.flush()

        self.sync_po_stage(session, po, workspace_id, user_id)
        return po

    def update_purchase_order(
        self, session: Session, po_id: int, data: PurchaseOrderUpdate,
        workspace_id: int, user_id: int
    ) -> PurchaseOrder:
        """Update purchase order."""
        record = self.po_dao.get_by_id_and_workspace(session, id=po_id, workspace_id=workspace_id)
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Purchase order with ID {po_id} not found")

        update_dict = data.model_dump(exclude_unset=True, exclude_none=True)
        update_dict.pop('current_status_id', None)
        update_dict['updated_by'] = user_id

        if self.is_po_financially_locked(session, record):
            if update_dict.get('supplier_confirmed') is False:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail='Cannot unconfirm supplier after invoice is confirmed',
                )
            if update_dict.get('details_confirmed') is False:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail='Cannot unconfirm order details after invoice is confirmed',
                )
            if update_dict.get('items_confirmed') is False:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail='Cannot unconfirm order items after invoice is confirmed',
                )
            if update_dict.get('invoice_confirmed') is False:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail='Cannot unconfirm draft invoice after invoice is finalized',
                )

        blocked_supplier = self._confirmed_supplier_update_fields(session, record).intersection(update_dict)
        if blocked_supplier:
            detail = (
                INVOICE_CONFIRM_MSG
                if self.is_po_financially_locked(session, record)
                else 'Supplier is confirmed'
            )
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)

        blocked_details = self._confirmed_detail_update_fields(session, record).intersection(update_dict)
        if blocked_details:
            detail = (
                INVOICE_CONFIRM_MSG
                if self.is_po_financially_locked(session, record)
                else 'Order details are confirmed'
            )
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)

        if record.notes_confirmed and NOTES_FIELDS.intersection(update_dict):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Order notes are confirmed',
            )

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
                    session, po_id, workspace_id,
                    f'{section_key}_{event_suffix}',
                    f'{label} {event_suffix}',
                    user_id,
                )

        if section_unconfirmed:
            self.reset_approvals(
                session, po_id, workspace_id, user_id,
                reason='Section unconfirmed',
            )

        self._log_section_field_updates(
            session, po_id, workspace_id, user_id, record, update_dict,
        )
        self._log_admin_field_updates(
            session, po_id, workspace_id, user_id, record, update_dict,
        )

        updated = self.po_dao.update(session, db_obj=record, obj_in=update_dict)
        self.sync_po_stage(session, updated, workspace_id, user_id)
        return updated

    def _format_scalar_value(self, field: str, value: Any) -> str:
        if value is None:
            if field in ('description', 'order_note', 'notes'):
                return '—'
            if field == 'required_approvals':
                return 'All assigned'
            return '—'
        if isinstance(value, date):
            return value.isoformat()
        if isinstance(value, Decimal):
            return str(int(value)) if value == value.to_integral_value() else str(value.normalize())
        text = str(value).strip()
        return text if text else '—'

    def _format_destination_id(
        self, session: Session, workspace_id: int, destination_type: str | None, destination_id: Any,
    ) -> str:
        if destination_id is None:
            return '—'
        dtype = (destination_type or '').lower()
        if dtype == 'storage':
            factory = factory_dao.get_by_id_and_workspace(
                session, id=destination_id, workspace_id=workspace_id
            )
            return factory.name if factory else f'Factory #{destination_id}'
        if dtype == 'machine':
            machine = machine_dao.get_by_id_and_workspace(
                session, id=destination_id, workspace_id=workspace_id
            )
            return machine.name if machine else f'Machine #{destination_id}'
        if dtype == 'project':
            component = project_component_dao.get_by_id_and_workspace(
                session, id=destination_id, workspace_id=workspace_id
            )
            return component.name if component else f'Project component #{destination_id}'
        return f'#{destination_id}'

    def _format_field_value(
        self,
        session: Session,
        workspace_id: int,
        field: str,
        value: Any,
        *,
        destination_type: str | None = None,
    ) -> str:
        if field == 'account_id':
            if value is None:
                return '—'
            account = account_dao.get_by_id_and_workspace(session, id=value, workspace_id=workspace_id)
            return account.name if account else f'Account #{value}'
        if field == 'destination_type':
            if not value:
                return '—'
            return DESTINATION_TYPE_LABELS.get(str(value).lower(), str(value))
        if field == 'destination_id':
            return self._format_destination_id(session, workspace_id, destination_type, value)
        if field == 'current_status_id':
            if value is None:
                return '—'
            status = status_dao.get(session, id=value)
            return status.name if status else f'Status #{value}'
        if field == 'required_approvals':
            if value is None:
                return 'All assigned'
            return str(value)
        return self._format_scalar_value(field, value)

    def _collect_field_changes(
        self,
        session: Session,
        workspace_id: int,
        record: PurchaseOrder,
        update_dict: dict,
        fields: dict[str, str],
    ) -> List[dict]:
        changes: List[dict] = []
        new_destination_type = update_dict.get('destination_type', record.destination_type)
        for field, label in fields.items():
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
                    destination_type=record.destination_type,
                ),
                'to_value': self._format_field_value(
                    session, workspace_id, field, new_val,
                    destination_type=new_destination_type,
                ),
            })
        return changes

    def _collect_item_field_changes(
        self, record: PurchaseOrderItem, update_dict: dict,
    ) -> List[dict]:
        changes: List[dict] = []
        for field, label in ITEM_UPDATE_LOG_FIELDS.items():
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

    def _log_field_change_event(
        self,
        session: Session,
        po_id: int,
        workspace_id: int,
        user_id: int,
        event_type: str,
        description: str,
        changes: List[dict],
        extra_metadata: dict | None = None,
    ) -> None:
        metadata: dict = {'changes': changes}
        if extra_metadata:
            metadata.update(extra_metadata)
        self.log_event(session, po_id, workspace_id, event_type, description, user_id, metadata)

    def _log_section_field_updates(
        self,
        session: Session,
        po_id: int,
        workspace_id: int,
        user_id: int,
        record: PurchaseOrder,
        update_dict: dict,
    ) -> None:
        supplier_changes = self._collect_field_changes(
            session, workspace_id, record, update_dict, SUPPLIER_LOG_FIELDS
        )
        if supplier_changes:
            self._log_field_change_event(
                session, po_id, workspace_id, user_id,
                'supplier_updated', 'Changed supplier', supplier_changes,
            )

        detail_changes = self._collect_field_changes(
            session, workspace_id, record, update_dict, DETAIL_LOG_FIELDS
        )
        if detail_changes:
            self._log_field_change_event(
                session, po_id, workspace_id, user_id,
                'details_updated', 'Changed order details', detail_changes,
            )

        note_changes = self._collect_field_changes(
            session, workspace_id, record, update_dict, NOTE_LOG_FIELDS
        )
        if note_changes:
            self._log_field_change_event(
                session, po_id, workspace_id, user_id,
                'notes_updated', 'Changed order notes', note_changes,
            )

    def _log_admin_field_updates(
        self,
        session: Session,
        po_id: int,
        workspace_id: int,
        user_id: int,
        record: PurchaseOrder,
        update_dict: dict,
    ) -> None:
        status_changes = self._collect_field_changes(
            session, workspace_id, record, update_dict, STATUS_LOG_FIELDS
        )
        if status_changes:
            self._log_field_change_event(
                session, po_id, workspace_id, user_id,
                'status_updated', 'Changed status', status_changes,
            )

        threshold_changes = self._collect_field_changes(
            session, workspace_id, record, update_dict, THRESHOLD_LOG_FIELDS
        )
        if threshold_changes:
            self._log_field_change_event(
                session, po_id, workspace_id, user_id,
                'approvals_threshold_updated', 'Changed approval threshold', threshold_changes,
            )

    def _confirmed_supplier_update_fields(self, session: Session, record: PurchaseOrder) -> frozenset:
        if self.is_po_financially_locked(session, record):
            return SUPPLIER_CONFIRMED_FIELDS
        if record.supplier_confirmed:
            return SUPPLIER_CONFIRMED_FIELDS
        return frozenset()

    def _confirmed_detail_update_fields(self, session: Session, record: PurchaseOrder) -> frozenset:
        if self.is_po_financially_locked(session, record):
            return INVOICE_CONFIRMED_DETAIL_FIELDS
        if record.details_confirmed:
            return INVOICE_CONFIRMED_DETAIL_FIELDS
        return frozenset()

    def _items_structure_confirmed(self, session: Session, po: PurchaseOrder) -> bool:
        return bool(po.items_confirmed or self.is_po_financially_locked(session, po))

    def details_complete_for_invoice(self, po: PurchaseOrder) -> bool:
        return (
            po.account_id is not None
            and bool(po.destination_type)
            and po.destination_id is not None
            and po.order_date is not None
        )

    def _base_sections_confirmed(self, po: PurchaseOrder) -> bool:
        return bool(
            po.supplier_confirmed
            and po.details_confirmed
            and po.items_confirmed
        )

    def _all_sections_confirmed(self, po: PurchaseOrder) -> bool:
        return bool(
            self._base_sections_confirmed(po)
            and po.invoice_confirmed
        )

    def _validate_section_confirm(
        self,
        record: PurchaseOrder,
        update_dict: dict,
        session: Session,
        workspace_id: int,
    ) -> None:
        account_id = update_dict.get('account_id', record.account_id)
        if (
            update_dict.get('supplier_confirmed') is True
            and not record.supplier_confirmed
            and account_id is None
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Select a supplier before confirming',
            )
        dest_type = update_dict.get('destination_type', record.destination_type)
        dest_id = update_dict.get('destination_id', record.destination_id)
        order_date = update_dict.get('order_date', record.order_date)
        details_ready = bool(dest_type) and dest_id is not None and order_date is not None
        if (
            update_dict.get('details_confirmed') is True
            and not record.details_confirmed
            and not details_ready
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Complete destination, location, and order date before confirming',
            )
        if update_dict.get('items_confirmed') is True and not record.items_confirmed:
            po_items = self.item_dao.get_by_order(
                session, purchase_order_id=record.id, workspace_id=workspace_id
            )
            if not po_items:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail='Add at least one line item before confirming',
                )
        if update_dict.get('invoice_confirmed') is True and not record.invoice_confirmed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Draft invoice is confirmed when you finalize the invoice — use Finalize Invoice instead',
            )

    def apply_post_invoice_confirms(
        self, session: Session, po: PurchaseOrder, workspace_id: int, user_id: int
    ) -> None:
        """Set section confirms and log events after an invoice is linked to the order."""
        self.log_event(
            session, po.id, workspace_id, 'invoice_created',
            'Invoice created', user_id,
        )
        if not po.supplier_confirmed:
            po.supplier_confirmed = True
            self.log_event(
                session, po.id, workspace_id, 'supplier_confirmed',
                'Supplier confirmed after invoice created', user_id,
            )
        if not po.details_confirmed:
            po.details_confirmed = True
            self.log_event(
                session, po.id, workspace_id, 'details_confirmed',
                'Order details confirmed after invoice created', user_id,
            )
        if not po.items_confirmed:
            po.items_confirmed = True
            self.log_event(
                session, po.id, workspace_id, 'items_confirmed',
                'Order items confirmed after invoice created', user_id,
            )
        if not po.invoice_confirmed:
            po.invoice_confirmed = True
            self.log_event(
                session, po.id, workspace_id, 'invoice_confirmed',
                'Draft invoice confirmed after invoice finalized', user_id,
            )
        session.flush()

    def get_purchase_order(self, session: Session, po_id: int, workspace_id: int) -> PurchaseOrder:
        record = self.po_dao.get_by_id_and_workspace(session, id=po_id, workspace_id=workspace_id)
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Purchase order with ID {po_id} not found")
        return record

    def list_purchase_orders(
        self, session: Session, workspace_id: int,
        account_id: Optional[int] = None,
        invoice_id: Optional[int] = None,
        skip: int = 0, limit: int = 100
    ) -> List[PurchaseOrder]:
        return self.po_dao.get_by_workspace(
            session, workspace_id=workspace_id,
            account_id=account_id,
            invoice_id=invoice_id,
            skip=skip, limit=limit
        )

    def delete_purchase_order(self, session: Session, po_id: int, workspace_id: int) -> None:
        record = self.po_dao.get_by_id_and_workspace(session, id=po_id, workspace_id=workspace_id)
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Purchase order with ID {po_id} not found")
        # Delete line items explicitly to avoid FK issues when DB constraints
        # were created without cascading deletes.
        line_items = self.item_dao.get_by_order(
            session, purchase_order_id=po_id, workspace_id=workspace_id
        )
        for line_item in line_items:
            session.delete(line_item)
        session.flush()
        session.delete(record)
        session.flush()

    # ─── Purchase Order Items ──────────────────────────────────
    def _quantity_received_decimal(self, record: PurchaseOrderItem) -> Decimal:
        """Coerce NULL legacy quantity_received rows to 0."""
        raw = record.quantity_received
        if raw is None:
            return Decimal('0')
        return Decimal(str(raw))

    def _validate_ordered_vs_received(
        self, quantity_ordered: Decimal, quantity_received: Decimal
    ) -> None:
        if quantity_ordered < quantity_received:
            received_display = (
                str(int(quantity_received))
                if quantity_received == quantity_received.to_integral_value()
                else str(quantity_received.normalize())
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f'Ordered quantity cannot be less than received ({received_display})',
            )

    def _ensure_catalog_item_not_on_po(
        self,
        session: Session,
        po_id: int,
        item_id: int,
        workspace_id: int,
        *,
        exclude_item_id: Optional[int] = None,
    ) -> None:
        for line in self.item_dao.get_by_order(
            session, purchase_order_id=po_id, workspace_id=workspace_id
        ):
            if line.item_id == item_id and line.id != exclude_item_id:
                catalog_item = item_dao.get_by_id_and_workspace(
                    session, id=item_id, workspace_id=workspace_id
                )
                name = catalog_item.name if catalog_item else f'Item #{item_id}'
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f'{name} is already on this purchase order',
                )

    def add_item(
        self, session: Session, po_id: int, data: PurchaseOrderItemCreate,
        workspace_id: int, user_id: Optional[int] = None
    ) -> PurchaseOrderItem:
        """Add item to purchase order and recalculate totals."""
        po = self.po_dao.get_by_id_and_workspace(session, id=po_id, workspace_id=workspace_id)
        if not po:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Purchase order not found")
        if self._items_structure_confirmed(session, po):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=INVOICE_CONFIRM_MSG if self.is_po_financially_locked(session, po) else 'Order items are confirmed',
            )

        self._ensure_catalog_item_not_on_po(session, po_id, data.item_id, workspace_id)

        existing = self.item_dao.get_by_order(session, purchase_order_id=po_id, workspace_id=workspace_id)
        next_line = max((i.line_number for i in existing), default=0) + 1

        item_dict = data.model_dump()
        item_dict['workspace_id'] = workspace_id
        item_dict['purchase_order_id'] = po_id
        item_dict['line_number'] = next_line
        item_dict['quantity_received'] = Decimal('0')

        qty = Decimal(str(item_dict['quantity_ordered']))
        price = Decimal(str(item_dict['unit_price']))
        item_dict['line_subtotal'] = qty * price

        item = self.item_dao.create(session, obj_in=item_dict)
        self._recalc_totals(session, po)
        session.refresh(item)
        catalog_item = item_dao.get_by_id_and_workspace(
            session, id=item.item_id, workspace_id=workspace_id
        )
        item_name = catalog_item.name if catalog_item else f'Item #{item.item_id}'
        self.log_event(
            session, po_id, workspace_id, 'item_added',
            f'Added {item_name} (line {item.line_number})',
            user_id,
            metadata={
                'item_id': item.item_id,
                'item_name': item_name,
                'line_number': item.line_number,
                'quantity_ordered': self._format_scalar_value('quantity_ordered', qty),
                'unit_price': self._format_scalar_value('unit_price', price),
            },
        )
        if user_id is not None:
            po = self.po_dao.get_by_id_and_workspace(session, id=po_id, workspace_id=workspace_id)
            if po:
                self.sync_po_stage(session, po, workspace_id, user_id)
        return item

    def update_item(
        self, session: Session, item_id: int, data: PurchaseOrderItemUpdate,
        workspace_id: int, user_id: Optional[int] = None
    ) -> PurchaseOrderItem:
        """Update purchase order item. Logs a 'received' event when quantity_received changes."""
        record = self.item_dao.get_by_id_and_workspace(session, id=item_id, workspace_id=workspace_id)
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Purchase order item not found")
        update_dict = data.model_dump(exclude_unset=True, exclude_none=True)

        po = self.po_dao.get_by_id_and_workspace(
            session, id=record.purchase_order_id, workspace_id=workspace_id
        )
        if po and self._items_structure_confirmed(session, po):
            structural = set(update_dict.keys()) - {'quantity_received'}
            if structural:
                detail = (
                    f'{INVOICE_CONFIRM_MSG} (receiving still allowed)'
                    if self.is_po_financially_locked(session, po)
                    else 'Order items are confirmed (receiving still allowed)'
                )
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)

        prev_received = self._quantity_received_decimal(record)
        received_changed = (
            'quantity_received' in update_dict
            and update_dict['quantity_received'] is not None
            and Decimal(str(update_dict['quantity_received'])) != prev_received
        )

        if received_changed and po:
            if po.invoice_id is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail='Finalize the invoice before recording receiving',
                )
            linked_invoice = account_invoice_dao.get_by_id_and_workspace(
                session, id=po.invoice_id, workspace_id=workspace_id
            )
            if not linked_invoice or linked_invoice.invoice_status not in ('confirmed', 'locked'):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail='Finalize the invoice before recording receiving',
                )

        item_changes = self._collect_item_field_changes(record, update_dict)

        qty_ordered = Decimal(str(update_dict.get('quantity_ordered', record.quantity_ordered)))
        qty_received = (
            Decimal(str(update_dict['quantity_received']))
            if update_dict.get('quantity_received') is not None
            else self._quantity_received_decimal(record)
        )
        self._validate_ordered_vs_received(qty_ordered, qty_received)

        if 'quantity_ordered' in update_dict or 'unit_price' in update_dict:
            qty = Decimal(str(update_dict.get('quantity_ordered', record.quantity_ordered)))
            price = Decimal(str(update_dict.get('unit_price', record.unit_price)))
            update_dict['line_subtotal'] = qty * price

        result = self.item_dao.update(session, db_obj=record, obj_in=update_dict)
        po = self.po_dao.get_by_id_and_workspace(session, id=record.purchase_order_id, workspace_id=workspace_id)
        if po:
            self._recalc_totals(session, po)

        if item_changes:
            item_label = getattr(record, 'item_name', None) or f'Item #{record.item_id}'
            self._log_field_change_event(
                session, record.purchase_order_id, workspace_id, user_id,
                'item_updated',
                f'Updated item: {item_label}',
                item_changes,
                extra_metadata={
                    'item_id': record.item_id,
                    'item_name': item_label,
                    'line_number': record.line_number,
                },
            )

        if received_changed:
            item_label = getattr(record, 'item_name', None) or f"item #{record.item_id}"
            new_received = Decimal(str(update_dict['quantity_received']))
            ordered = Decimal(str(record.quantity_ordered))
            delta = new_received - prev_received
            fully_received = new_received >= ordered

            def _qty(d: Decimal) -> str:
                return str(int(d)) if d == d.to_integral_value() else str(d.normalize())

            xy = f"({_qty(new_received)} of {_qty(ordered)})"
            if delta > 0:
                if fully_received:
                    description = f"Received {_qty(delta)} more — {xy} {item_label} fully received"
                else:
                    description = f"Received {_qty(delta)} more {xy} {item_label}"
            else:
                description = f"Receiving adjusted to {_qty(new_received)} of {_qty(ordered)} {item_label}"
            self.log_event(
                session, record.purchase_order_id, workspace_id, 'received',
                description,
                user_id,
                metadata={
                    'changes': [{
                        'field': 'quantity_received',
                        'label': f'{item_label} received',
                        'from_value': _qty(prev_received),
                        'to_value': _qty(new_received),
                    }],
                    'item_id': record.item_id,
                    'item_name': item_label,
                    'line_number': record.line_number,
                    'quantity_ordered': _qty(ordered),
                },
            )

            # If this completed the final outstanding item, log an order-level
            # "all items received" milestone (once).
            if fully_received:
                po_items = self.item_dao.get_by_order(
                    session, purchase_order_id=record.purchase_order_id, workspace_id=workspace_id
                )
                all_done = po_items and all(
                    Decimal(str(i.quantity_received)) >= Decimal(str(i.quantity_ordered))
                    for i in po_items
                )
                if all_done:
                    already_logged = any(
                        e.event_type == 'all_received'
                        for e in self.event_dao.get_by_order(
                            session, purchase_order_id=record.purchase_order_id, workspace_id=workspace_id
                        )
                    )
                    if not already_logged:
                        self.log_event(
                            session, record.purchase_order_id, workspace_id, 'all_received',
                            'All items received', user_id,
                        )

            if po and po.invoice_id:
                linked_invoice_for_lock = account_invoice_dao.get_by_id_and_workspace(
                    session, id=po.invoice_id, workspace_id=workspace_id
                )
                if linked_invoice_for_lock and linked_invoice_for_lock.invoice_status == 'confirmed':
                    po_items = self.item_dao.get_by_order(
                        session, purchase_order_id=po.id, workspace_id=workspace_id
                    )
                    total_received = sum(
                        Decimal(str(i.quantity_received or 0)) for i in po_items
                    )
                    if total_received > 0:
                        from app.managers.account_invoice_manager import account_invoice_manager
                        account_invoice_manager.lock_invoice(
                            session, po.invoice_id, workspace_id, user_id or 0
                        )
                        self.log_event(
                            session, po.id, workspace_id, 'invoice_locked',
                            f'Invoice #{po.invoice_id} locked after first receipt',
                            user_id,
                            metadata={'invoice_id': po.invoice_id},
                        )

        if po and user_id is not None:
            self.sync_po_stage(session, po, workspace_id, user_id)
        return result

    def remove_item(
        self, session: Session, item_id: int, workspace_id: int, user_id: Optional[int] = None
    ) -> PurchaseOrderItem:
        """Remove item from purchase order."""
        record = self.item_dao.get_by_id_and_workspace(session, id=item_id, workspace_id=workspace_id)
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Purchase order item not found")
        po = self.po_dao.get_by_id_and_workspace(
            session, id=record.purchase_order_id, workspace_id=workspace_id
        )
        if po and self._items_structure_confirmed(session, po):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=INVOICE_CONFIRM_MSG if self.is_po_financially_locked(session, po) else 'Order items are confirmed',
            )
        po_id = record.purchase_order_id
        item_label = getattr(record, 'item_name', None) or f'Item #{record.item_id}'
        line_number = record.line_number
        catalog_item_id = record.item_id
        session.delete(record)
        session.flush()
        po = self.po_dao.get_by_id_and_workspace(session, id=po_id, workspace_id=workspace_id)
        if po:
            self._recalc_totals(session, po)
        self.log_event(
            session, po_id, workspace_id, 'item_removed',
            f'Removed {item_label} (line {line_number})',
            user_id,
            metadata={
                'item_id': catalog_item_id,
                'item_name': item_label,
                'line_number': line_number,
            },
        )
        if po and user_id is not None:
            self.sync_po_stage(session, po, workspace_id, user_id)
        return record

    def sync_items(
        self,
        session: Session,
        po_id: int,
        data: PurchaseOrderItemSyncRequest,
        workspace_id: int,
        user_id: Optional[int] = None,
    ) -> PurchaseOrder:
        """Apply item removes, updates, and additions in one pass; recalc totals once."""
        po = self.po_dao.get_by_id_and_workspace(session, id=po_id, workspace_id=workspace_id)
        if not po:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Purchase order not found")
        if self._items_structure_confirmed(session, po):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=INVOICE_CONFIRM_MSG if self.is_po_financially_locked(session, po) else 'Order items are confirmed',
            )

        existing_by_id = {
            i.id: i
            for i in self.item_dao.get_by_order(
                session, purchase_order_id=po_id, workspace_id=workspace_id
            )
        }

        for rid in data.remove_ids:
            record = existing_by_id.get(rid)
            if not record:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Purchase order item {rid} not found",
                )
            received = self._quantity_received_decimal(record)
            if received > 0:
                item_label = getattr(record, 'item_name', None) or f'Item #{record.item_id}'
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f'Cannot remove {item_label} — receiving has already been recorded',
                )
            item_label = getattr(record, 'item_name', None) or f'Item #{record.item_id}'
            line_number = record.line_number
            catalog_item_id = record.item_id
            session.delete(record)
            del existing_by_id[rid]
            self.log_event(
                session, po_id, workspace_id, 'item_removed',
                f'Removed {item_label} (line {line_number})',
                user_id,
                metadata={
                    'item_id': catalog_item_id,
                    'item_name': item_label,
                    'line_number': line_number,
                },
            )
        session.flush()

        for upd in data.updates:
            record = existing_by_id.get(upd.id)
            if not record:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Purchase order item {upd.id} not found",
                )
            session.refresh(record)
            qty = Decimal(str(upd.quantity_ordered))
            price = Decimal(str(upd.unit_price))
            received = self._quantity_received_decimal(record)
            self._validate_ordered_vs_received(qty, received)
            update_dict = {
                'quantity_ordered': upd.quantity_ordered,
                'unit_price': upd.unit_price,
                'line_subtotal': qty * price,
            }
            if record.quantity_received is None:
                update_dict['quantity_received'] = received
            item_changes = self._collect_item_field_changes(record, update_dict)
            self.item_dao.update(session, db_obj=record, obj_in=update_dict)
            if item_changes and user_id is not None:
                item_label = getattr(record, 'item_name', None) or f'Item #{record.item_id}'
                self._log_field_change_event(
                    session, po_id, workspace_id, user_id,
                    'item_updated',
                    f'Updated item: {item_label}',
                    item_changes,
                    extra_metadata={
                        'item_id': record.item_id,
                        'item_name': item_label,
                        'line_number': record.line_number,
                    },
                )
        session.flush()

        remaining = list(existing_by_id.values())
        next_line = max((i.line_number for i in remaining), default=0) + 1

        for add in data.additions:
            self._ensure_catalog_item_not_on_po(session, po_id, add.item_id, workspace_id)
            item_dict = add.model_dump()
            item_dict['workspace_id'] = workspace_id
            item_dict['purchase_order_id'] = po_id
            item_dict['line_number'] = next_line
            item_dict['quantity_received'] = Decimal('0')
            qty = Decimal(str(item_dict['quantity_ordered']))
            price = Decimal(str(item_dict['unit_price']))
            item_dict['line_subtotal'] = qty * price
            item = self.item_dao.create(session, obj_in=item_dict)
            catalog_item = item_dao.get_by_id_and_workspace(
                session, id=item.item_id, workspace_id=workspace_id
            )
            item_name = catalog_item.name if catalog_item else f'Item #{item.item_id}'
            self.log_event(
                session, po_id, workspace_id, 'item_added',
                f'Added {item_name} (line {item.line_number})',
                user_id,
                metadata={
                    'item_id': item.item_id,
                    'item_name': item_name,
                    'line_number': item.line_number,
                    'quantity_ordered': self._format_scalar_value('quantity_ordered', qty),
                    'unit_price': self._format_scalar_value('unit_price', price),
                },
            )
            next_line += 1

        self._recalc_totals(session, po)
        session.refresh(po)
        if user_id is not None:
            self.sync_po_stage(session, po, workspace_id, user_id)
        return po

    def get_items(self, session: Session, po_id: int, workspace_id: int) -> List[PurchaseOrderItem]:
        return self.item_dao.get_by_order(session, purchase_order_id=po_id, workspace_id=workspace_id)

    def _recalc_totals(self, session: Session, po: PurchaseOrder):
        """Recalculate order totals from line items."""
        items = self.item_dao.get_by_order(session, purchase_order_id=po.id, workspace_id=po.workspace_id)
        subtotal = sum((i.line_subtotal or Decimal('0')) for i in items)
        po.subtotal = subtotal
        po.total_amount = subtotal
        session.flush()

    # ─── Approvers ─────────────────────────────────────────────
    def list_approvers(
        self, session: Session, po_id: int, workspace_id: int
    ) -> List[Tuple[PurchaseOrderApprover, Optional[Profile], Optional[str]]]:
        """Approvers for an order, enriched with profile + workspace position."""
        self.get_purchase_order(session, po_id, workspace_id)  # 404 guard
        approvers = self.approver_dao.get_by_order(session, purchase_order_id=po_id, workspace_id=workspace_id)
        result: List[Tuple[PurchaseOrderApprover, Optional[Profile], Optional[str]]] = []
        for a in approvers:
            profile = profile_dao.get(session, id=a.user_id)
            member = workspace_member_dao.get_by_workspace_and_user(
                session, workspace_id=workspace_id, user_id=a.user_id
            )
            result.append((a, profile, member.position if member else None))
        return result

    def approval_summary(self, session: Session, po: PurchaseOrder) -> Tuple[int, int, bool]:
        """(approved_count, required, met). required null -> all assigned must approve."""
        approvers = self.approver_dao.get_by_order(
            session, purchase_order_id=po.id, workspace_id=po.workspace_id
        )
        approved_count = sum(1 for a in approvers if a.approved)
        if po.required_approvals is not None:
            required = po.required_approvals
        elif len(approvers) > 0:
            required = len(approvers)
        else:
            required = 0
        return approved_count, required, approved_count >= required

    def approvals_met(self, session: Session, po: PurchaseOrder) -> bool:
        return self.approval_summary(session, po)[2]

    def add_approver(
        self, session: Session, po_id: int, user_id: int, workspace_id: int, assigned_by: int
    ) -> PurchaseOrderApprover:
        self.get_purchase_order(session, po_id, workspace_id)  # 404 guard
        member = workspace_member_dao.get_by_workspace_and_user(
            session, workspace_id=workspace_id, user_id=user_id
        )
        if not member or member.status != 'active':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User is not an active member of this workspace"
            )
        existing = self.approver_dao.get_by_order_and_user(
            session, purchase_order_id=po_id, user_id=user_id, workspace_id=workspace_id
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User is already an approver for this order"
            )
        obj = PurchaseOrderApprover(
            workspace_id=workspace_id,
            purchase_order_id=po_id,
            user_id=user_id,
            assigned_by=assigned_by,
            approved=False,
        )
        session.add(obj)
        session.flush()
        profile = profile_dao.get(session, id=user_id)
        user_name = profile.name if profile else f'User #{user_id}'
        self.log_event(
            session, po_id, workspace_id, 'approver_added',
            f'Added {user_name} as approver',
            assigned_by,
            metadata={'user_id': user_id, 'user_name': user_name},
        )
        return obj

    def remove_approver(
        self, session: Session, po_id: int, user_id: int, workspace_id: int,
        performed_by: Optional[int] = None,
    ) -> None:
        rec = self.approver_dao.get_by_order_and_user(
            session, purchase_order_id=po_id, user_id=user_id, workspace_id=workspace_id
        )
        if not rec:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approver not found")
        profile = profile_dao.get(session, id=user_id)
        user_name = profile.name if profile else f'User #{user_id}'
        session.delete(rec)
        session.flush()
        self.log_event(
            session, po_id, workspace_id, 'approver_removed',
            f'Removed {user_name} as approver',
            performed_by,
            metadata={'user_id': user_id, 'user_name': user_name},
        )

    def set_approval(
        self, session: Session, po_id: int, user_id: int, workspace_id: int, approved: bool
    ) -> PurchaseOrderApprover:
        rec = self.approver_dao.get_by_order_and_user(
            session, purchase_order_id=po_id, user_id=user_id, workspace_id=workspace_id
        )
        if not rec:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not an assigned approver for this order"
            )
        if approved:
            po = self.get_purchase_order(session, po_id, workspace_id)
            if not self._base_sections_confirmed(po):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail='Confirm supplier, order details, and items before approving',
                )
        else:
            po = self.get_purchase_order(session, po_id, workspace_id)
            if po.invoice_id is not None:
                invoice = account_invoice_dao.get_by_id_and_workspace(
                    session, id=po.invoice_id, workspace_id=workspace_id
                )
                if invoice and invoice.invoice_status == 'locked':
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail='Cannot withdraw approval — invoice is locked',
                    )
        rec.approved = approved
        rec.approved_at = datetime.utcnow() if approved else None
        session.flush()

        self.log_event(
            session, po_id, workspace_id,
            'approved' if approved else 'approval_withdrawn',
            'Approved order' if approved else 'Withdrew approval',
            user_id,
        )
        return rec

    # ─── Events ────────────────────────────────────────────────
    def log_event(
        self, session: Session, po_id: int, workspace_id: int,
        event_type: str, description: str, performed_by: Optional[int] = None,
        metadata: dict | None = None,
    ) -> PurchaseOrderEvent:
        ev = PurchaseOrderEvent(
            workspace_id=workspace_id,
            purchase_order_id=po_id,
            event_type=event_type,
            description=description,
            metadata_json=metadata,
            performed_by=performed_by,
        )
        session.add(ev)
        session.flush()
        return ev

    def list_events(
        self, session: Session, po_id: int, workspace_id: int
    ) -> List[Tuple[PurchaseOrderEvent, Optional[Profile]]]:
        self.get_purchase_order(session, po_id, workspace_id)  # 404 guard
        events = self.event_dao.get_by_order(session, purchase_order_id=po_id, workspace_id=workspace_id)
        return [
            (e, profile_dao.get(session, id=e.performed_by) if e.performed_by else None)
            for e in events
        ]


purchase_order_manager = PurchaseOrderManager()
