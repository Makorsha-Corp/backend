"""Staged scheduled work orders — expected maintenance before confirm creates live WO."""
from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey, Text, Enum
from sqlalchemy.sql import func
from app.db.base_class import Base
from app.models.enums import WorkOrderPriorityEnum, WorkOrderScheduleStatusEnum


class WorkOrderSchedule(Base):
    __tablename__ = "work_order_schedules"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    scheduled_date = Column(Date, nullable=False, index=True)
    status = Column(
        Enum(WorkOrderScheduleStatusEnum),
        nullable=False,
        default=WorkOrderScheduleStatusEnum.STAGED,
        index=True,
    )

    work_order_template_id = Column(
        Integer, ForeignKey("work_order_templates.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    machine_id = Column(Integer, ForeignKey("machines.id", ondelete="CASCADE"), nullable=False, index=True)
    factory_id = Column(Integer, ForeignKey("factories.id"), nullable=False, index=True)
    factory_section_id = Column(Integer, ForeignKey("factory_sections.id"), nullable=True, index=True)
    work_order_type_id = Column(Integer, ForeignKey("work_order_types.id", ondelete="RESTRICT"), nullable=False)

    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    priority = Column(Enum(WorkOrderPriorityEnum), nullable=False, default=WorkOrderPriorityEnum.MEDIUM)
    assigned_to = Column(String(255), nullable=True)

    work_order_id = Column(Integer, ForeignKey("work_orders.id", ondelete="SET NULL"), nullable=True, index=True)

    confirmed_at = Column(DateTime, nullable=True)
    confirmed_by = Column(Integer, ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True)
    cancelled_at = Column(DateTime, nullable=True)
    cancelled_by = Column(Integer, ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True)

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    created_by = Column(Integer, ForeignKey("profiles.id"), nullable=True)
