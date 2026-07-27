"""Transfer Order Service - transaction orchestration"""
from datetime import date
from typing import List, Optional
from sqlalchemy.orm import Session

from app.services.base_service import BaseService
from app.managers.transfer_order_manager import transfer_order_manager
from app.models.transfer_order import TransferOrder
from app.models.transfer_order_item import TransferOrderItem
from app.schemas.transfer_order import (
    TransferOrderCreate, TransferOrderUpdate,
    TransferOrderItemCreate, TransferOrderItemUpdate,
)
from app.services.approval_notification_service import (
    handle_add_approver,
    handle_order_update_notifications,
)


class TransferOrderService(BaseService):
    """Service for transfer order workflows. Handles commit/rollback."""

    def __init__(self):
        super().__init__()
        self.manager = transfer_order_manager

    def create_transfer_order(
        self, db: Session, to_in: TransferOrderCreate,
        workspace_id: int, user_id: int
    ) -> TransferOrder:
        try:
            record = self.manager.create_transfer_order(db, data=to_in, workspace_id=workspace_id, user_id=user_id)
            self._commit_transaction(db)
            db.refresh(record)
            return record
        except Exception:
            self._rollback_transaction(db)
            raise

    def update_transfer_order(
        self, db: Session, to_id: int, to_in: TransferOrderUpdate,
        workspace_id: int, user_id: int
    ) -> TransferOrder:
        try:
            to_before = self.manager.get_transfer_order(db, to_id, workspace_id)
            was_ready = self.manager._ready_for_approval(db, to_before, workspace_id)

            record = self.manager.update_transfer_order(
                db, to_id=to_id, data=to_in, workspace_id=workspace_id, user_id=user_id
            )
            handle_order_update_notifications(
                db,
                workspace_id=workspace_id,
                entity_type='transfer_order',
                entity_id=to_id,
                actor_user_id=user_id,
                order=record,
                was_ready=was_ready,
            )
            self._commit_transaction(db)
            db.refresh(record)
            return record
        except Exception:
            self._rollback_transaction(db)
            raise

    def get_transfer_order(self, db: Session, to_id: int, workspace_id: int) -> TransferOrder:
        return self.manager.get_transfer_order(db, to_id, workspace_id)

    def list_transfer_orders(
        self, db: Session, workspace_id: int,
        skip: int = 0, limit: int = 100,
        **hub_filters,
    ):
        return self.list_transfer_orders_page(
            db, workspace_id, skip=skip, limit=limit, **hub_filters
        )

    def _hub_filter_kwargs(
        self,
        *,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        status_ids: Optional[List[int]] = None,
        factory_id: Optional[int] = None,
        source_location_type: Optional[str] = None,
        destination_location_type: Optional[str] = None,
        search: Optional[str] = None,
        exclude_complete: bool = False,
    ) -> dict:
        return {
            "date_from": date_from,
            "date_to": date_to,
            "status_ids": status_ids,
            "factory_id": factory_id,
            "source_location_type": source_location_type
            if source_location_type and source_location_type != "all"
            else None,
            "destination_location_type": destination_location_type
            if destination_location_type and destination_location_type != "all"
            else None,
            "search": search,
            "exclude_complete": exclude_complete,
        }

    def list_transfer_orders_page(
        self,
        db: Session,
        workspace_id: int,
        *,
        skip: int = 0,
        limit: int = 50,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        status_ids: Optional[List[int]] = None,
        factory_id: Optional[int] = None,
        source_location_type: Optional[str] = None,
        destination_location_type: Optional[str] = None,
        search: Optional[str] = None,
        exclude_complete: bool = False,
    ):
        from app.schemas.transfer_order import TransferOrderListResponse

        filters = self._hub_filter_kwargs(
            date_from=date_from,
            date_to=date_to,
            status_ids=status_ids,
            factory_id=factory_id,
            source_location_type=source_location_type,
            destination_location_type=destination_location_type,
            search=search,
            exclude_complete=exclude_complete,
        )
        total = self.manager.count_transfer_orders_for_hub(db, workspace_id, **filters)
        orders = self.manager.list_transfer_orders_for_hub(
            db, workspace_id, skip=skip, limit=limit, **filters
        )
        return TransferOrderListResponse(
            items=orders,
            total=total,
            skip=skip,
            limit=limit,
            has_more=skip + len(orders) < total,
        )

    def get_transfer_order_hub_stats(
        self,
        db: Session,
        workspace_id: int,
        *,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        status_ids: Optional[List[int]] = None,
        factory_id: Optional[int] = None,
        source_location_type: Optional[str] = None,
        destination_location_type: Optional[str] = None,
        search: Optional[str] = None,
        exclude_complete: bool = False,
    ):
        from app.schemas.transfer_order import TransferOrderHubStatsResponse

        filters = self._hub_filter_kwargs(
            date_from=date_from,
            date_to=date_to,
            status_ids=status_ids,
            factory_id=factory_id,
            source_location_type=source_location_type,
            destination_location_type=destination_location_type,
            search=search,
            exclude_complete=exclude_complete,
        )
        total_count, open_count, completed_count = self.manager.transfer_order_hub_stats(
            db, workspace_id, **filters
        )
        recent = self.manager.list_transfer_orders_recent_for_hub(
            db, workspace_id, limit=10, **filters
        )
        machine_involved_count = (
            self.manager.count_transfer_orders_machine_involved_for_hub(
                db, workspace_id, **filters
            )
        )
        from app.services.order_hub_stats_helpers import (
            pending_highlight_from_dict,
            transfer_order_to_recent_summary,
        )

        pending = self.manager.transfer_order_pending_highlights_for_hub(
            db, workspace_id, **filters
        )

        return TransferOrderHubStatsResponse(
            total_count=total_count,
            open_count=open_count,
            completed_count=completed_count,
            machine_involved_count=machine_involved_count,
            recent_orders=[transfer_order_to_recent_summary(o) for o in recent],
            pending_planned_count=pending["pending_planned_count"],
            pending_planned=[
                pending_highlight_from_dict(x) for x in pending["pending_planned"]
            ],
            awaiting_setup_count=pending["awaiting_setup_count"],
            awaiting_setup=[
                pending_highlight_from_dict(x) for x in pending["awaiting_setup"]
            ],
            oldest_drafts=[
                pending_highlight_from_dict(x) for x in pending["oldest_drafts"]
            ],
        )

    def delete_transfer_order(self, db: Session, to_id: int, workspace_id: int) -> None:
        try:
            self.manager.delete_transfer_order(db, to_id=to_id, workspace_id=workspace_id)
            self._commit_transaction(db)
        except Exception:
            self._rollback_transaction(db)
            raise

    def mark_order_complete(
        self, db: Session, to_id: int, workspace_id: int, user_id: int
    ) -> TransferOrder:
        try:
            record = self.manager.mark_order_complete(
                db, to_id=to_id, workspace_id=workspace_id, user_id=user_id
            )
            self._commit_transaction(db)
            db.refresh(record)
            return record
        except Exception:
            self._rollback_transaction(db)
            raise

    # ─── Items ─────────────────────────────────────────────────
    def add_item(
        self, db: Session, to_id: int, item_in: TransferOrderItemCreate,
        workspace_id: int, user_id: int,
    ) -> TransferOrderItem:
        try:
            to_before = self.manager.get_transfer_order(db, to_id, workspace_id)
            was_ready = self.manager._ready_for_approval(db, to_before, workspace_id)

            record = self.manager.add_item(
                db, to_id=to_id, data=item_in, workspace_id=workspace_id, user_id=user_id
            )
            to_after = self.manager.get_transfer_order(db, to_id, workspace_id)
            handle_order_update_notifications(
                db,
                workspace_id=workspace_id,
                entity_type='transfer_order',
                entity_id=to_id,
                actor_user_id=user_id,
                order=to_after,
                was_ready=was_ready,
            )
            self._commit_transaction(db)
            db.refresh(record)
            return record
        except Exception:
            self._rollback_transaction(db)
            raise

    def update_item(
        self, db: Session, item_id: int, item_in: TransferOrderItemUpdate,
        workspace_id: int, user_id: int
    ) -> TransferOrderItem:
        try:
            record = self.manager.update_item(db, item_id=item_id, data=item_in, workspace_id=workspace_id, user_id=user_id)
            self._commit_transaction(db)
            db.refresh(record)
            return record
        except Exception:
            self._rollback_transaction(db)
            raise

    def remove_item(self, db: Session, item_id: int, workspace_id: int, user_id: int) -> TransferOrderItem:
        try:
            record = self.manager.remove_item(db, item_id=item_id, workspace_id=workspace_id, user_id=user_id)
            self._commit_transaction(db)
            return record
        except Exception:
            self._rollback_transaction(db)
            raise

    def get_items(self, db: Session, to_id: int, workspace_id: int) -> List[TransferOrderItem]:
        return self.manager.get_items(db, to_id, workspace_id)

    # ─── Events ────────────────────────────────────────────────
    def list_events(self, db: Session, to_id: int, workspace_id: int):
        return self.manager.list_events(db, to_id=to_id, workspace_id=workspace_id)

    # ─── Approvers ─────────────────────────────────────────────
    def list_approvers(self, db: Session, to_id: int, workspace_id: int):
        return self.manager.list_approvers(db, to_id=to_id, workspace_id=workspace_id)

    def approval_summary_for(self, db: Session, to_id: int, workspace_id: int):
        to = self.manager.get_transfer_order(db, to_id=to_id, workspace_id=workspace_id)
        return self.manager.approval_summary(db, to)

    def add_approver(self, db: Session, to_id: int, user_id: int, workspace_id: int, assigned_by: int):
        try:
            record = self.manager.add_approver(
                db, to_id=to_id, user_id=user_id, workspace_id=workspace_id, assigned_by=assigned_by
            )
            to = self.manager.get_transfer_order(db, to_id, workspace_id)
            handle_add_approver(
                db,
                workspace_id=workspace_id,
                entity_type='transfer_order',
                entity_id=to_id,
                actor_user_id=assigned_by,
                approver_user_id=user_id,
                approver_record_id=record.id,
                order=to,
            )
            self._commit_transaction(db)
            db.refresh(record)
            return record
        except Exception:
            self._rollback_transaction(db)
            raise

    def remove_approver(
        self, db: Session, to_id: int, user_id: int, workspace_id: int, performed_by: Optional[int] = None
    ) -> None:
        try:
            self.manager.remove_approver(
                db, to_id=to_id, user_id=user_id, workspace_id=workspace_id, performed_by=performed_by
            )
            self._commit_transaction(db)
        except Exception:
            self._rollback_transaction(db)
            raise

    def set_approval(self, db: Session, to_id: int, user_id: int, workspace_id: int, approved: bool):
        try:
            record = self.manager.set_approval(
                db, to_id=to_id, user_id=user_id, workspace_id=workspace_id, approved=approved
            )
            self._commit_transaction(db)
            db.refresh(record)
            return record
        except Exception:
            self._rollback_transaction(db)
            raise


transfer_order_service = TransferOrderService()
