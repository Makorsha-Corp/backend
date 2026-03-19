"""Ledger Manager for ledger queries and reconciliation"""
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from datetime import datetime, date
from decimal import Decimal
from app.managers.base_manager import BaseManager
from app.models.storage_item_ledger import StorageItemLedger
from app.models.machine_item_ledger import MachineItemLedger
from app.models.damaged_item_ledger import DamagedItemLedger
from app.models.project_component_item_ledger import ProjectComponentItemLedger
from app.models.inventory_ledger import InventoryLedger
from app.dao.storage_item_ledger import storage_item_ledger_dao
from app.dao.machine_item_ledger import machine_item_ledger_dao
from app.dao.damaged_item_ledger import damaged_item_ledger_dao
from app.dao.project_component_item_ledger import project_component_item_ledger_dao
from app.dao.inventory_ledger import inventory_ledger_dao
from app.dao.storage_item import storage_item_dao
from app.dao.machine_item import machine_item_dao
from app.dao.damaged_item import damaged_item_dao
from app.dao.inventory import inventory_dao
from app.schemas.storage_item_ledger import StorageItemLedgerCreate
from app.schemas.machine_item_ledger import MachineItemLedgerCreate
from app.schemas.damaged_item_ledger import DamagedItemLedgerCreate
from app.schemas.inventory_ledger import InventoryLedgerCreate


