"""Ledger Manager for ledger queries and reconciliation"""
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from datetime import datetime, date
from decimal import Decimal
from app.managers.base_manager import BaseManager
from app.models.machine_item_ledger import MachineItemLedger
from app.models.project_component_item_ledger import ProjectComponentItemLedger
from app.models.inventory_ledger import InventoryLedger
from app.models.enums import InventoryTypeEnum
from app.dao.machine_item_ledger import machine_item_ledger_dao
from app.dao.project_component_item_ledger import project_component_item_ledger_dao
from app.dao.inventory_ledger import inventory_ledger_dao
from app.dao.machine_item import machine_item_dao
from app.dao.inventory import inventory_dao
from app.schemas.inventory_ledger import InventoryLedgerCreate


class LedgerManager(BaseManager[MachineItemLedger]):
    """
    UNIFIED LEDGER MANAGER: Queries and reconciliation for all ledgers.

    Handles ledger types:
    - Machine Item Ledger
    - Project Component Item Ledger
    - Inventory Ledger (unified: STORAGE, DAMAGED, WASTE, SCRAP, finished goods)

    Does NOT commit transactions - that's the service layer's responsibility.
    """

    def __init__(self):
        super().__init__(MachineItemLedger)
        self.machine_ledger_dao = machine_item_ledger_dao
        self.project_ledger_dao = project_component_item_ledger_dao
        self.inventory_ledger_dao = inventory_ledger_dao

        # Snapshot DAOs (for reconciliation)
        self.machine_item_dao = machine_item_dao
        self.inventory_dao = inventory_dao

    # ============================================================================
    # MACHINE LEDGER OPERATIONS
    # ============================================================================

    def get_machine_ledger(
        self,
        session: Session,
        machine_id: int,
        workspace_id: int,
        item_id: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        transaction_type: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[MachineItemLedger]:
        """
        Get machine ledger entries with optional filters.

        Always scoped to the given machine. `item_id` is optional: when omitted
        every ledger row for the machine is returned.

        Args:
            session: Database session
            machine_id: Machine ID (required — list is always scoped to one machine)
            workspace_id: Workspace ID
            item_id: Optional item filter
            start_date: Optional start date filter
            end_date: Optional end date filter
            transaction_type: Optional transaction type filter
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            List of machine ledger entries (newest first)

        NOTE: The date-range and transaction-type DAO helpers below currently
        scope to workspace only — they don't filter by machine/item. The
        date/transaction filters are exposed for completeness but combining
        them with the machine scope will not narrow the result to the chosen
        machine. Tracked as a separate cleanup.
        """
        if start_date and end_date:
            return self.machine_ledger_dao.get_by_date_range(
                session,
                workspace_id=workspace_id,
                start_date=start_date,
                end_date=end_date,
                skip=skip,
                limit=limit
            )
        elif transaction_type:
            return self.machine_ledger_dao.get_by_transaction_type(
                session,
                transaction_type=transaction_type,
                workspace_id=workspace_id,
                skip=skip,
                limit=limit
            )
        elif item_id is not None:
            return self.machine_ledger_dao.get_by_machine_and_item(
                session,
                machine_id=machine_id,
                item_id=item_id,
                workspace_id=workspace_id,
                skip=skip,
                limit=limit
            )
        else:
            # No item picked → list every entry for the machine.
            return self.machine_ledger_dao.get_by_machine(
                session,
                machine_id=machine_id,
                workspace_id=workspace_id,
                skip=skip,
                limit=limit
            )

    def get_machine_balance(
        self,
        session: Session,
        machine_id: int,
        item_id: int,
        workspace_id: int
    ) -> Tuple[int, Decimal]:
        """
        Calculate current machine balance from ledger.

        Args:
            session: Database session
            machine_id: Machine ID
            item_id: Item ID
            workspace_id: Workspace ID

        Returns:
            Tuple of (quantity, total_value)
        """
        return self.machine_ledger_dao.calculate_balance(
            session,
            machine_id=machine_id,
            item_id=item_id,
            workspace_id=workspace_id
        )

    def reconcile_machine_item(
        self,
        session: Session,
        machine_id: int,
        item_id: int,
        workspace_id: int,
        user_id: int
    ) -> Dict[str, Any]:
        """
        Reconcile machine ledger vs machine_items snapshot.

        Business logic:
        - Ledger is source of truth
        - If snapshot doesn't match ledger, create adjustment transaction
        - Update snapshot to match ledger

        Args:
            session: Database session
            machine_id: Machine ID
            item_id: Item ID
            workspace_id: Workspace ID
            user_id: User performing reconciliation

        Returns:
            Dictionary with reconciliation results

        Note:
            This method does NOT commit. Service layer must commit.
        """
        # Get balance from ledger
        ledger_qty, ledger_value = self.machine_ledger_dao.calculate_balance(
            session,
            machine_id=machine_id,
            item_id=item_id,
            workspace_id=workspace_id
        )

        # Get snapshot
        snapshot = self.machine_item_dao.get_by_machine_and_item(
            session,
            machine_id=machine_id,
            item_id=item_id,
            workspace_id=workspace_id
        )

        if not snapshot:
            return {
                'status': 'error',
                'ledger_qty': ledger_qty,
                'snapshot_qty': 0,
                'discrepancy': ledger_qty,
                'adjustment_created': False,
                'error': 'Snapshot missing for item with ledger transactions'
            }

        snapshot_qty = snapshot.qty
        discrepancy = ledger_qty - snapshot_qty

        if discrepancy == 0:
            return {
                'status': 'balanced',
                'ledger_qty': ledger_qty,
                'snapshot_qty': snapshot_qty,
                'discrepancy': 0,
                'adjustment_created': False
            }

        # Create adjustment
        latest_entry = self.machine_ledger_dao.get_latest_entry(
            session,
            machine_id=machine_id,
            item_id=item_id,
            workspace_id=workspace_id
        )

        avg_price = latest_entry.avg_price_after if latest_entry else Decimal('0.00')

        # NOTE: Build as a dict (bypassing MachineItemLedgerCreate) so that
        # workspace_id and performed_by actually persist — they're not part of
        # the Pydantic schema and would otherwise be silently dropped.
        adjustment_payload: Dict[str, Any] = {
            'workspace_id': workspace_id,
            'machine_id': machine_id,
            'item_id': item_id,
            'transaction_type': 'inventory_adjustment',
            'quantity': abs(discrepancy),
            'unit_cost': avg_price,
            'total_cost': abs(discrepancy) * avg_price,
            'qty_before': snapshot_qty,
            'qty_after': ledger_qty,
            'value_before': snapshot_qty * avg_price,
            'value_after': ledger_qty * avg_price,
            'avg_price_before': avg_price,
            'avg_price_after': avg_price,
            'source_type': 'reconciliation',
            'notes': f"Reconciliation adjustment: Snapshot was {snapshot_qty}, ledger shows {ledger_qty}. Discrepancy: {discrepancy}",
            'performed_by': user_id,
        }

        self.machine_ledger_dao.create(session, obj_in=adjustment_payload)

        # Update snapshot
        snapshot.qty = ledger_qty
        session.flush()

        return {
            'status': 'adjusted',
            'ledger_qty': ledger_qty,
            'snapshot_qty': snapshot_qty,
            'discrepancy': discrepancy,
            'adjustment_created': True
        }

    # ============================================================================
    # PROJECT COMPONENT LEDGER OPERATIONS
    # ============================================================================

    def get_project_component_ledger(
        self,
        session: Session,
        project_component_id: int,
        workspace_id: int,
        item_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[ProjectComponentItemLedger]:
        """
        Get project component consumption ledger.

        Args:
            session: Database session
            project_component_id: Project component ID
            workspace_id: Workspace ID
            item_id: Optional item ID filter
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            List of project component ledger entries (newest first)
        """
        if item_id:
            return self.project_ledger_dao.get_by_component_and_item(
                session,
                project_component_id=project_component_id,
                item_id=item_id,
                workspace_id=workspace_id,
                skip=skip,
                limit=limit
            )
        else:
            return self.project_ledger_dao.get_by_component(
                session,
                project_component_id=project_component_id,
                workspace_id=workspace_id,
                skip=skip,
                limit=limit
            )

    def calculate_project_component_total_cost(
        self,
        session: Session,
        project_component_id: int,
        workspace_id: int
    ) -> Decimal:
        """
        Calculate total cost of all items consumed by a project component.

        Business logic:
        - Sum total_cost from all ledger entries
        - Used for project budgeting and cost tracking

        Args:
            session: Database session
            project_component_id: Project component ID
            workspace_id: Workspace ID

        Returns:
            Total cost (Decimal)
        """
        return self.project_ledger_dao.calculate_total_cost_for_component(
            session,
            project_component_id=project_component_id,
            workspace_id=workspace_id
        )

    # ============================================================================
    # INVENTORY LEDGER (Finished Goods) OPERATIONS
    # ============================================================================

    def get_inventory_ledger(
        self,
        session: Session,
        workspace_id: int,
        inventory_type: Optional[InventoryTypeEnum] = None,
        factory_id: Optional[int] = None,
        item_id: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        transaction_type: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[InventoryLedger]:
        """
        Get unified inventory ledger entries with optional filters.

        All scoping params (inventory_type, factory_id, item_id) are optional —
        callers can list every ledger entry in a workspace by passing only
        workspace_id.

        Args:
            session: Database session
            workspace_id: Workspace ID (required for isolation)
            inventory_type: Optional inventory type filter (STORAGE/DAMAGED/WASTE/SCRAP)
            factory_id: Optional factory filter
            item_id: Optional item filter
            start_date: Optional start date filter
            end_date: Optional end date filter
            transaction_type: Optional transaction type filter
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            List of inventory ledger entries (newest first)
        """
        if start_date and end_date:
            return self.inventory_ledger_dao.get_by_date_range(
                session,
                workspace_id=workspace_id,
                start_date=start_date,
                end_date=end_date,
                inventory_type=inventory_type,
                factory_id=factory_id,
                item_id=item_id,
                skip=skip,
                limit=limit,
            )
        if transaction_type:
            return self.inventory_ledger_dao.get_by_transaction_type(
                session,
                transaction_type=transaction_type,
                workspace_id=workspace_id,
                inventory_type=inventory_type,
                factory_id=factory_id,
                item_id=item_id,
                skip=skip,
                limit=limit,
            )
        return self.inventory_ledger_dao.get_by_workspace(
            session,
            workspace_id=workspace_id,
            inventory_type=inventory_type,
            factory_id=factory_id,
            item_id=item_id,
            skip=skip,
            limit=limit,
        )

    def get_inventory_balance(
        self,
        session: Session,
        factory_id: int,
        item_id: int,
        inventory_type: InventoryTypeEnum,
        workspace_id: int
    ) -> Tuple[int, Decimal]:
        """
        Calculate current inventory balance from ledger for a single
        (factory, item, inventory_type) bucket.

        Args:
            session: Database session
            factory_id: Factory ID
            item_id: Item ID
            inventory_type: Inventory type bucket (each type has its own balance)
            workspace_id: Workspace ID

        Returns:
            Tuple of (quantity, total_value)
        """
        return self.inventory_ledger_dao.calculate_balance(
            session,
            factory_id=factory_id,
            item_id=item_id,
            inventory_type=inventory_type,
            workspace_id=workspace_id,
        )

    def reconcile_inventory(
        self,
        session: Session,
        factory_id: int,
        item_id: int,
        inventory_type: InventoryTypeEnum,
        workspace_id: int,
        user_id: int
    ) -> Dict[str, Any]:
        """
        Reconcile inventory ledger vs the matching inventory snapshot
        for one (factory, item, inventory_type) bucket.

        Args:
            session: Database session
            factory_id: Factory ID
            item_id: Item ID
            inventory_type: Inventory type bucket to reconcile
            workspace_id: Workspace ID
            user_id: User performing reconciliation

        Returns:
            Dictionary with reconciliation results

        Note:
            This method does NOT commit. Service layer must commit.
        """
        ledger_qty, _ledger_value = self.inventory_ledger_dao.calculate_balance(
            session,
            factory_id=factory_id,
            item_id=item_id,
            inventory_type=inventory_type,
            workspace_id=workspace_id,
        )

        snapshot = self.inventory_dao.get_by_factory_item_type(
            session,
            factory_id=factory_id,
            item_id=item_id,
            inventory_type=inventory_type,
            workspace_id=workspace_id,
        )

        if not snapshot:
            return {
                'status': 'error',
                'ledger_qty': ledger_qty,
                'snapshot_qty': 0,
                'discrepancy': ledger_qty,
                'adjustment_created': False,
                'error': 'Snapshot missing for item with ledger transactions',
            }

        snapshot_qty = snapshot.qty
        discrepancy = ledger_qty - snapshot_qty

        if discrepancy == 0:
            return {
                'status': 'balanced',
                'ledger_qty': ledger_qty,
                'snapshot_qty': snapshot_qty,
                'discrepancy': 0,
                'adjustment_created': False,
            }

        latest_entry = self.inventory_ledger_dao.get_latest_entry(
            session,
            factory_id=factory_id,
            item_id=item_id,
            inventory_type=inventory_type,
            workspace_id=workspace_id,
        )

        avg_price = latest_entry.avg_price_after if latest_entry else Decimal('0.00')

        # Build dict directly so we can inject workspace_id + performed_by,
        # which are NOT part of InventoryLedgerCreate.
        adjustment_payload: Dict[str, Any] = {
            'workspace_id': workspace_id,
            'inventory_type': inventory_type,
            'factory_id': factory_id,
            'item_id': item_id,
            'transaction_type': 'inventory_adjustment',
            'quantity': abs(discrepancy),
            'unit_cost': avg_price,
            'total_cost': abs(discrepancy) * avg_price,
            'qty_before': snapshot_qty,
            'qty_after': ledger_qty,
            'avg_price_before': avg_price,
            'avg_price_after': avg_price,
            'source_type': 'reconciliation',
            'notes': (
                f"Reconciliation adjustment: Snapshot was {snapshot_qty}, "
                f"ledger shows {ledger_qty}. Discrepancy: {discrepancy}"
            ),
            'performed_by': user_id,
        }

        self.inventory_ledger_dao.create(session, obj_in=adjustment_payload)

        snapshot.qty = ledger_qty
        snapshot.avg_price = avg_price
        session.flush()

        return {
            'status': 'adjusted',
            'ledger_qty': ledger_qty,
            'snapshot_qty': snapshot_qty,
            'discrepancy': discrepancy,
            'adjustment_created': True,
        }

    # ============================================================================
    # CROSS-LEDGER REPORTING
    # ============================================================================

    def get_item_movement_summary(
        self,
        session: Session,
        item_id: int,
        workspace_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, List]:
        """
        Get item movement across all ledgers.

        Business logic:
        - Track item journey: Purchase -> Storage -> Machine -> Production -> Inventory -> Sales
        - Aggregate view of item flow

        Args:
            session: Database session
            item_id: Item ID
            workspace_id: Workspace ID
            start_date: Optional start date
            end_date: Optional end date

        Returns:
            Dictionary with ledger entries from all ledgers
        """
        result = {}

        # Machine movements
        if start_date and end_date:
            result['machine'] = self.machine_ledger_dao.get_by_date_range(
                session,
                workspace_id=workspace_id,
                start_date=start_date,
                end_date=end_date
            )
        else:
            result['machine'] = []

        # Project consumption
        result['project'] = []

        # Inventory (unified: storage, damaged, finished goods)
        if start_date and end_date:
            result['inventory'] = self.inventory_ledger_dao.get_by_date_range(
                session,
                workspace_id=workspace_id,
                start_date=start_date,
                end_date=end_date
            )
        else:
            result['inventory'] = []

        return result

    def get_transactions_by_user(
        self,
        session: Session,
        user_id: int,
        workspace_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 100
    ) -> Dict[str, List]:
        """
        Get all transactions performed by a user across all ledgers.

        Useful for:
        - User activity audit
        - Performance tracking
        - Error investigation

        Args:
            session: Database session
            user_id: User ID
            workspace_id: Workspace ID
            start_date: Optional start date
            end_date: Optional end date
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            Dictionary with transactions from all ledgers
        """
        result = {}

        # Machine transactions
        result['machine'] = self.machine_ledger_dao.get_by_performer(
            session,
            performed_by=user_id,
            workspace_id=workspace_id,
            skip=skip,
            limit=limit
        )

        # Project transactions
        result['project'] = self.project_ledger_dao.get_by_performer(
            session,
            performed_by=user_id,
            workspace_id=workspace_id,
            skip=skip,
            limit=limit
        )

        # Inventory transactions
        result['inventory'] = self.inventory_ledger_dao.get_by_performer(
            session,
            performed_by=user_id,
            workspace_id=workspace_id,
            skip=skip,
            limit=limit
        )

        return result

    def get_transactions_by_order(
        self,
        session: Session,
        order_id: int,
        workspace_id: int
    ) -> Dict[str, List]:
        """
        Get all ledger entries related to an order across all ledgers.

        Business logic:
        - Track complete order flow
        - See all inventory impacts of an order

        Args:
            session: Database session
            order_id: Order ID
            workspace_id: Workspace ID

        Returns:
            Dictionary with ledger entries from all ledgers
        """
        result = {}

        # Machine transactions
        result['machine'] = self.machine_ledger_dao.get_by_order(
            session,
            order_id=order_id,
            workspace_id=workspace_id
        )

        # Inventory transactions (unified)
        result['inventory'] = self.inventory_ledger_dao.get_by_order(
            session,
            order_id=order_id,
            workspace_id=workspace_id
        )

        return result


# Singleton instance
ledger_manager = LedgerManager()
