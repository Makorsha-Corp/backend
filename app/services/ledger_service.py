"""Ledger Service for orchestrating ledger workflows"""
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from datetime import datetime
from decimal import Decimal
from app.services.base_service import BaseService
from app.managers.ledger_manager import ledger_manager
from app.models.storage_item_ledger import StorageItemLedger
from app.models.machine_item_ledger import MachineItemLedger
from app.models.damaged_item_ledger import DamagedItemLedger
from app.models.project_component_item_ledger import ProjectComponentItemLedger
from app.models.inventory_ledger import InventoryLedger
from app.models.profile import Profile
from app.schemas.response import ActionMessage, success_message, info_message, warning_message
from app.core.exceptions import NotFoundError


class LedgerService(BaseService):
    """
    Service for Ledger workflows.

    Handles:
    - Transaction boundaries (commit/rollback)
    - Ledger query operations
    - Reconciliation with user messages
    - Cross-ledger reporting
    """

    def __init__(self):
        super().__init__()
        self.ledger_manager = ledger_manager

    # ============================================================================
    # STORAGE LEDGER OPERATIONS
    # ============================================================================

    def get_storage_ledger(
        self,
        db: Session,
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
            db: Database session
            factory_id: Factory ID
            item_id: Item ID
            workspace_id: Workspace ID
            start_date: Optional start date filter
            end_date: Optional end date filter
            transaction_type: Optional transaction type filter
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            List of storage ledger entries
        """
        return self.ledger_manager.get_storage_ledger(
            session=db,
            factory_id=factory_id,
            item_id=item_id,
            workspace_id=workspace_id,
            start_date=start_date,
            end_date=end_date,
            transaction_type=transaction_type,
            skip=skip,
            limit=limit
        )

    def get_storage_balance(
        self,
        db: Session,
        factory_id: int,
        item_id: int,
        workspace_id: int
    ) -> Dict[str, Any]:
        """
        Get current storage balance from ledger.

        Args:
            db: Database session
            factory_id: Factory ID
            item_id: Item ID
            workspace_id: Workspace ID

        Returns:
            Dictionary with quantity and value
        """
        qty, value = self.ledger_manager.get_storage_balance(
            session=db,
            factory_id=factory_id,
            item_id=item_id,
            workspace_id=workspace_id
        )
        return {
            'factory_id': factory_id,
            'item_id': item_id,
            'quantity': qty,
            'total_value': float(value)
        }

    def reconcile_storage_item(
        self,
        db: Session,
        factory_id: int,
        item_id: int,
        workspace_id: int,
        current_user: Profile
    ) -> Tuple[Dict[str, Any], List[ActionMessage]]:
        """
        Reconcile storage ledger vs snapshot and return messages.

        Args:
            db: Database session
            factory_id: Factory ID
            item_id: Item ID
            workspace_id: Workspace ID
            current_user: Current authenticated user

        Returns:
            Tuple of (reconciliation_result, messages)
        """
        messages = []

        try:
            # Perform reconciliation
            result = self.ledger_manager.reconcile_storage_item(
                session=db,
                factory_id=factory_id,
                item_id=item_id,
                workspace_id=workspace_id,
                user_id=current_user.id
            )

            # Generate user-friendly messages
            if result['status'] == 'balanced':
                messages.append(success_message(
                    f"Storage inventory is balanced. Ledger and snapshot match at {result['ledger_qty']} units."
                ))
            elif result['status'] == 'adjusted':
                messages.append(warning_message(
                    f"Discrepancy found: Snapshot was {result['snapshot_qty']}, ledger shows {result['ledger_qty']}. "
                    f"Adjustment of {abs(result['discrepancy'])} units created.",
                    details=result
                ))
                messages.append(success_message(
                    "Snapshot updated to match ledger (source of truth)."
                ))
            elif result['status'] == 'error':
                messages.append(warning_message(
                    f"Reconciliation issue: {result.get('error', 'Unknown error')}",
                    details=result
                ))

            # Commit transaction
            self._commit_transaction(db)

            return result, messages

        except Exception as e:
            self._rollback_transaction(db)
            raise

    # ============================================================================
    # MACHINE LEDGER OPERATIONS
    # ============================================================================

    def get_machine_ledger(
        self,
        db: Session,
        machine_id: int,
        item_id: int,
        workspace_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        transaction_type: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[MachineItemLedger]:
        """Get machine ledger entries with optional filters."""
        return self.ledger_manager.get_machine_ledger(
            session=db,
            machine_id=machine_id,
            item_id=item_id,
            workspace_id=workspace_id,
            start_date=start_date,
            end_date=end_date,
            transaction_type=transaction_type,
            skip=skip,
            limit=limit
        )

    def get_machine_balance(
        self,
        db: Session,
        machine_id: int,
        item_id: int,
        workspace_id: int
    ) -> Dict[str, Any]:
        """Get current machine balance from ledger."""
        qty, value = self.ledger_manager.get_machine_balance(
            session=db,
            machine_id=machine_id,
            item_id=item_id,
            workspace_id=workspace_id
        )
        return {
            'machine_id': machine_id,
            'item_id': item_id,
            'quantity': qty,
            'total_value': float(value)
        }

    def reconcile_machine_item(
        self,
        db: Session,
        machine_id: int,
        item_id: int,
        workspace_id: int,
        current_user: Profile
    ) -> Tuple[Dict[str, Any], List[ActionMessage]]:
        """Reconcile machine ledger vs snapshot and return messages."""
        messages = []

        try:
            result = self.ledger_manager.reconcile_machine_item(
                session=db,
                machine_id=machine_id,
                item_id=item_id,
                workspace_id=workspace_id,
                user_id=current_user.id
            )

            if result['status'] == 'balanced':
                messages.append(success_message(
                    f"Machine inventory is balanced at {result['ledger_qty']} units."
                ))
            elif result['status'] == 'adjusted':
                messages.append(warning_message(
                    f"Discrepancy found and corrected: {abs(result['discrepancy'])} units adjusted.",
                    details=result
                ))
                messages.append(success_message("Snapshot updated to match ledger."))
            elif result['status'] == 'error':
                messages.append(warning_message(
                    f"Reconciliation issue: {result.get('error', 'Unknown error')}"
                ))

            self._commit_transaction(db)
            return result, messages

        except Exception as e:
            self._rollback_transaction(db)
            raise

    # ============================================================================
    # DAMAGED LEDGER OPERATIONS
    # ============================================================================

    def get_damaged_ledger(
        self,
        db: Session,
        factory_id: int,
        item_id: int,
        workspace_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[DamagedItemLedger]:
        """Get damaged items ledger entries with optional filters."""
        return self.ledger_manager.get_damaged_ledger(
            session=db,
            factory_id=factory_id,
            item_id=item_id,
            workspace_id=workspace_id,
            start_date=start_date,
            end_date=end_date,
            skip=skip,
            limit=limit
        )

    def get_damaged_balance(
        self,
        db: Session,
        factory_id: int,
        item_id: int,
        workspace_id: int
    ) -> Dict[str, Any]:
        """Get current damaged items balance from ledger."""
        qty, value = self.ledger_manager.get_damaged_balance(
            session=db,
            factory_id=factory_id,
            item_id=item_id,
            workspace_id=workspace_id
        )
        return {
            'factory_id': factory_id,
            'item_id': item_id,
            'quantity': qty,
            'total_value': float(value)
        }

    def reconcile_damaged_item(
        self,
        db: Session,
        factory_id: int,
        item_id: int,
        workspace_id: int,
        current_user: Profile
    ) -> Tuple[Dict[str, Any], List[ActionMessage]]:
        """Reconcile damaged ledger vs snapshot and return messages."""
        messages = []

        try:
            result = self.ledger_manager.reconcile_damaged_item(
                session=db,
                factory_id=factory_id,
                item_id=item_id,
                workspace_id=workspace_id,
                user_id=current_user.id
            )

            if result['status'] == 'balanced':
                messages.append(success_message(
                    f"Damaged inventory is balanced at {result['ledger_qty']} units."
                ))
            elif result['status'] == 'adjusted':
                messages.append(warning_message(
                    f"Discrepancy found and corrected: {abs(result['discrepancy'])} units adjusted.",
                    details=result
                ))
                messages.append(success_message("Snapshot updated to match ledger."))
            elif result['status'] == 'error':
                messages.append(warning_message(
                    f"Reconciliation issue: {result.get('error', 'Unknown error')}"
                ))

            self._commit_transaction(db)
            return result, messages

        except Exception as e:
            self._rollback_transaction(db)
            raise

    # ============================================================================
    # PROJECT COMPONENT LEDGER OPERATIONS
    # ============================================================================

    def get_project_component_ledger(
        self,
        db: Session,
        project_component_id: int,
        workspace_id: int,
        item_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[ProjectComponentItemLedger]:
        """Get project component consumption ledger."""
        return self.ledger_manager.get_project_component_ledger(
            session=db,
            project_component_id=project_component_id,
            workspace_id=workspace_id,
            item_id=item_id,
            skip=skip,
            limit=limit
        )

    def get_project_component_total_cost(
        self,
        db: Session,
        project_component_id: int,
        workspace_id: int
    ) -> Dict[str, Any]:
        """Calculate total cost of all items consumed by a project component."""
        total_cost = self.ledger_manager.calculate_project_component_total_cost(
            session=db,
            project_component_id=project_component_id,
            workspace_id=workspace_id
        )
        return {
            'project_component_id': project_component_id,
            'total_cost': float(total_cost)
        }

    # ============================================================================
    # INVENTORY LEDGER (Finished Goods) OPERATIONS
    # ============================================================================

    def get_inventory_ledger(
        self,
        db: Session,
        factory_id: int,
        item_id: int,
        workspace_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        transaction_type: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[InventoryLedger]:
        """Get finished goods inventory ledger entries with optional filters."""
        return self.ledger_manager.get_inventory_ledger(
            session=db,
            factory_id=factory_id,
            item_id=item_id,
            workspace_id=workspace_id,
            start_date=start_date,
            end_date=end_date,
            transaction_type=transaction_type,
            skip=skip,
            limit=limit
        )

    def get_inventory_balance(
        self,
        db: Session,
        factory_id: int,
        item_id: int,
        workspace_id: int
    ) -> Dict[str, Any]:
        """Get current finished goods balance from ledger."""
        qty, value = self.ledger_manager.get_inventory_balance(
            session=db,
            factory_id=factory_id,
            item_id=item_id,
            workspace_id=workspace_id
        )
        return {
            'factory_id': factory_id,
            'item_id': item_id,
            'quantity': qty,
            'total_value': float(value)
        }

    def reconcile_inventory(
        self,
        db: Session,
        factory_id: int,
        item_id: int,
        workspace_id: int,
        current_user: Profile
    ) -> Tuple[Dict[str, Any], List[ActionMessage]]:
        """Reconcile inventory ledger vs snapshot and return messages."""
        messages = []

        try:
            result = self.ledger_manager.reconcile_inventory(
                session=db,
                factory_id=factory_id,
                item_id=item_id,
                workspace_id=workspace_id,
                user_id=current_user.id
            )

            if result['status'] == 'balanced':
                messages.append(success_message(
                    f"Finished goods inventory is balanced at {result['ledger_qty']} units."
                ))
            elif result['status'] == 'adjusted':
                messages.append(warning_message(
                    f"Discrepancy found and corrected: {abs(result['discrepancy'])} units adjusted.",
                    details=result
                ))
                messages.append(success_message("Snapshot updated to match ledger."))
            elif result['status'] == 'error':
                messages.append(warning_message(
                    f"Reconciliation issue: {result.get('error', 'Unknown error')}"
                ))

            self._commit_transaction(db)
            return result, messages

        except Exception as e:
            self._rollback_transaction(db)
            raise

    # ============================================================================
    # CROSS-LEDGER REPORTING
    # ============================================================================

    def get_item_movement_summary(
        self,
        db: Session,
        item_id: int,
        workspace_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, List]:
        """
        Get item movement across all ledgers.

        Tracks item journey: Purchase -> Storage -> Machine -> Production -> Inventory -> Sales
        """
        return self.ledger_manager.get_item_movement_summary(
            session=db,
            item_id=item_id,
            workspace_id=workspace_id,
            start_date=start_date,
            end_date=end_date
        )

    def get_transactions_by_user(
        self,
        db: Session,
        user_id: int,
        workspace_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 100
    ) -> Dict[str, List]:
        """Get all transactions performed by a user across all ledgers."""
        return self.ledger_manager.get_transactions_by_user(
            session=db,
            user_id=user_id,
            workspace_id=workspace_id,
            start_date=start_date,
            end_date=end_date,
            skip=skip,
            limit=limit
        )

    def get_transactions_by_order(
        self,
        db: Session,
        order_id: int,
        workspace_id: int
    ) -> Dict[str, List]:
        """Get all ledger entries related to an order across all ledgers."""
        return self.ledger_manager.get_transactions_by_order(
            session=db,
            order_id=order_id,
            workspace_id=workspace_id
        )


# Singleton instance
ledger_service = LedgerService()