class LedgerManager(BaseManager[StorageItemLedger]):
    """
    UNIFIED LEDGER MANAGER: Queries and reconciliation for all ledgers.

    Handles all 5 ledger types:
    - Storage Item Ledger
    - Machine Item Ledger
    - Damaged Item Ledger
    - Project Component Item Ledger
    - Inventory Ledger (Finished Goods)

    Responsibilities:
    1. Read operations (query ledgers)
    2. Balance calculation from ledgers
    3. Reconciliation (compare ledger vs snapshots)
    4. Create adjustment transactions when discrepancies found
    5. Cross-ledger reporting

    Note: Ledger WRITES happen as side effects in other managers
          (SalesManager, InventoryManager, OrderManager, etc.)

    Does NOT commit transactions - that's the service layer's responsibility.
    """

    def __init__(self):
        super().__init__(StorageItemLedger)
        # Initialize all 5 ledger DAOs
        self.storage_ledger_dao = storage_item_ledger_dao
        self.machine_ledger_dao = machine_item_ledger_dao
        self.damaged_ledger_dao = damaged_item_ledger_dao
        self.project_ledger_dao = project_component_item_ledger_dao
        self.inventory_ledger_dao = inventory_ledger_dao

        # Initialize snapshot DAOs (for reconciliation)
        self.storage_item_dao = storage_item_dao
        self.machine_item_dao = machine_item_dao
        self.damaged_item_dao = damaged_item_dao
        self.inventory_dao = inventory_dao

    # ============================================================================
    # STORAGE LEDGER OPERATIONS
    # ============================================================================

    def get_storage_ledger(
        self,
        session: Session,
        factory_id: int,
        item_id: int,
        workspace_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        transaction_type: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[StorageItemLedger]:
        """
        Get storage ledger entries with optional filters.

        Args:
            session: Database session
            factory_id: Factory ID
            item_id: Item ID
            workspace_id: Workspace ID
            start_date: Optional start date filter
            end_date: Optional end date filter
            transaction_type: Optional transaction type filter
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            List of storage ledger entries (newest first)
        """
        if start_date and end_date:
            return self.storage_ledger_dao.get_by_date_range(
                session,
                workspace_id=workspace_id,
                start_date=start_date,
                end_date=end_date,
                skip=skip,
                limit=limit
            )
        elif transaction_type:
            return self.storage_ledger_dao.get_by_transaction_type(
                session,
                transaction_type=transaction_type,
                workspace_id=workspace_id,
                skip=skip,
                limit=limit
            )
        else:
            return self.storage_ledger_dao.get_by_factory_and_item(
                session,
                factory_id=factory_id,
                item_id=item_id,
                workspace_id=workspace_id,
                skip=skip,
                limit=limit
            )

    def get_storage_balance(
        self,
        session: Session,
        factory_id: int,
        item_id: int,
        workspace_id: int
    ) -> Tuple[int, Decimal]:
        """
        Calculate current storage balance from ledger.

        Args:
            session: Database session
            factory_id: Factory ID
            item_id: Item ID
            workspace_id: Workspace ID

        Returns:
            Tuple of (quantity, total_value)
        """
        return self.storage_ledger_dao.calculate_balance(
            session,
            factory_id=factory_id,
            item_id=item_id,
            workspace_id=workspace_id
        )

    def reconcile_storage_item(
        self,
        session: Session,
        factory_id: int,
        item_id: int,
        workspace_id: int,
        user_id: int
    ) -> Dict[str, Any]:
        """
        Reconcile storage ledger vs storage_items snapshot.

        Business logic:
        - Ledger is source of truth
        - If snapshot doesn't match ledger, create adjustment transaction
        - Update snapshot to match ledger

        Args:
            session: Database session
            factory_id: Factory ID
            item_id: Item ID
            workspace_id: Workspace ID
            user_id: User performing reconciliation

        Returns:
            Dictionary with reconciliation results:
            {
                'status': 'balanced' | 'adjusted' | 'created',
                'ledger_qty': int,
                'snapshot_qty': int,
                'discrepancy': int,
                'adjustment_created': bool
            }

        Note:
            This method does NOT commit. Service layer must commit.
        """
        # Get balance from ledger (source of truth)
        ledger_qty, ledger_value = self.storage_ledger_dao.calculate_balance(
            session,
            factory_id=factory_id,
            item_id=item_id,
            workspace_id=workspace_id
        )

        # Get snapshot
        snapshot = self.storage_item_dao.get_by_factory_and_item(
            session,
            factory_id=factory_id,
            item_id=item_id,
            workspace_id=workspace_id
        )

        if not snapshot:
            # Ledger has transactions but snapshot missing
            # This shouldn't happen but if it does, we can't reconcile
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
            # Perfect match!
            return {
                'status': 'balanced',
                'ledger_qty': ledger_qty,
                'snapshot_qty': snapshot_qty,
                'discrepancy': 0,
                'adjustment_created': False
            }

        # DISCREPANCY FOUND - Create adjustment transaction
        latest_entry = self.storage_ledger_dao.get_latest_entry(
            session,
            factory_id=factory_id,
            item_id=item_id,
            workspace_id=workspace_id
        )

        avg_price = latest_entry.avg_price_after if latest_entry else Decimal('0.00')

        adjustment = StorageItemLedgerCreate(
            workspace_id=workspace_id,
            factory_id=factory_id,
            item_id=item_id,
            transaction_type='inventory_adjustment',
            quantity=abs(discrepancy),
            unit_cost=avg_price,
            total_cost=abs(discrepancy) * avg_price,
            qty_before=snapshot_qty,
            qty_after=ledger_qty,
            value_before=snapshot_qty * avg_price,
            value_after=ledger_qty * avg_price,
            avg_price_before=avg_price,
            avg_price_after=avg_price,
            source_type='reconciliation',
            notes=f"Reconciliation adjustment: Snapshot was {snapshot_qty}, ledger shows {ledger_qty}. Discrepancy: {discrepancy}",
            performed_by=user_id
        )

        self.storage_ledger_dao.create(session, obj_in=adjustment)

        # Update snapshot to match ledger
        snapshot.qty = ledger_qty
        snapshot.avg_price = avg_price
        session.flush()

        return {
            'status': 'adjusted',
            'ledger_qty': ledger_qty,
            'snapshot_qty': snapshot_qty,
            'discrepancy': discrepancy,
            'adjustment_created': True
        }

    # ============================================================================
    # MACHINE LEDGER OPERATIONS
    # ============================================================================

    def get_machine_ledger(
        self,
        session: Session,
        machine_id: int,
        item_id: int,
        workspace_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        transaction_type: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[MachineItemLedger]:
        """
        Get machine ledger entries with optional filters.

        Args:
            session: Database session
            machine_id: Machine ID
            item_id: Item ID
            workspace_id: Workspace ID
            start_date: Optional start date filter
            end_date: Optional end date filter
            transaction_type: Optional transaction type filter
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            List of machine ledger entries (newest first)
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
        else:
            return self.machine_ledger_dao.get_by_machine_and_item(
                session,
                machine_id=machine_id,
                item_id=item_id,
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

        adjustment = MachineItemLedgerCreate(
            workspace_id=workspace_id,
            machine_id=machine_id,
            item_id=item_id,
            transaction_type='inventory_adjustment',
            quantity=abs(discrepancy),
            unit_cost=avg_price,
            total_cost=abs(discrepancy) * avg_price,
            qty_before=snapshot_qty,
            qty_after=ledger_qty,
            value_before=snapshot_qty * avg_price,
            value_after=ledger_qty * avg_price,
            avg_price_before=avg_price,
            avg_price_after=avg_price,
            source_type='reconciliation',
            notes=f"Reconciliation adjustment: Snapshot was {snapshot_qty}, ledger shows {ledger_qty}. Discrepancy: {discrepancy}",
            performed_by=user_id
        )

        self.machine_ledger_dao.create(session, obj_in=adjustment)

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
    # DAMAGED LEDGER OPERATIONS
    # ============================================================================

    def get_damaged_ledger(
        self,
        session: Session,
        factory_id: int,
        item_id: int,
        workspace_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[DamagedItemLedger]:
        """
        Get damaged items ledger entries with optional filters.

        Args:
            session: Database session
            factory_id: Factory ID
            item_id: Item ID
            workspace_id: Workspace ID
            start_date: Optional start date filter
            end_date: Optional end date filter
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            List of damaged ledger entries (newest first)
        """
        if start_date and end_date:
            return self.damaged_ledger_dao.get_by_date_range(
                session,
                workspace_id=workspace_id,
                start_date=start_date,
                end_date=end_date,
                skip=skip,
                limit=limit
            )
        else:
            return self.damaged_ledger_dao.get_by_factory_and_item(
                session,
                factory_id=factory_id,
                item_id=item_id,
                workspace_id=workspace_id,
                skip=skip,
                limit=limit
            )

    def get_damaged_balance(
        self,
        session: Session,
        factory_id: int,
        item_id: int,
        workspace_id: int
    ) -> Tuple[int, Decimal]:
        """
        Calculate current damaged items balance from ledger.

        Args:
            session: Database session
            factory_id: Factory ID
            item_id: Item ID
            workspace_id: Workspace ID

        Returns:
            Tuple of (quantity, total_value)
        """
        return self.damaged_ledger_dao.calculate_balance(
            session,
            factory_id=factory_id,
            item_id=item_id,
            workspace_id=workspace_id
        )

    def reconcile_damaged_item(
        self,
        session: Session,
        factory_id: int,
        item_id: int,
        workspace_id: int,
        user_id: int
    ) -> Dict[str, Any]:
        """
        Reconcile damaged ledger vs damaged_items snapshot.

        Args:
            session: Database session
            factory_id: Factory ID
            item_id: Item ID
            workspace_id: Workspace ID
            user_id: User performing reconciliation

        Returns:
            Dictionary with reconciliation results

        Note:
            This method does NOT commit. Service layer must commit.
        """
        # Get balance from ledger
        ledger_qty, ledger_value = self.damaged_ledger_dao.calculate_balance(
            session,
            factory_id=factory_id,
            item_id=item_id,
            workspace_id=workspace_id
        )

        # Get snapshot
        snapshot = self.damaged_item_dao.get_by_factory_and_item(
            session,
            factory_id=factory_id,
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
        latest_entry = self.damaged_ledger_dao.get_latest_entry(
            session,
            factory_id=factory_id,
            item_id=item_id,
            workspace_id=workspace_id
        )

        avg_price = latest_entry.avg_price_after if latest_entry else Decimal('0.00')

        adjustment = DamagedItemLedgerCreate(
            workspace_id=workspace_id,
            factory_id=factory_id,
            item_id=item_id,
            transaction_type='inventory_adjustment',
            quantity=abs(discrepancy),
            unit_cost=avg_price,
            total_cost=abs(discrepancy) * avg_price,
            qty_before=snapshot_qty,
            qty_after=ledger_qty,
            value_before=snapshot_qty * avg_price,
            value_after=ledger_qty * avg_price,
            avg_price_before=avg_price,
            avg_price_after=avg_price,
            source_type='reconciliation',
            notes=f"Reconciliation adjustment: Snapshot was {snapshot_qty}, ledger shows {ledger_qty}. Discrepancy: {discrepancy}",
            performed_by=user_id
        )

        self.damaged_ledger_dao.create(session, obj_in=adjustment)

        # Update snapshot
        snapshot.qty = ledger_qty
        snapshot.avg_price = avg_price
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
        factory_id: int,
        item_id: int,
        workspace_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        transaction_type: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[InventoryLedger]:
        """
        Get finished goods inventory ledger entries with optional filters.

        Args:
            session: Database session
            factory_id: Factory ID
            item_id: Item ID
            workspace_id: Workspace ID
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
                skip=skip,
                limit=limit
            )
        elif transaction_type:
            return self.inventory_ledger_dao.get_by_transaction_type(
                session,
                transaction_type=transaction_type,
                workspace_id=workspace_id,
                skip=skip,
                limit=limit
            )
        else:
            return self.inventory_ledger_dao.get_by_factory_and_item(
                session,
                factory_id=factory_id,
                item_id=item_id,
                workspace_id=workspace_id,
                skip=skip,
                limit=limit
            )

    def get_inventory_balance(
        self,
        session: Session,
        factory_id: int,
        item_id: int,
        workspace_id: int
    ) -> Tuple[int, Decimal]:
        """
        Calculate current finished goods balance from ledger.

        Args:
            session: Database session
            factory_id: Factory ID
            item_id: Item ID
            workspace_id: Workspace ID

        Returns:
            Tuple of (quantity, total_value)
        """
        return self.inventory_ledger_dao.calculate_balance(
            session,
            factory_id=factory_id,
            item_id=item_id,
            workspace_id=workspace_id
        )

    def reconcile_inventory(
        self,
        session: Session,
        factory_id: int,
        item_id: int,
        workspace_id: int,
        user_id: int
    ) -> Dict[str, Any]:
        """
        Reconcile inventory ledger vs inventory snapshot.

        Args:
            session: Database session
            factory_id: Factory ID
            item_id: Item ID
            workspace_id: Workspace ID
            user_id: User performing reconciliation

        Returns:
            Dictionary with reconciliation results

        Note:
            This method does NOT commit. Service layer must commit.
        """
        # Get balance from ledger
        ledger_qty, ledger_value = self.inventory_ledger_dao.calculate_balance(
            session,
            factory_id=factory_id,
            item_id=item_id,
            workspace_id=workspace_id
        )

        # Get snapshot
        snapshot = self.inventory_dao.get_by_factory_and_item(
            session,
            factory_id=factory_id,
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
        latest_entry = self.inventory_ledger_dao.get_latest_entry(
            session,
            factory_id=factory_id,
            item_id=item_id,
            workspace_id=workspace_id
        )

        avg_price = latest_entry.avg_price_after if latest_entry else Decimal('0.00')

        adjustment = InventoryLedgerCreate(
            workspace_id=workspace_id,
            factory_id=factory_id,
            item_id=item_id,
            transaction_type='inventory_adjustment',
            quantity=abs(discrepancy),
            unit_cost=avg_price,
            total_cost=abs(discrepancy) * avg_price,
            qty_before=snapshot_qty,
            qty_after=ledger_qty,
            value_before=snapshot_qty * avg_price,
            value_after=ledger_qty * avg_price,
            avg_price_before=avg_price,
            avg_price_after=avg_price,
            source_type='reconciliation',
            notes=f"Reconciliation adjustment: Snapshot was {snapshot_qty}, ledger shows {ledger_qty}. Discrepancy: {discrepancy}",
            performed_by=user_id
        )

        self.inventory_ledger_dao.create(session, obj_in=adjustment)

        # Update snapshot
        snapshot.qty = ledger_qty
        snapshot.avg_price = avg_price
        session.flush()

        return {
            'status': 'adjusted',
            'ledger_qty': ledger_qty,
            'snapshot_qty': snapshot_qty,
            'discrepancy': discrepancy,
            'adjustment_created': True
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

        # Storage movements
        if start_date and end_date:
            result['storage'] = self.storage_ledger_dao.get_by_date_range(
                session,
                workspace_id=workspace_id,
                start_date=start_date,
                end_date=end_date
            )
        else:
            result['storage'] = []

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

        # Damaged movements
        if start_date and end_date:
            result['damaged'] = self.damaged_ledger_dao.get_by_date_range(
                session,
                workspace_id=workspace_id,
                start_date=start_date,
                end_date=end_date
            )
        else:
            result['damaged'] = []

        # Project consumption
        result['project'] = []

        # Finished goods (inventory)
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

        # Storage transactions
        result['storage'] = self.storage_ledger_dao.get_by_performer(
            session,
            performed_by=user_id,
            workspace_id=workspace_id,
            skip=skip,
            limit=limit
        )

        # Machine transactions
        result['machine'] = self.machine_ledger_dao.get_by_performer(
            session,
            performed_by=user_id,
            workspace_id=workspace_id,
            skip=skip,
            limit=limit
        )

        # Damaged transactions
        result['damaged'] = self.damaged_ledger_dao.get_by_performer(
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

        # Storage transactions
        result['storage'] = self.storage_ledger_dao.get_by_order(
            session,
            order_id=order_id,
            workspace_id=workspace_id
        )

        # Machine transactions
        result['machine'] = self.machine_ledger_dao.get_by_order(
            session,
            order_id=order_id,
            workspace_id=workspace_id
        )

        # Damaged transactions
        result['damaged'] = self.damaged_ledger_dao.get_by_order(
            session,
            order_id=order_id,
            workspace_id=workspace_id
        )

        # Inventory transactions
        result['inventory'] = self.inventory_ledger_dao.get_by_order(
            session,
            order_id=order_id,
            workspace_id=workspace_id
        )

        return result


# Singleton instance
ledger_manager = LedgerManager()
