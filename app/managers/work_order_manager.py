"""Work Order Manager - business logic for work orders"""
from datetime import date
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from fastapi import HTTPException, status

from app.managers.base_manager import BaseManager
from app.models.work_order import WorkOrder
from app.models.work_order_item import WorkOrderItem
from app.models.enums import WorkTypeEnum, WorkOrderPriorityEnum, WorkOrderStatusEnum, MaintenanceTypeEnum
from app.schemas.work_order import WorkOrderCreate, WorkOrderUpdate
from app.schemas.work_order_item import WorkOrderItemCreate, WorkOrderItemUpdate
from app.schemas.machine_maintenance_log import MachineMaintenanceLogCreate
from app.dao.work_order import work_order_dao
from app.dao.work_order_item import work_order_item_dao
from app.dao.factory import factory_dao
from app.managers.machine_maintenance_log_manager import machine_maintenance_log_manager


class WorkOrderManager(BaseManager[WorkOrder]):
    """Manager for work order business logic."""

    def __init__(self):
        super().__init__(WorkOrder)
        self.wo_dao = work_order_dao
        self.item_dao = work_order_item_dao

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

        wo_number = self.wo_dao.get_next_number(session, workspace_id=workspace_id)

        wo_dict = data.model_dump()
        wo_dict['workspace_id'] = workspace_id
        wo_dict['work_order_number'] = wo_number
        wo_dict['created_by'] = user_id

        return self.wo_dao.create(session, obj_in=wo_dict)

    def update_work_order(
        self, session: Session, wo_id: int, data: WorkOrderUpdate,
        workspace_id: int, user_id: int
    ) -> WorkOrder:
        """Update work order. Handles approval stamps."""
        record = self.wo_dao.get_by_id_and_workspace(
            session, id=wo_id, workspace_id=workspace_id
        )
        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Work order with ID {wo_id} not found"
            )
        if record.is_deleted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot update a deleted work order"
            )

        update_dict = data.model_dump(exclude_unset=True)
        update_dict['updated_by'] = user_id

        # Stamp order approval
        if 'order_approved' in update_dict and update_dict['order_approved'] and not record.order_approved:
            update_dict['order_approved_by'] = user_id
            update_dict['order_approved_at'] = func.now()

        # Stamp cost approval
        if 'cost_approved' in update_dict and update_dict['cost_approved'] and not record.cost_approved:
            update_dict['cost_approved_by'] = user_id
            update_dict['cost_approved_at'] = func.now()

        # When status changes to COMPLETED and machine_id is set, create a Machine Maintenance Log
        new_status = update_dict.get('status')
        machine_id = update_dict.get('machine_id') if 'machine_id' in update_dict else record.machine_id
        if new_status == WorkOrderStatusEnum.COMPLETED and machine_id is not None:
            work_type_to_maintenance = {
                WorkTypeEnum.MAINTENANCE: MaintenanceTypeEnum.PREVENTIVE,
                WorkTypeEnum.INSPECTION: MaintenanceTypeEnum.INSPECTION,
                WorkTypeEnum.REPAIR: MaintenanceTypeEnum.REPAIR,
                WorkTypeEnum.INSTALLATION: MaintenanceTypeEnum.REPAIR,
                WorkTypeEnum.CALIBRATION: MaintenanceTypeEnum.INSPECTION,
                WorkTypeEnum.OVERHAUL: MaintenanceTypeEnum.REPAIR,
                WorkTypeEnum.FABRICATION: MaintenanceTypeEnum.REPAIR,
                WorkTypeEnum.OTHER: MaintenanceTypeEnum.REPAIR,
            }
            maint_type = work_type_to_maintenance.get(record.work_type, MaintenanceTypeEnum.REPAIR)
            summary = f"Work order {record.work_order_number} completed: {record.title}"
            if record.completion_notes:
                summary = f"{summary}. {record.completion_notes}"
            log_data = MachineMaintenanceLogCreate(
                machine_id=machine_id,
                maintenance_type=maint_type,
                maintenance_date=date.today(),
                summary=summary[:500] if len(summary) > 500 else summary,
                cost=record.cost,
                performed_by=record.assigned_to,
            )
            machine_maintenance_log_manager.create_log(
                session, log_data=log_data,
                workspace_id=record.workspace_id, user_id=user_id
            )

        return self.wo_dao.update(session, db_obj=record, obj_in=update_dict)

    def get_work_order(self, session: Session, wo_id: int, workspace_id: int) -> WorkOrder:
        record = self.wo_dao.get_by_id_and_workspace(session, id=wo_id, workspace_id=workspace_id)
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Work order with ID {wo_id} not found")
        return record

    def list_work_orders(
        self, session: Session, workspace_id: int,
        work_type: Optional[WorkTypeEnum] = None,
        wo_status: Optional[WorkOrderStatusEnum] = None,
        priority: Optional[WorkOrderPriorityEnum] = None,
        factory_id: Optional[int] = None,
        machine_id: Optional[int] = None,
        skip: int = 0, limit: int = 100
    ) -> List[WorkOrder]:
        return self.wo_dao.get_by_workspace(
            session, workspace_id=workspace_id,
            work_type=work_type, status=wo_status, priority=priority,
            factory_id=factory_id, machine_id=machine_id,
            skip=skip, limit=limit
        )

    def delete_work_order(self, session: Session, wo_id: int, workspace_id: int, user_id: int) -> WorkOrder:
        record = self.wo_dao.get_by_id_and_workspace(session, id=wo_id, workspace_id=workspace_id)
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Work order with ID {wo_id} not found")
        if record.is_deleted:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Work order is already deleted")
        return self.wo_dao.soft_delete(session, db_obj=record, deleted_by=user_id)

    # ─── Work Order Items ───────────────────────────────────────
    def add_item(
        self, session: Session, data: WorkOrderItemCreate,
        workspace_id: int, user_id: int
    ) -> WorkOrderItem:
        """Add item to work order."""
        wo = self.wo_dao.get_by_id_and_workspace(
            session, id=data.work_order_id, workspace_id=workspace_id
        )
        if not wo:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work order not found")

        item_dict = data.model_dump()
        item_dict['workspace_id'] = workspace_id
        item_dict['created_by'] = user_id
        return self.item_dao.create(session, obj_in=item_dict)

    def update_item(
        self, session: Session, item_id: int, data: WorkOrderItemUpdate,
        workspace_id: int
    ) -> WorkOrderItem:
        """Update work order item."""
        record = self.item_dao.get_by_id_and_workspace(session, id=item_id, workspace_id=workspace_id)
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work order item not found")
        update_dict = data.model_dump(exclude_unset=True)
        return self.item_dao.update(session, db_obj=record, obj_in=update_dict)

    def remove_item(self, session: Session, item_id: int, workspace_id: int) -> WorkOrderItem:
        """Remove item from work order."""
        record = self.item_dao.get_by_id_and_workspace(session, id=item_id, workspace_id=workspace_id)
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work order item not found")
        session.delete(record)
        session.flush()
        return record

    def get_items(self, session: Session, wo_id: int, workspace_id: int) -> List[WorkOrderItem]:
        return self.item_dao.get_by_work_order(session, work_order_id=wo_id, workspace_id=workspace_id)


work_order_manager = WorkOrderManager()
