"""Production Batch Manager for business logic"""
from collections import defaultdict
from typing import List, Optional
from datetime import datetime
from decimal import Decimal
from sqlalchemy.orm import Session
from app.managers.base_manager import BaseManager
from app.models.production_batch import ProductionBatch
from app.models.production_batch_item import ProductionBatchItem
from app.dao.production_batch import production_batch_dao
from app.dao.production_batch_item import production_batch_item_dao
from app.dao.production_line import production_line_dao
from app.dao.production_formula import production_formula_dao
from app.dao.production_formula_item import production_formula_item_dao
from app.dao.item import item_dao
from app.dao.inventory import inventory_dao
from app.dao.inventory_ledger import inventory_ledger_dao
from app.dao.product_ledger import product_ledger_dao
from app.managers.product_manager import product_manager
from app.models.enums import InventoryTypeEnum
from app.schemas.production_batch import ProductionBatchCreate, ProductionBatchUpdate
from app.schemas.production_batch_item import ProductionBatchItemCreate, ProductionBatchItemUpdate


class ProductionBatchManager(BaseManager[ProductionBatch]):
    """
    STANDALONE MANAGER: Production batch business logic.

    Manages: ProductionBatch and ProductionBatchItem entities
    Operations: CRUD, batch workflow (start, complete, cancel), variance calculation

    Does NOT commit transactions - that's the service layer's responsibility.
    """

    VALID_STATUSES = {'draft', 'in_progress', 'completed', 'cancelled'}
    VALID_ITEM_ROLES = {'input', 'output', 'waste', 'byproduct'}

    def __init__(self):
        super().__init__(ProductionBatch)
        self.batch_dao = production_batch_dao
        self.batch_item_dao = production_batch_item_dao
        self.formula_dao = production_formula_dao
        self.formula_item_dao = production_formula_item_dao

    # ─── Batch CRUD ─────────────────────────────────────────────────

    def create_batch(
        self,
        session: Session,
        batch_data: ProductionBatchCreate,
        workspace_id: int,
        user_id: int
    ) -> ProductionBatch:
        """
        Create a new production batch.

        Validates:
        - Production line exists and belongs to workspace
        - Formula exists and belongs to workspace (if provided)
        - Auto-generates batch_number

        If formula_id is provided and status is 'draft', expected values
        can be populated later via start_batch.
        """
        # Validate production line
        line = production_line_dao.get_by_id_and_workspace(
            session, id=batch_data.production_line_id, workspace_id=workspace_id
        )
        if not line:
            raise ValueError(f"Production line {batch_data.production_line_id} not found")
        if not line.is_active:
            raise ValueError(f"Production line {batch_data.production_line_id} is not active")

        # Validate formula if provided
        if batch_data.formula_id is not None:
            formula = self.formula_dao.get_by_id_and_workspace(
                session, id=batch_data.formula_id, workspace_id=workspace_id
            )
            if not formula:
                raise ValueError(f"Production formula {batch_data.formula_id} not found")
            if not formula.is_active:
                raise ValueError(f"Production formula {batch_data.formula_id} is not active")

        # Generate batch number
        batch_number = self.batch_dao.generate_batch_number(session, workspace_id=workspace_id)

        # Build creation dict
        batch_dict = batch_data.model_dump()
        batch_dict['workspace_id'] = workspace_id
        batch_dict['batch_number'] = batch_number
        batch_dict['created_by'] = user_id

        return self.batch_dao.create(session, obj_in=batch_dict)

    def update_batch(
        self,
        session: Session,
        batch_id: int,
        batch_data: ProductionBatchUpdate,
        workspace_id: int,
        user_id: int
    ) -> ProductionBatch:
        """
        Update a production batch (only draft or in_progress batches).

        Cannot update completed or cancelled batches.
        """
        batch = self.batch_dao.get_by_id_and_workspace(
            session, id=batch_id, workspace_id=workspace_id
        )
        if not batch:
            raise ValueError(f"Production batch {batch_id} not found")
        if batch.status in ('completed', 'cancelled'):
            raise ValueError(f"Cannot update a {batch.status} batch")

        update_dict = batch_data.model_dump(exclude_unset=True)

        # Don't allow direct status changes via update - use start/complete/cancel
        if 'status' in update_dict:
            raise ValueError("Use start_batch, complete_batch, or cancel_batch to change status")

        # Validate formula if being changed
        if 'formula_id' in update_dict and update_dict['formula_id'] is not None:
            formula = self.formula_dao.get_by_id_and_workspace(
                session, id=update_dict['formula_id'], workspace_id=workspace_id
            )
            if not formula:
                raise ValueError(f"Production formula {update_dict['formula_id']} not found")

        update_dict['updated_by'] = user_id
        return self.batch_dao.update(session, db_obj=batch, obj_in=update_dict)

    def get_batch(
        self,
        session: Session,
        batch_id: int,
        workspace_id: int
    ) -> Optional[ProductionBatch]:
        """Get batch by ID within workspace."""
        return self.batch_dao.get_by_id_and_workspace(
            session, id=batch_id, workspace_id=workspace_id
        )

    def get_batches(
        self,
        session: Session,
        workspace_id: int,
        production_line_id: Optional[int] = None,
        formula_id: Optional[int] = None,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[ProductionBatch]:
        """Get batches with optional filtering."""
        if production_line_id is not None:
            return self.batch_dao.get_by_production_line(
                session, production_line_id=production_line_id,
                workspace_id=workspace_id, skip=skip, limit=limit
            )
        elif formula_id is not None:
            return self.batch_dao.get_by_formula(
                session, formula_id=formula_id,
                workspace_id=workspace_id, skip=skip, limit=limit
            )
        elif status is not None:
            return self.batch_dao.get_by_status(
                session, status=status,
                workspace_id=workspace_id, skip=skip, limit=limit
            )
        else:
            return self.batch_dao.get_by_workspace(
                session, workspace_id=workspace_id, skip=skip, limit=limit
            )

    def delete_batch(
        self,
        session: Session,
        batch_id: int,
        workspace_id: int
    ) -> ProductionBatch:
        """
        Cancel a batch (soft delete via status change).

        Only draft batches can be deleted/cancelled this way.
        In-progress batches should use cancel_batch instead.
        """
        batch = self.batch_dao.get_by_id_and_workspace(
            session, id=batch_id, workspace_id=workspace_id
        )
        if not batch:
            raise ValueError(f"Production batch {batch_id} not found")
        if batch.status not in ('draft',):
            raise ValueError(
                f"Only draft batches can be deleted. Current status: {batch.status}. "
                f"Use cancel_batch for in-progress batches."
            )

        return self.batch_dao.update(
            session, db_obj=batch, obj_in={'status': 'cancelled'}
        )

    # ─── Batch Workflow ─────────────────────────────────────────────

    def start_batch(
        self,
        session: Session,
        batch_id: int,
        workspace_id: int,
        user_id: int,
        target_output_quantity: Optional[int] = None,
    ) -> ProductionBatch:
        """
        Start a production batch (draft → in_progress).

        Validates all input items have sufficient storage — hard blocks if any are short.
        Deducts input items from storage and writes ledger entries.
        Stores target_output_quantity as expected_output_quantity for record-keeping.
        """
        batch = self.batch_dao.get_by_id_and_workspace(
            session, id=batch_id, workspace_id=workspace_id
        )
        if not batch:
            raise ValueError(f"Production batch {batch_id} not found")
        if batch.status != 'draft':
            raise ValueError(f"Can only start draft batches. Current status: {batch.status}")

        # Get factory_id from production line (default source for storage deductions)
        line = production_line_dao.get_by_id_and_workspace(
            session, id=batch.production_line_id, workspace_id=workspace_id
        )
        if not line:
            raise ValueError(f"Production line {batch.production_line_id} not found")
        factory_id = line.factory_id

        # Require at least one item before starting
        all_batch_items = self.batch_item_dao.get_by_batch(
            session, batch_id=batch_id, workspace_id=workspace_id
        )
        if not all_batch_items:
            raise ValueError("Cannot start a batch with no items. Add at least one item before starting.")

        # Validate all input items have sufficient inventory before doing anything
        input_items = [bi for bi in all_batch_items if bi.item_role == 'input']

        shortfalls = []
        for bi in input_items:
            qty_needed = bi.actual_quantity or bi.expected_quantity
            if not qty_needed:
                continue
            source_factory_id = (
                bi.source_location_id
                if bi.source_location_type == 'storage' and bi.source_location_id
                else factory_id
            )
            inv = inventory_dao.get_by_factory_item_type(
                session, factory_id=source_factory_id, item_id=bi.item_id,
                inventory_type=InventoryTypeEnum.STORAGE, workspace_id=workspace_id
            )
            available = inv.qty if inv else 0
            if available < qty_needed:
                shortfalls.append({
                    'item_id': bi.item_id,
                    'required_qty': qty_needed,
                    'available_qty': available,
                })

        if shortfalls:
            lines = [
                f"item_id={s['item_id']} (required {s['required_qty']}, available {s['available_qty']})"
                for s in shortfalls
            ]
            raise ValueError(
                f"Insufficient inventory for {len(shortfalls)} input item(s): {'; '.join(lines)}. "
                f"Replenish storage before starting this batch."
            )

        # All items OK — deduct from inventory and write ledger entries
        note = f"SYSTEM - PRODUCTION BATCH START | {batch.batch_number}"
        for bi in input_items:
            qty_to_deduct = bi.actual_quantity or bi.expected_quantity
            if not qty_to_deduct:
                continue
            source_factory_id = (
                bi.source_location_id
                if bi.source_location_type == 'storage' and bi.source_location_id
                else factory_id
            )
            inv = inventory_dao.get_by_factory_item_type(
                session, factory_id=source_factory_id, item_id=bi.item_id,
                inventory_type=InventoryTypeEnum.STORAGE, workspace_id=workspace_id
            )
            old_qty = inv.qty
            new_qty = old_qty - qty_to_deduct
            avg_price = inv.avg_price if inv.avg_price is not None else Decimal('0')

            inv.qty = new_qty
            session.flush()

            inventory_ledger_dao.create(session, obj_in={
                'workspace_id': workspace_id,
                'inventory_type': InventoryTypeEnum.STORAGE,
                'factory_id': source_factory_id,
                'item_id': bi.item_id,
                'transaction_type': 'consumption',
                'quantity': qty_to_deduct,
                'unit_cost': avg_price if avg_price else None,
                'total_cost': (avg_price * qty_to_deduct) if avg_price else None,
                'qty_before': old_qty,
                'qty_after': new_qty,
                'avg_price_before': avg_price if avg_price else None,
                'avg_price_after': avg_price if avg_price else None,
                'source_type': 'production_batch',
                'source_id': batch.id,
                'notes': note,
                'performed_by': user_id,
            })

        now = datetime.utcnow()
        update_data = {
            'status': 'in_progress',
            'started_by': user_id,
            'started_at': now,
            'actual_start_time': now,
            'updated_by': user_id,
        }
        if target_output_quantity is not None:
            update_data['expected_output_quantity'] = target_output_quantity

        return self.batch_dao.update(session, db_obj=batch, obj_in=update_data)

    def complete_batch(
        self,
        session: Session,
        batch_id: int,
        workspace_id: int,
        user_id: int,
        actual_output_quantity: Optional[int] = None,
        actual_duration_minutes: Optional[int] = None,
        notes: Optional[str] = None
    ) -> ProductionBatch:
        """
        Complete a production batch (in_progress → completed).

        - Calculates variance between expected and actual values.
        - Auto-posts output/byproduct items to finished goods (products).
        - Auto-posts waste items to damaged ledger.
        - All ledger entries are tagged SYSTEM - PRODUCTION BATCH COMPLETE.
        """
        batch = self.batch_dao.get_by_id_and_workspace(
            session, id=batch_id, workspace_id=workspace_id
        )
        if not batch:
            raise ValueError(f"Production batch {batch_id} not found")
        if batch.status != 'in_progress':
            raise ValueError(f"Can only complete in-progress batches. Current status: {batch.status}")

        # Get factory from production line
        line = production_line_dao.get_by_id_and_workspace(
            session, id=batch.production_line_id, workspace_id=workspace_id
        )
        if not line:
            raise ValueError(f"Production line {batch.production_line_id} not found")
        factory_id = line.factory_id

        now = datetime.utcnow()
        update_data = {
            'status': 'completed',
            'completed_by': user_id,
            'completed_at': now,
            'actual_end_time': now,
            'updated_by': user_id,
        }

        if actual_output_quantity is not None:
            update_data['actual_output_quantity'] = actual_output_quantity
        if actual_duration_minutes is not None:
            update_data['actual_duration_minutes'] = actual_duration_minutes
        if notes is not None:
            update_data['notes'] = notes

        # Calculate output variance
        actual_out = actual_output_quantity or batch.actual_output_quantity
        expected_out = batch.expected_output_quantity
        if actual_out is not None and expected_out is not None and expected_out > 0:
            variance = actual_out - expected_out
            update_data['output_variance_quantity'] = variance
            update_data['output_variance_percentage'] = Decimal(
                str(round((variance / expected_out) * 100, 2))
            )
            update_data['efficiency_percentage'] = Decimal(
                str(round((actual_out / expected_out) * 100, 2))
            )

        updated_batch = self.batch_dao.update(session, db_obj=batch, obj_in=update_data)

        # Calculate per-item variances
        self._calculate_batch_item_variances(session, batch_id, workspace_id)

        # Post outputs and byproducts to finished goods
        system_note = f"SYSTEM - PRODUCTION BATCH COMPLETE | {batch.batch_number}"
        all_items = self.batch_item_dao.get_by_batch(session, batch_id=batch_id, workspace_id=workspace_id)

        for bi in all_items:
            qty = bi.actual_quantity or bi.expected_quantity
            if not qty or qty <= 0:
                continue

            dest_factory_id = (
                bi.destination_location_id
                if bi.destination_location_type == 'inventory' and bi.destination_location_id
                else factory_id
            )

            if bi.item_role in ('output', 'byproduct'):
                product_manager.apply_production_output(
                    session,
                    workspace_id=workspace_id,
                    user_id=user_id,
                    factory_id=dest_factory_id,
                    item_id=bi.item_id,
                    quantity=qty,
                    batch_id=batch_id,
                    notes=system_note,
                )

            elif bi.item_role == 'waste':
                inv_type = InventoryTypeEnum.DAMAGED
                damaged = inventory_dao.get_by_factory_item_type(
                    session, factory_id=dest_factory_id, item_id=bi.item_id,
                    inventory_type=inv_type, workspace_id=workspace_id
                )
                if not damaged:
                    damaged = inventory_dao.create(session, obj_in={
                        'workspace_id': workspace_id,
                        'inventory_type': inv_type,
                        'factory_id': dest_factory_id,
                        'item_id': bi.item_id,
                        'qty': 0,
                        'avg_price': None,
                        'created_by': user_id,
                    })

                old_qty = damaged.qty
                new_qty = old_qty + qty
                avg_price = damaged.avg_price if damaged.avg_price is not None else None
                damaged.qty = new_qty
                session.flush()

                inventory_ledger_dao.create(session, obj_in={
                    'workspace_id': workspace_id,
                    'inventory_type': inv_type,
                    'factory_id': dest_factory_id,
                    'item_id': bi.item_id,
                    'transaction_type': 'damaged',
                    'quantity': qty,
                    'unit_cost': avg_price,
                    'total_cost': (avg_price * qty) if avg_price else None,
                    'qty_before': old_qty,
                    'qty_after': new_qty,
                    'avg_price_before': avg_price,
                    'avg_price_after': avg_price,
                    'source_type': 'production_batch',
                    'source_id': batch_id,
                    'notes': system_note,
                    'performed_by': user_id,
                })

        return updated_batch

    def cancel_batch(
        self,
        session: Session,
        batch_id: int,
        workspace_id: int,
        user_id: int,
        notes: Optional[str] = None
    ) -> ProductionBatch:
        """
        Cancel a production batch (draft or in_progress → cancelled).
        """
        batch = self.batch_dao.get_by_id_and_workspace(
            session, id=batch_id, workspace_id=workspace_id
        )
        if not batch:
            raise ValueError(f"Production batch {batch_id} not found")
        if batch.status not in ('draft', 'in_progress'):
            raise ValueError(
                f"Can only cancel draft or in-progress batches. Current status: {batch.status}"
            )

        update_data = {
            'status': 'cancelled',
            'updated_by': user_id,
        }
        if notes is not None:
            update_data['notes'] = notes

        return self.batch_dao.update(session, db_obj=batch, obj_in=update_data)

    # ─── Batch Item CRUD ────────────────────────────────────────────

    def add_batch_item(
        self,
        session: Session,
        item_data: ProductionBatchItemCreate,
        workspace_id: int
    ) -> ProductionBatchItem:
        """
        Add an item to a batch.

        Validates batch exists, is not completed/cancelled, and item exists.
        """
        # Validate batch
        batch = self.batch_dao.get_by_id_and_workspace(
            session, id=item_data.batch_id, workspace_id=workspace_id
        )
        if not batch:
            raise ValueError(f"Production batch {item_data.batch_id} not found")
        if batch.status in ('completed', 'cancelled'):
            raise ValueError(f"Cannot add items to a {batch.status} batch")

        # Validate item
        item = item_dao.get(session, id=item_data.item_id)
        if not item:
            raise ValueError(f"Item {item_data.item_id} not found")
        if item.workspace_id != workspace_id:
            raise ValueError(
                f"Item {item_data.item_id} does not belong to workspace {workspace_id}"
            )

        if item_data.item_role not in self.VALID_ITEM_ROLES:
            raise ValueError(
                f"Invalid item_role '{item_data.item_role}'. Must be one of: {', '.join(self.VALID_ITEM_ROLES)}"
            )

        item_dict = item_data.model_dump()
        item_dict['workspace_id'] = workspace_id

        return self.batch_item_dao.create(session, obj_in=item_dict)

    def update_batch_item(
        self,
        session: Session,
        batch_item_id: int,
        item_data: ProductionBatchItemUpdate,
        workspace_id: int
    ) -> ProductionBatchItem:
        """Update a batch item (e.g., log actual quantities)."""
        batch_item = self.batch_item_dao.get_by_id_and_workspace(
            session, id=batch_item_id, workspace_id=workspace_id
        )
        if not batch_item:
            raise ValueError(f"Batch item {batch_item_id} not found")

        # Check parent batch is not completed/cancelled
        batch = self.batch_dao.get_by_id_and_workspace(
            session, id=batch_item.batch_id, workspace_id=workspace_id
        )
        if batch and batch.status in ('completed', 'cancelled'):
            raise ValueError(f"Cannot update items in a {batch.status} batch")

        update_dict = item_data.model_dump(exclude_unset=True)

        if 'item_role' in update_dict and update_dict['item_role'] not in self.VALID_ITEM_ROLES:
            raise ValueError(
                f"Invalid item_role '{update_dict['item_role']}'. Must be one of: {', '.join(self.VALID_ITEM_ROLES)}"
            )

        return self.batch_item_dao.update(session, db_obj=batch_item, obj_in=update_dict)

    def remove_batch_item(
        self,
        session: Session,
        batch_item_id: int,
        workspace_id: int
    ) -> ProductionBatchItem:
        """Remove an item from a batch (hard delete). Only for draft/in_progress batches."""
        batch_item = self.batch_item_dao.get_by_id_and_workspace(
            session, id=batch_item_id, workspace_id=workspace_id
        )
        if not batch_item:
            raise ValueError(f"Batch item {batch_item_id} not found")

        batch = self.batch_dao.get_by_id_and_workspace(
            session, id=batch_item.batch_id, workspace_id=workspace_id
        )
        if batch and batch.status in ('completed', 'cancelled'):
            raise ValueError(f"Cannot remove items from a {batch.status} batch")

        return self.batch_item_dao.remove(session, id=batch_item_id)

    def get_batch_items(
        self,
        session: Session,
        batch_id: int,
        workspace_id: int,
        item_role: Optional[str] = None
    ) -> List[ProductionBatchItem]:
        """Get items for a batch with optional role filter."""
        batch = self.batch_dao.get_by_id_and_workspace(
            session, id=batch_id, workspace_id=workspace_id
        )
        if not batch:
            raise ValueError(f"Production batch {batch_id} not found")

        if item_role:
            if item_role not in self.VALID_ITEM_ROLES:
                raise ValueError(
                    f"Invalid item_role '{item_role}'. Must be one of: {', '.join(self.VALID_ITEM_ROLES)}"
                )
            return self.batch_item_dao.get_by_batch_and_role(
                session, batch_id=batch_id, item_role=item_role, workspace_id=workspace_id
            )

        return self.batch_item_dao.get_by_batch(
            session, batch_id=batch_id, workspace_id=workspace_id
        )

    # ─── Helpers ────────────────────────────────────────────────────

    def _calculate_batch_item_variances(
        self,
        session: Session,
        batch_id: int,
        workspace_id: int
    ) -> None:
        """Calculate variance for all batch items that have both expected and actual quantities."""
        batch_items = self.batch_item_dao.get_by_batch(
            session, batch_id=batch_id, workspace_id=workspace_id
        )
        for bi in batch_items:
            if bi.expected_quantity is not None and bi.actual_quantity is not None and bi.expected_quantity > 0:
                variance = bi.actual_quantity - bi.expected_quantity
                variance_pct = Decimal(str(round((variance / bi.expected_quantity) * 100, 2)))
                self.batch_item_dao.update(
                    session, db_obj=bi,
                    obj_in={'variance_quantity': variance, 'variance_percentage': variance_pct}
                )

    def post_outputs_to_finished_goods(
        self,
        session: Session,
        batch_id: int,
        workspace_id: int,
        user_id: int,
        *,
        include_byproducts: bool = True,
    ) -> int:
        """
        Post output and optional byproduct quantities to finished goods (products) for the batch's factory.

        Idempotent: raises if any product ledger row already exists for this batch.

        Returns:
            Number of distinct items posted (ledger lines created).
        """
        if product_ledger_dao.exists_for_production_batch(
            session, workspace_id=workspace_id, batch_id=batch_id
        ):
            raise ValueError(
                "Finished goods for this batch have already been posted. "
                "Each batch can only be received into products once."
            )

        batch = self.batch_dao.get_by_id_and_workspace(
            session, id=batch_id, workspace_id=workspace_id
        )
        if not batch:
            raise ValueError(f"Production batch {batch_id} not found")
        if batch.status != "completed":
            raise ValueError("Only completed batches can post outputs to finished goods")

        line = production_line_dao.get_by_id_and_workspace(
            session, id=batch.production_line_id, workspace_id=workspace_id
        )
        if not line:
            raise ValueError("Production line not found for this batch")
        factory_id = line.factory_id

        roles = {"output"}
        if include_byproducts:
            roles.add("byproduct")

        merged_qty: defaultdict[int, int] = defaultdict(int)
        batch_items = self.batch_item_dao.get_by_batch(
            session, batch_id=batch_id, workspace_id=workspace_id
        )
        for bi in batch_items:
            if bi.item_role not in roles:
                continue
            qty = bi.actual_quantity if bi.actual_quantity is not None else bi.expected_quantity
            if qty is None or qty <= 0:
                continue
            merged_qty[bi.item_id] += int(qty)

        if not merged_qty and batch.actual_output_quantity and batch.actual_output_quantity > 0 and batch.formula_id:
            outs = production_formula_item_dao.get_by_formula_and_role(
                session,
                formula_id=batch.formula_id,
                item_role="output",
                workspace_id=workspace_id,
            )
            if len(outs) == 1:
                merged_qty[outs[0].item_id] += int(batch.actual_output_quantity)

        if not merged_qty:
            raise ValueError(
                "No quantities to post. Enter actual amounts on output/byproduct lines, "
                "or set actual output quantity on the batch when the formula has a single output item."
            )

        for item_id, qty in merged_qty.items():
            product_manager.apply_production_output(
                session,
                workspace_id=workspace_id,
                user_id=user_id,
                factory_id=factory_id,
                item_id=item_id,
                quantity=qty,
                batch_id=batch_id,
                unit_cost=None,
            )

        return len(merged_qty)


# Singleton instance
production_batch_manager = ProductionBatchManager()
