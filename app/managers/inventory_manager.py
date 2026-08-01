"""Inventory Manager - business logic for unified inventory"""
from collections import defaultdict
from decimal import Decimal
from typing import DefaultDict, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.managers.base_manager import BaseManager
from app.models.inventory import Inventory
from app.models.enums import InventoryTypeEnum
from app.schemas.inventory import InventoryCreate, InventoryUpdate, InventoryListResponse, InventoryStatsResponse, InventoryStatsByTypeRow
from app.schemas.inventory_incoming import IncomingOrderLine, ItemIncomingSummary
from app.dao.inventory import inventory_dao
from app.dao.inventory_ledger import inventory_ledger_dao
from app.dao.factory import factory_dao
from app.dao.purchase_order import purchase_order_dao, purchase_order_item_dao
from app.dao.transfer_order import transfer_order_dao, transfer_order_item_dao
from app.utils.order_workflow_terminal import is_order_terminal, terminal_status_ids_by_workflow


class InventoryManager(BaseManager[Inventory]):
    """Manager for unified inventory business logic."""

    def __init__(self):
        super().__init__(Inventory)
        self.inv_dao = inventory_dao
        self.ledger_dao = inventory_ledger_dao

    def create_inventory(
        self, session: Session, data: InventoryCreate,
        workspace_id: int, user_id: int
    ) -> Inventory:
        """Create inventory record. Validates factory exists."""
        factory = factory_dao.get_by_id_and_workspace(
            session, id=data.factory_id, workspace_id=workspace_id
        )
        if not factory:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Factory with ID {data.factory_id} not found"
            )

        # Check for duplicate
        existing = self.inv_dao.get_by_factory_item_type(
            session, factory_id=data.factory_id, item_id=data.item_id,
            inventory_type=data.inventory_type, workspace_id=workspace_id
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Inventory record already exists for this item/type/factory combination"
            )

        inv_dict = data.model_dump()
        inv_dict['workspace_id'] = workspace_id
        inv_dict['created_by'] = user_id

        record = self.inv_dao.create(session, obj_in=inv_dict)

        # Create initial ledger entry if qty > 0
        if data.qty > 0:
            ledger_dict = {
                'workspace_id': workspace_id,
                'inventory_type': data.inventory_type,
                'factory_id': data.factory_id,
                'item_id': data.item_id,
                'transaction_type': 'manual_add',
                'quantity': data.qty,
                'unit_cost': data.avg_price,
                'total_cost': (data.avg_price * data.qty) if data.avg_price else None,
                'qty_before': 0,
                'qty_after': data.qty,
                'avg_price_before': None,
                'avg_price_after': data.avg_price,
                'source_type': 'manual',
                'notes': 'Initial inventory record created',
                'performed_by': user_id,
            }
            self.ledger_dao.create(session, obj_in=ledger_dict)

        return record

    def update_inventory(
        self, session: Session, inv_id: int, data: InventoryUpdate,
        workspace_id: int, user_id: int
    ) -> Inventory:
        """Update inventory record. Creates ledger entry if qty changes."""
        record = self.inv_dao.get_by_id_and_workspace(
            session, id=inv_id, workspace_id=workspace_id
        )
        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Inventory record with ID {inv_id} not found"
            )
        if record.is_deleted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot update a deleted inventory record"
            )

        old_qty = record.qty
        old_avg = record.avg_price

        update_dict = data.model_dump(exclude_unset=True, exclude_none=True)
        update_dict['updated_by'] = user_id

        updated = self.inv_dao.update(session, db_obj=record, obj_in=update_dict)

        # If qty changed, create ledger entry
        new_qty = update_dict.get('qty')
        if new_qty is not None and new_qty != old_qty:
            new_avg = update_dict.get('avg_price', old_avg)
            ledger_dict = {
                'workspace_id': workspace_id,
                'inventory_type': record.inventory_type,
                'factory_id': record.factory_id,
                'item_id': record.item_id,
                'transaction_type': 'inventory_adjustment',
                'quantity': abs(new_qty - old_qty),
                'unit_cost': new_avg,
                'total_cost': (new_avg * abs(new_qty - old_qty)) if new_avg else None,
                'qty_before': old_qty,
                'qty_after': new_qty,
                'avg_price_before': old_avg,
                'avg_price_after': new_avg,
                'source_type': 'adjustment',
                'notes': f'Quantity adjusted from {old_qty} to {new_qty}',
                'performed_by': user_id,
            }
            self.ledger_dao.create(session, obj_in=ledger_dict)

        return updated

    def get_inventory(self, session: Session, inv_id: int, workspace_id: int) -> Inventory:
        """Get inventory record by ID."""
        record = self.inv_dao.get_by_id_and_workspace(session, id=inv_id, workspace_id=workspace_id)
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Inventory record with ID {inv_id} not found")
        return record

    def list_inventory(
        self, session: Session, workspace_id: int,
        inventory_type: Optional[InventoryTypeEnum] = None,
        factory_id: Optional[int] = None,
        skip: int = 0, limit: int = 100
    ) -> List[Inventory]:
        """List inventory records with optional filters (includes zero-qty rows)."""
        return self.inv_dao.get_by_workspace(
            session, workspace_id=workspace_id,
            inventory_type=inventory_type, factory_id=factory_id,
            skip=skip, limit=limit
        )

    def get_inventory_page(
        self,
        session: Session,
        *,
        workspace_id: int,
        inventory_type: Optional[InventoryTypeEnum] = None,
        factory_id: Optional[int] = None,
        item_id: Optional[int] = None,
        search: Optional[str] = None,
        include_zero_qty: bool = False,
        skip: int = 0,
        limit: int = 50,
    ) -> InventoryListResponse:
        items = self.inv_dao.list_filtered(
            session,
            workspace_id=workspace_id,
            inventory_type=inventory_type,
            factory_id=factory_id,
            item_id=item_id,
            search=search,
            include_zero_qty=include_zero_qty,
            skip=skip,
            limit=limit,
        )
        total = self.inv_dao.count_filtered(
            session,
            workspace_id=workspace_id,
            inventory_type=inventory_type,
            factory_id=factory_id,
            item_id=item_id,
            search=search,
            include_zero_qty=include_zero_qty,
        )
        return InventoryListResponse(
            items=items,
            total=total,
            skip=skip,
            limit=limit,
            has_more=(skip + len(items)) < total,
        )

    def get_inventory_stats(
        self,
        session: Session,
        *,
        workspace_id: int,
        inventory_type: Optional[InventoryTypeEnum] = None,
        factory_id: Optional[int] = None,
        item_id: Optional[int] = None,
        search: Optional[str] = None,
        include_zero_qty: bool = False,
    ) -> InventoryStatsResponse:
        records, total_qty, estimated_value, by_type_rows = self.inv_dao.stats_filtered(
            session,
            workspace_id=workspace_id,
            inventory_type=inventory_type,
            factory_id=factory_id,
            item_id=item_id,
            search=search,
            include_zero_qty=include_zero_qty,
        )
        return InventoryStatsResponse(
            records=records,
            total_qty=total_qty,
            estimated_value=estimated_value or Decimal("0"),
            by_type=[
                InventoryStatsByTypeRow(
                    inventory_type=row_type,
                    unique_item_count=int(unique_count or 0),
                    total_qty=int(type_qty or 0),
                )
                for row_type, unique_count, type_qty in by_type_rows
            ],
        )

    def delete_inventory(self, session: Session, inv_id: int, workspace_id: int, user_id: int) -> Inventory:
        """Clear inventory stock to zero; ledger records the adjustment. Row stays active."""
        record = self.inv_dao.get_by_id_and_workspace(session, id=inv_id, workspace_id=workspace_id)
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Inventory record with ID {inv_id} not found")
        if record.is_deleted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot clear stock on a deactivated inventory record",
            )
        if record.qty <= 0:
            return record

        old_qty = record.qty
        old_avg = record.avg_price
        self.ledger_dao.create(session, obj_in={
            'workspace_id': workspace_id,
            'inventory_type': record.inventory_type,
            'factory_id': record.factory_id,
            'item_id': record.item_id,
            'transaction_type': 'inventory_adjustment',
            'quantity': old_qty,
            'unit_cost': old_avg,
            'total_cost': (old_avg * old_qty) if old_avg else None,
            'qty_before': old_qty,
            'qty_after': 0,
            'avg_price_before': old_avg,
            'avg_price_after': old_avg,
            'source_type': 'adjustment',
            'notes': 'Stock cleared',
            'performed_by': user_id,
        })
        record.qty = 0
        record.updated_by = user_id
        session.flush()
        return record

    def get_incoming_summary_for_factory(
        self,
        session: Session,
        *,
        workspace_id: int,
        factory_id: int,
    ) -> List[ItemIncomingSummary]:
        """Pending qty per item from open POs and inbound transfers to factory storage."""
        factory = factory_dao.get_by_id_and_workspace(
            session, id=factory_id, workspace_id=workspace_id
        )
        if not factory:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Factory with ID {factory_id} not found",
            )

        # item_id -> (total_qty, order_key -> IncomingOrderLine)
        OrderKey = Tuple[str, int]
        totals: DefaultDict[int, Decimal] = defaultdict(lambda: Decimal("0"))
        lines_by_item: DefaultDict[int, Dict[OrderKey, IncomingOrderLine]] = defaultdict(dict)

        pos = purchase_order_dao.list_for_destination(
            session,
            workspace_id=workspace_id,
            destination_type="storage",
            destination_id=factory_id,
        )
        po_wf_ids = {po.order_workflow_id for po in pos if po.order_workflow_id}
        po_terminal = terminal_status_ids_by_workflow(
            session, workspace_id=workspace_id, workflow_ids=po_wf_ids
        )
        open_po_ids: List[int] = []
        open_po_by_id = {}
        for po in pos:
            if is_order_terminal(
                workflow_id=po.order_workflow_id,
                current_status_id=po.current_status_id,
                terminal_by_wf=po_terminal,
            ):
                continue
            open_po_ids.append(po.id)
            open_po_by_id[po.id] = po

        if open_po_ids:
            po_items = purchase_order_item_dao.get_by_purchase_order_ids(
                session, workspace_id=workspace_id, purchase_order_ids=open_po_ids
            )
            for line in po_items:
                pending = Decimal(str(line.quantity_ordered or 0)) - Decimal(
                    str(line.quantity_received or 0)
                )
                if pending <= 0:
                    continue
                po = open_po_by_id[line.purchase_order_id]
                key: OrderKey = ("purchase", po.id)
                existing = lines_by_item[line.item_id].get(key)
                new_qty = (existing.pending_qty if existing else Decimal("0")) + pending
                lines_by_item[line.item_id][key] = IncomingOrderLine(
                    order_kind="purchase",
                    order_id=po.id,
                    order_number=po.po_number,
                    status_name=po.current_status.name if po.current_status else None,
                    pending_qty=new_qty,
                )
                totals[line.item_id] += pending

        transfers = transfer_order_dao.list_inbound_to_storage_incomplete(
            session, workspace_id=workspace_id, factory_id=factory_id
        )
        tr_ids = [tr.id for tr in transfers]
        tr_by_id = {tr.id: tr for tr in transfers}
        if tr_ids:
            tr_items = transfer_order_item_dao.get_by_transfer_order_ids(
                session, workspace_id=workspace_id, transfer_order_ids=tr_ids
            )
            for line in tr_items:
                qty = Decimal(str(line.quantity or 0))
                if qty <= 0:
                    continue
                tr = tr_by_id[line.transfer_order_id]
                key = ("transfer", tr.id)
                existing = lines_by_item[line.item_id].get(key)
                new_qty = (existing.pending_qty if existing else Decimal("0")) + qty
                lines_by_item[line.item_id][key] = IncomingOrderLine(
                    order_kind="transfer",
                    order_id=tr.id,
                    order_number=tr.transfer_number,
                    status_name=tr.current_status.name if tr.current_status else None,
                    pending_qty=new_qty,
                )
                totals[line.item_id] += qty

        summaries: List[ItemIncomingSummary] = []
        for item_id in sorted(totals.keys()):
            order_lines = list(lines_by_item[item_id].values())
            summaries.append(
                ItemIncomingSummary(
                    factory_id=factory_id,
                    item_id=item_id,
                    total_pending_qty=totals[item_id],
                    order_count=len(order_lines),
                    orders=order_lines,
                )
            )
        return summaries

    def get_incoming_summary(
        self,
        session: Session,
        *,
        workspace_id: int,
        factory_id: Optional[int] = None,
    ) -> List[ItemIncomingSummary]:
        """Pending qty per item; one factory or all active factories in workspace."""
        if factory_id is not None:
            return self.get_incoming_summary_for_factory(
                session, workspace_id=workspace_id, factory_id=factory_id
            )

        factories = factory_dao.get_active_factories(
            session, workspace_id=workspace_id, skip=0, limit=500
        )
        summaries: List[ItemIncomingSummary] = []
        for factory in factories:
            summaries.extend(
                self.get_incoming_summary_for_factory(
                    session, workspace_id=workspace_id, factory_id=factory.id
                )
            )
        return summaries


inventory_manager = InventoryManager()
